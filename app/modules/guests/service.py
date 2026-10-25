"""Goście: gospodarstwa, osoby, obecność na wydarzeniach, RSVP przez link, import CSV."""

import csv
import io
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core import clock, crypto, mail_templates, qr, ratelimit
from app.core.config import get_settings
from app.core.db import utcnow
from app.core.email import queue_mail
from app.core.errors import Conflict, NotFound, Unprocessable
from app.core.ids import uuid7
from app.core.security import hash_token, new_token
from app.core.spreadsheet import csv_safe as _csv_safe
from app.modules.audit import service as audit
from app.modules.guests.models import (
    AGE_GROUPS,
    DIETS,
    SIDES,
    Guest,
    GuestEventAttendance,
    GuestInfo,
    Household,
    ReserveEntry,
    RsvpToken,
)
from app.modules.identity.service import Principal
from app.modules.workspace.models import Event, Wedding
from app.modules.workspace.permissions import Action, authorize
from app.modules.workspace.service import access_end, last_wedding_day

CHILD_GROUPS = ("child", "infant")
RETENTION_DAYS_AFTER_WEDDING = 90


def _conflict() -> Conflict:
    return Conflict(
        "Dane zmieniły się w międzyczasie. Pobierz aktualną wersję.",
        code="conflict.version_mismatch",
    )


def _commit(db: Session) -> None:
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise _conflict() from exc


def _ctx(guest_id: UUID) -> bytes:
    return b"guest.dietary_note:" + guest_id.bytes


def dietary_note(guest: Guest) -> str | None:
    if guest.dietary_note_encrypted is None:
        return None
    return crypto.decrypt(guest.dietary_note_encrypted, _ctx(guest.id))


def _set_note(guest: Guest, note: str | None) -> None:
    note = (note or "").strip() or None
    guest.dietary_note_encrypted = crypto.encrypt(note, _ctx(guest.id)) if note else None


def reencrypt_notes(db: Session, *, dry_run: bool, batch: int = 500) -> dict[str, int]:
    """Przeszyfrowanie uwag dietetycznych bieżącym kluczem (rotacja klucza).

    Bez zmiany `version` rekordu (treść się nie zmienia, klienci nie dostaną konfliktu).
    Zapis tylko, jeśli szyfrogram nie zmienił się w międzyczasie (równoległa edycja wygrywa).
    """
    current = crypto.current_version()
    stats = {"encrypted": 0, "old_key": 0, "rotated": 0}
    last_id: UUID | None = None
    while True:
        stmt = (
            select(Guest.id, Guest.dietary_note_encrypted)
            .where(Guest.dietary_note_encrypted.is_not(None))
            .order_by(Guest.id)
            .limit(batch)
        )
        if last_id is not None:
            stmt = stmt.where(Guest.id > last_id)
        rows = db.execute(stmt).all()
        if not rows:
            break
        for guest_id, blob in rows:
            stats["encrypted"] += 1
            if blob is None or crypto.key_version(blob) == current:
                continue
            stats["old_key"] += 1
            if dry_run:
                continue
            fresh = crypto.encrypt(crypto.decrypt(blob, _ctx(guest_id)), _ctx(guest_id))
            # Masowy UPDATE nie podbija licznika wersji (to robi tylko flush obiektu ORM).
            result = db.execute(
                update(Guest)
                .where(Guest.id == guest_id, Guest.dietary_note_encrypted == blob)
                .values(dietary_note_encrypted=fresh)
                .execution_options(synchronize_session=False)
            )
            stats["rotated"] += int(getattr(result, "rowcount", 0) or 0)
        db.commit()
        last_id = rows[-1][0]
    return stats


def _record(
    db: Session,
    actor_type: str,
    actor_id: UUID | None,
    wedding_id: UUID,
    entity: str,
    entity_id: UUID,
    action: str,
    changes: dict[str, Any] | None = None,
) -> None:
    audit.record(
        db,
        actor_type=actor_type,
        actor_id=actor_id,
        entity_type=entity,
        entity_id=entity_id,
        wedding_id=wedding_id,
        action=action,
        changes=changes,
    )


# --- odczyty pomocnicze -------------------------------------------------------------------


def attendance_map(db: Session, guest_ids: list[UUID]) -> dict[UUID, dict[UUID, str]]:
    result: dict[UUID, dict[UUID, str]] = defaultdict(dict)
    if guest_ids:
        for a in db.scalars(
            select(GuestEventAttendance).where(GuestEventAttendance.guest_id.in_(guest_ids))
        ):
            result[a.guest_id][a.event_id] = a.status
    return result


def active_links(db: Session, household_ids: list[UUID]) -> set[UUID]:
    if not household_ids:
        return set()
    rows = db.execute(
        select(RsvpToken, Household.wedding_id)
        .join(Household, Household.id == RsvpToken.household_id)
        .where(RsvpToken.household_id.in_(household_ids), RsvpToken.revoked_at.is_(None))
    ).all()
    last = {wid: last_wedding_day(db, db.get_one(Wedding, wid)) for wid in {w for _, w in rows}}
    return {t.household_id for t, wid in rows if _token_valid(t, last[wid])}


def age_breakdown(db: Session, wedding: Wedding, basis: str) -> tuple[int, int]:
    """(dorośli, dzieci) dla wyceny. Nastolatki liczone jak dorośli, niemowlęta pomijane.

    Dla basis="planned" dostępna jest tylko łączna planowana liczba (wszyscy jako dorośli).
    """
    if basis == "planned":
        return wedding.guest_count_planned or 0, 0
    stmt = select(Guest.age_group, func.count(func.distinct(Guest.id))).where(
        Guest.wedding_id == wedding.id
    )
    if basis == "confirmed":
        reception = list(
            db.scalars(
                select(Event.id).where(Event.wedding_id == wedding.id, Event.kind == "reception")
            )
        )
        stmt = stmt.join(GuestEventAttendance, GuestEventAttendance.guest_id == Guest.id).where(
            GuestEventAttendance.status == "attending"
        )
        if reception:
            stmt = stmt.where(GuestEventAttendance.event_id.in_(reception))
    by_age = {age: n for age, n in db.execute(stmt.group_by(Guest.age_group))}
    adults = by_age.get("adult", 0) + by_age.get("teen", 0)
    return adults, by_age.get("child", 0)


def counts(db: Session, wedding: Wedding) -> dict[str, int]:
    """Liczby gości dla budżetu: planowana, zaproszeni, potwierdzeni (przyjęcie)."""
    invited = (
        db.scalar(select(func.count()).select_from(Guest).where(Guest.wedding_id == wedding.id))
        or 0
    )
    reception = list(
        db.scalars(
            select(Event.id).where(Event.wedding_id == wedding.id, Event.kind == "reception")
        )
    )
    stmt = (
        select(func.count(func.distinct(GuestEventAttendance.guest_id)))
        .join(Guest, Guest.id == GuestEventAttendance.guest_id)
        .where(Guest.wedding_id == wedding.id, GuestEventAttendance.status == "attending")
    )
    if reception:
        stmt = stmt.where(GuestEventAttendance.event_id.in_(reception))
    confirmed = db.scalar(stmt) or 0
    return {"planned": wedding.guest_count_planned or 0, "invited": invited, "confirmed": confirmed}


# --- gospodarstwa ----------------------------------------------------------------------------


def _household(db: Session, wedding_id: UUID, household_id: UUID) -> Household:
    h = db.get(Household, household_id)
    if h is None or h.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono gospodarstwa.", code="household.not_found")
    return h


def _guest(db: Session, wedding_id: UUID, guest_id: UUID) -> Guest:
    g = db.get(Guest, guest_id)
    if g is None or g.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono gościa.", code="guest.not_found")
    return g


def list_households(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    *,
    side: str | None,
    invitation_status: str | None,
) -> tuple[list[Household], dict[UUID, list[Guest]]]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    stmt = select(Household).where(Household.wedding_id == wedding_id)
    if side:
        stmt = stmt.where(Household.side == side)
    if invitation_status:
        stmt = stmt.where(Household.invitation_status == invitation_status)
    households = list(db.scalars(stmt.order_by(Household.name, Household.id)))
    by_household: dict[UUID, list[Guest]] = defaultdict(list)
    if households:
        for g in db.scalars(
            select(Guest)
            .where(Guest.household_id.in_([h.id for h in households]))
            .order_by(Guest.created_at)
        ):
            by_household[g.household_id].append(g)
    return households, by_household


def household_guests(db: Session, household_id: UUID) -> list[Guest]:
    return list(
        db.scalars(
            select(Guest).where(Guest.household_id == household_id).order_by(Guest.created_at)
        )
    )


def create_household(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]
) -> Household:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    h = Household(wedding_id=wedding_id, **data)
    db.add(h)
    db.flush()
    _record(db, "user", principal.user.id, wedding_id, "household", h.id, "create")
    db.commit()
    return h


def get_household(
    db: Session, principal: Principal, wedding_id: UUID, household_id: UUID
) -> Household:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return _household(db, wedding_id, household_id)


def update_household(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    household_id: UUID,
    data: dict[str, Any],
    version: int,
) -> Household:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    h = _household(db, wedding_id, household_id)
    if h.version != version:
        raise _conflict()
    nullable = (
        "group_label",
        "contact_email",
        "contact_phone",
        "rsvp_deadline",
        "notes",
        "gift_note",
        "delivery_method",
        "delivery_by",
        "delivery_place",
        "delivery_planned_on",
        "delivered_on",
    )
    before = {k: getattr(h, k) for k in data}
    for k, v in data.items():
        if v is not None or k in nullable:
            setattr(h, k, v)
    _record(
        db,
        "user",
        principal.user.id,
        wedding_id,
        "household",
        h.id,
        "update",
        audit.diff(before, data),
    )
    _commit(db)
    return h


def delete_household(
    db: Session, principal: Principal, wedding_id: UUID, household_id: UUID
) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    h = _household(db, wedding_id, household_id)
    db.delete(h)
    _record(db, "user", principal.user.id, wedding_id, "household", household_id, "delete")
    db.commit()


# --- goście ----------------------------------------------------------------------------------


def list_guests(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    *,
    dietary: str | None,
    needs_accommodation: bool | None,
    event_id: UUID | None,
    attendance: str | None,
) -> list[Guest]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    stmt = select(Guest).where(Guest.wedding_id == wedding_id)
    if dietary:
        stmt = stmt.where(Guest.dietary_preference == dietary)
    if needs_accommodation is not None:
        stmt = stmt.where(Guest.needs_accommodation.is_(needs_accommodation))
    if event_id and attendance:
        if attendance == "pending":
            answered = select(GuestEventAttendance.guest_id).where(
                GuestEventAttendance.event_id == event_id, GuestEventAttendance.status != "pending"
            )
            stmt = stmt.where(Guest.id.not_in(answered))
        else:
            stmt = stmt.join(GuestEventAttendance, GuestEventAttendance.guest_id == Guest.id).where(
                GuestEventAttendance.event_id == event_id, GuestEventAttendance.status == attendance
            )
    return list(db.scalars(stmt.order_by(Guest.last_name.asc().nulls_last(), Guest.first_name)))


def create_guest(
    db: Session, principal: Principal, wedding_id: UUID, household_id: UUID, data: dict[str, Any]
) -> Guest:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    _household(db, wedding_id, household_id)
    note = data.pop("dietary_note", None)
    # id nadane przed zapisem: szyfrogram wiąże się z id, a rekord powstaje jednym INSERT.
    g = Guest(id=uuid7(), wedding_id=wedding_id, household_id=household_id, **data)
    _set_note(g, note)
    db.add(g)
    db.flush()
    _record(db, "user", principal.user.id, wedding_id, "guest", g.id, "create")
    db.commit()
    return g


def update_guest(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    guest_id: UUID,
    data: dict[str, Any],
    version: int,
) -> Guest:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    g = _guest(db, wedding_id, guest_id)
    if g.version != version:
        raise _conflict()
    if data.get("household_id"):
        _household(db, wedding_id, data["household_id"])
    changed = sorted(data)  # do audytu tylko nazwy pól: bez imion i notatek
    if "dietary_note" in data:
        _set_note(g, data.pop("dietary_note"))
    for k, v in data.items():
        if v is not None or k in ("last_name", "notes"):
            setattr(g, k, v)
    _record(
        db,
        "user",
        principal.user.id,
        wedding_id,
        "guest",
        g.id,
        "update",
        {"fields": [None, changed]},
    )
    _commit(db)
    return g


def delete_guest(db: Session, principal: Principal, wedding_id: UUID, guest_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    g = _guest(db, wedding_id, guest_id)
    db.delete(g)
    _record(db, "user", principal.user.id, wedding_id, "guest", guest_id, "delete")
    db.commit()


def _set_attendance(db: Session, guest: Guest, event_id: UUID, status: str, via: str) -> str:
    a = db.get(GuestEventAttendance, (guest.id, event_id))
    old = a.status if a else "pending"
    if a is None:
        a = GuestEventAttendance(guest_id=guest.id, event_id=event_id)
        db.add(a)
    a.status, a.responded_at, a.responded_via = status, utcnow(), via
    return old


def _event(db: Session, wedding_id: UUID, event_id: UUID) -> Event:
    e = db.get(Event, event_id)
    if e is None or e.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono wydarzenia.", code="event.not_found")
    return e


def set_attendance(
    db: Session, principal: Principal, wedding_id: UUID, guest_id: UUID, event_id: UUID, status: str
) -> Guest:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    g = _guest(db, wedding_id, guest_id)
    _event(db, wedding_id, event_id)
    old = _set_attendance(db, g, event_id, status, "couple")
    _record(
        db,
        "user",
        principal.user.id,
        wedding_id,
        "attendance",
        g.id,
        "set",
        {"event_id": [None, str(event_id)], "status": [old, status]},
    )
    db.commit()
    return g


def stats(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    guests = list(db.scalars(select(Guest).where(Guest.wedding_id == wedding_id)))
    households = list(db.scalars(select(Household).where(Household.wedding_id == wedding_id)))
    side_of = {h.id: h.side for h in households}
    att = attendance_map(db, [g.id for g in guests])
    events = list(
        db.scalars(
            select(Event)
            .where(Event.wedding_id == wedding_id)
            .order_by(Event.starts_at.asc().nulls_last())
        )
    )
    event_stats = []
    for e in events:
        c: Counter[str] = Counter()
        adults = children = 0
        for g in guests:
            status = att[g.id].get(e.id, "pending")
            c[status] += 1
            if status == "attending":
                if g.age_group in CHILD_GROUPS:
                    children += 1
                else:
                    adults += 1
        event_stats.append(
            {
                "event_id": e.id,
                "name": e.name,
                "kind": e.kind,
                "attending": c["attending"],
                "declined": c["declined"],
                "maybe": c["maybe"],
                "pending": c["pending"],
                "attending_adults": adults,
                "attending_children": children,
            }
        )
    return {
        "households": len(households),
        "guests": len(guests),
        "adults": sum(1 for g in guests if g.age_group not in CHILD_GROUPS),
        "children": sum(1 for g in guests if g.age_group in CHILD_GROUPS),
        "plus_ones": sum(1 for g in guests if g.is_plus_one),
        "by_side": dict(Counter(side_of.get(g.household_id, "other") for g in guests)),
        "diets": dict(Counter(g.dietary_preference for g in guests)),
        "with_dietary_note": sum(1 for g in guests if g.dietary_note_encrypted),
        "needs_accommodation": sum(1 for g in guests if g.needs_accommodation),
        "needs_transport": sum(1 for g in guests if g.needs_transport),
        "invitations": dict(Counter(h.invitation_status for h in households)),
        "events": event_stats,
    }


# --- link RSVP ----------------------------------------------------------------------------


LINK_DAYS_AFTER_WEDDING = 7


def _access_end(last_day: date) -> datetime:
    return access_end(last_day, LINK_DAYS_AFTER_WEDDING)


def _rsvp_expiry(db: Session, wedding: Wedding, household: Household) -> datetime:
    """Strona gościa działa do 7 dni po ostatnim dniu wesela — niezależnie od terminu RSVP.

    Termin odpowiedzi (`rsvp_deadline`) zamyka tylko edycję odpowiedzi (`_is_open`); po nim gość
    nadal widzi program, dojazd i komunikaty. Bez daty wesela: rok od wydania linku.
    """
    last = last_wedding_day(db, wedding)
    if last is None:
        return datetime.combine(
            clock.today() + timedelta(days=365), time(23, 59), tzinfo=clock.WARSAW
        )
    return _access_end(last)


def _token_valid(t: RsvpToken, last: date | None) -> bool:
    """Ważność liczona od aktualnej daty wesela (data mogła się zmienić po wydaniu linku).

    Zapisane `expires_at` obowiązuje tylko, gdy wesele nie ma daty.
    """
    if t.revoked_at is not None:
        return False
    expires = _access_end(last) if last is not None else t.expires_at
    return expires > utcnow()


def create_rsvp_link(
    db: Session, principal: Principal, wedding_id: UUID, household_id: UUID
) -> tuple[str, str, datetime]:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    h = _household(db, wedding_id, household_id)
    wedding = db.get_one(Wedding, wedding_id)
    db.execute(
        update(RsvpToken)
        .where(RsvpToken.household_id == h.id, RsvpToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    token, token_hash = new_token()
    expires = _rsvp_expiry(db, wedding, h)
    db.add(RsvpToken(household_id=h.id, token_hash=token_hash, expires_at=expires))
    _record(db, "user", principal.user.id, wedding_id, "rsvp_link", h.id, "create")
    db.commit()
    url = f"{get_settings().public_app_url}/rsvp/{token}"
    return token, url, expires


def qr_svg(url: str) -> str:
    """Kod QR z adresem RSVP (segno, BSD) — czarny na białym, do druku na zaproszeniu."""
    return qr.qr_svg(url, scale=4)


def rsvp_qr(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    *,
    household_ids: list[UUID] | None,
    include_with_link: bool,
    dry_run: bool,
) -> dict[str, Any]:
    """Karty z kodem QR do druku: nowe linki dla wybranych rodzin.

    Token znamy tylko w chwili tworzenia (w bazie hash), więc druk hurtowy tworzy nowe linki.
    Rodziny z aktywnym linkiem pomijamy (jak przy e-mailach), chyba że para zaznaczy inaczej.
    """
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    wedding = db.get_one(Wedding, wedding_id)
    stmt = select(Household).where(Household.wedding_id == wedding_id)
    if household_ids is not None:
        stmt = stmt.where(Household.id.in_(household_ids))
    households = list(db.scalars(stmt.order_by(Household.name)))
    if household_ids is not None and len(households) != len(set(household_ids)):
        raise NotFound("Nie znaleziono zaproszenia.", code="household.not_found")
    linked = active_links(db, [h.id for h in households])
    targets = [h for h in households if include_with_link or h.id not in linked]
    cards = []
    base = get_settings().public_app_url
    for h in targets:
        url = None
        if not dry_run:
            db.execute(
                update(RsvpToken)
                .where(RsvpToken.household_id == h.id, RsvpToken.revoked_at.is_(None))
                .values(revoked_at=utcnow())
            )
            token, token_hash = new_token()
            db.add(
                RsvpToken(
                    household_id=h.id,
                    token_hash=token_hash,
                    expires_at=_rsvp_expiry(db, wedding, h),
                )
            )
            _record(db, "user", principal.user.id, wedding_id, "rsvp_link", h.id, "qr")
            url = f"{base}/rsvp/{token}"
        cards.append(
            {
                "household_id": h.id,
                "name": h.name,
                "has_active_link": h.id in linked,
                "rsvp_deadline": h.rsvp_deadline,
                "url": url,
                "qr_svg": qr_svg(url) if url else None,
            }
        )
    if not dry_run:
        db.commit()
    return {
        "dry_run": dry_run,
        "cards": cards,
        "with_link_skipped": len(households) - len(targets),
    }


def revoke_rsvp_link(
    db: Session, principal: Principal, wedding_id: UUID, household_id: UUID
) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    _household(db, wedding_id, household_id)
    result = db.execute(
        update(RsvpToken)
        .where(RsvpToken.household_id == household_id, RsvpToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    if not getattr(result, "rowcount", 0):
        raise NotFound("Brak aktywnego linku RSVP.", code="rsvp.not_found")
    _record(db, "user", principal.user.id, wedding_id, "rsvp_link", household_id, "revoke")
    db.commit()


def _resolve_token(db: Session, token: str, ip: str) -> tuple[RsvpToken, Household, Wedding]:
    limit = get_settings().rsvp_rate_limit
    ratelimit.hit(db, ratelimit.key_for("rsvp:ip", ip), limit, timedelta(minutes=10))
    db.commit()
    t = db.scalars(select(RsvpToken).where(RsvpToken.token_hash == hash_token(token))).first()
    gone = NotFound("Link jest nieprawidłowy lub wygasł.", code="rsvp.not_found")
    if t is None or t.revoked_at is not None:
        raise gone
    h = db.get_one(Household, t.household_id)
    wedding = db.get_one(Wedding, h.wedding_id)
    if not _token_valid(t, last_wedding_day(db, wedding)):
        raise gone
    return t, h, wedding


def _is_open(h: Household) -> bool:
    return h.rsvp_deadline is None or clock.today() <= h.rsvp_deadline


def rsvp_view(db: Session, token: str, ip: str) -> dict[str, Any]:
    t, h, wedding = _resolve_token(db, token, ip)
    t.last_used_at = utcnow()
    db.commit()
    guests = household_guests(db, h.id)
    att = attendance_map(db, [g.id for g in guests])
    events = list(
        db.scalars(
            select(Event)
            .where(Event.wedding_id == wedding.id)
            .order_by(Event.starts_at.asc().nulls_last())
        )
    )
    info = db.get(GuestInfo, wedding.id)
    from app.modules.logistics.service import guest_runs  # transport czyta gości

    runs, chosen = guest_runs(db, wedding.id, [g.id for g in guests])
    from app.modules.guests import page
    from app.modules.menu import service as menu  # menu czyta gości, nie odwrotnie
    from app.modules.schedule import music  # muzyka czyta gości, nie odwrotnie

    return {
        "menu": menu.guest_menu(db, wedding.id),
        **page.guest_extras(db, wedding.id, h.id),
        "songs": {
            "enabled": bool(info and info.song_requests),
            "limit": music.GUEST_LIMIT,
            "mine": music.guest_suggestions(db, h.id),
        },
        "theme": {
            "style": info.theme if info else "classic",
            "accent": info.accent if info else None,
        },
        "wedding_name": wedding.name,
        "household_name": h.name,
        "transport_runs": runs,
        "language": h.language,
        "rsvp_deadline": h.rsvp_deadline,
        "is_open": _is_open(h),
        "events": [
            {
                "id": e.id,
                "kind": e.kind,
                "name": e.name,
                "starts_at": e.starts_at,
                "ends_at": e.ends_at,
                "address": e.address,
            }
            for e in events
        ],
        "guests": [
            {
                "id": g.id,
                "first_name": g.first_name,
                "age_group": g.age_group,
                "is_plus_one": g.is_plus_one,
                "added_via_rsvp": g.added_via_rsvp,
                "dietary_preference": g.dietary_preference,
                "has_dietary_note": g.dietary_note_encrypted is not None,
                "needs_accommodation": g.needs_accommodation,
                "needs_transport": g.needs_transport,
                "attendance": att[g.id],
                "transport_run_ids": chosen.get(g.id, []),
            }
            for g in guests
        ],
        "info": _published_info(db, wedding.id),
        "schedule": _guest_schedule(db, wedding.id),
    }


PREVIEW_GUESTS = (("Anna", "adult"), ("Jan", "adult"), ("Zosia", "child"))


def guest_page_preview(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    """Podgląd strony gościa dla pary: prawdziwe wydarzenia, program i informacje (także
    nieopublikowane — jako szkic), ale fikcyjna rodzina zamiast prawdziwych gości."""
    authorize(db, principal.user.id, wedding_id, Action.READ)
    wedding = db.get_one(Wedding, wedding_id)
    events = list(
        db.scalars(
            select(Event)
            .where(Event.wedding_id == wedding_id)
            .order_by(Event.starts_at.asc().nulls_last())
        )
    )
    info = db.get(GuestInfo, wedding_id)
    from app.modules.logistics.service import guest_runs

    runs, _ = guest_runs(db, wedding_id, [])
    from app.modules.guests import page
    from app.modules.menu import service as menu
    from app.modules.schedule import music

    return {
        "menu": menu.guest_menu(db, wedding_id),
        **page.guest_extras(db, wedding_id, None),
        "songs": {
            "enabled": bool(info and info.song_requests),
            "limit": music.GUEST_LIMIT,
            "mine": [],
        },
        "theme": {
            "style": info.theme if info else "classic",
            "accent": info.accent if info else None,
        },
        "wedding_name": wedding.name,
        "household_name": "Przykładowa rodzina",
        "transport_runs": runs,
        "rsvp_deadline": None,
        "is_open": True,
        "events": [
            {
                "id": e.id,
                "kind": e.kind,
                "name": e.name,
                "starts_at": e.starts_at,
                "ends_at": e.ends_at,
                "address": e.address,
            }
            for e in events
        ],
        "guests": [
            {
                "id": uuid7(),
                "first_name": name,
                "age_group": age,
                "is_plus_one": False,
                "added_via_rsvp": False,
                "dietary_preference": "standard",
                "has_dietary_note": False,
                "needs_accommodation": False,
                "needs_transport": False,
                "attendance": {},
            }
            for name, age in PREVIEW_GUESTS
        ],
        "info": {k: getattr(info, k) for k in INFO_FIELDS} if info else None,
        "schedule": _guest_schedule(db, wedding_id),
        "preview_info_published": bool(info and info.published),
    }


def _published_info(db: Session, wedding_id: UUID) -> dict[str, Any] | None:
    info = db.get(GuestInfo, wedding_id)
    if info is None or not info.published:
        return None
    return {k: getattr(info, k) for k in INFO_FIELDS}


def _guest_schedule(db: Session, wedding_id: UUID) -> list[dict[str, Any]]:
    # Import lokalny: harmonogram nie zależy od gości, a goście tylko czytają program.
    from app.modules.schedule.models import ScheduleItem

    items = db.scalars(
        select(ScheduleItem)
        .where(ScheduleItem.wedding_id == wedding_id, ScheduleItem.for_guests.is_(True))
        .order_by(ScheduleItem.starts_at)
    )
    return [
        {"title": i.title, "starts_at": clock.local(i.starts_at), "location": i.location}
        for i in items
    ]


def rsvp_submit(db: Session, token: str, ip: str, data: dict[str, Any]) -> dict[str, Any]:
    t, h, wedding = _resolve_token(db, token, ip)
    if not _is_open(h):
        raise Conflict("Termin potwierdzeń minął. Skontaktuj się z parą młodą.", code="rsvp.closed")
    guests = {g.id: g for g in household_guests(db, h.id)}
    event_ids = set(db.scalars(select(Event.id).where(Event.wedding_id == wedding.id)))
    for r in data["responses"]:
        if r["guest_id"] not in guests or r["event_id"] not in event_ids:
            raise Unprocessable(
                "Odpowiedź dotyczy osoby lub wydarzenia spoza zaproszenia.",
                code="rsvp.invalid_target",
            )
    for d in data["guests"]:
        if d["guest_id"] not in guests:
            raise Unprocessable("Dane dotyczą osoby spoza zaproszenia.", code="rsvp.invalid_target")
    for r in data["responses"]:
        _set_attendance(db, guests[r["guest_id"]], r["event_id"], r["status"], "rsvp_link")
    for d in data["guests"]:
        g = guests[d["guest_id"]]
        for key in ("dietary_preference", "needs_accommodation", "needs_transport"):
            if d.get(key) is not None:
                setattr(g, key, d[key])
        if d.get("dietary_note") is not None:
            _set_note(g, d["dietary_note"])
        if d.get("transport_run_ids") is not None:
            from app.modules.logistics.service import set_guest_runs

            set_guest_runs(db, wedding.id, g.id, d["transport_run_ids"])
            if d["transport_run_ids"]:
                g.needs_transport = True
    t.last_used_at = utcnow()
    _record(
        db,
        "guest",
        None,
        wedding.id,
        "rsvp",
        h.id,
        "submit",
        {
            "responses": [None, len(data["responses"])],
            "health_data_consent": [None, data["health_data_consent"]],
        },
    )
    db.commit()
    return rsvp_view(db, token, ip)


# Liczby osób towarzyszących nie ograniczamy (decyzja produktowa). To tylko bezpiecznik
# przeciw nadużyciu publicznego linku — para zawsze może dopisać więcej sama.
MAX_RSVP_COMPANIONS = 20


def rsvp_add_companion(db: Session, token: str, ip: str, data: dict[str, Any]) -> dict[str, Any]:
    t, h, wedding = _resolve_token(db, token, ip)
    if not _is_open(h):
        raise Conflict("Termin potwierdzeń minął. Skontaktuj się z parą młodą.", code="rsvp.closed")
    added = db.scalar(
        select(func.count())
        .select_from(Guest)
        .where(Guest.household_id == h.id, Guest.added_via_rsvp.is_(True))
    )
    if (added or 0) >= MAX_RSVP_COMPANIONS:
        raise Conflict(
            "Dopisano już wiele osób. Pozostałe zgłoś parze młodej.",
            code="rsvp.companions_limit",
        )
    g = Guest(
        id=uuid7(),
        wedding_id=wedding.id,
        household_id=h.id,
        first_name=data["first_name"].strip(),
        last_name=(data.get("last_name") or "").strip() or None,
        age_group=data["age_group"],
        is_plus_one=True,
        added_via_rsvp=True,
    )
    db.add(g)
    db.flush()
    t.last_used_at = utcnow()
    _record(db, "guest", None, wedding.id, "guest", g.id, "create", {"via": [None, "rsvp_link"]})
    db.commit()
    return rsvp_view(db, token, ip)


def rsvp_reserve_gift(
    db: Session, token: str, ip: str, gift_id: UUID, reserved: bool
) -> dict[str, Any]:
    from app.modules.guests import gifts

    t, h, wedding = _resolve_token(db, token, ip)
    t.last_used_at = utcnow()
    gifts.reserve(db, wedding.id, h.id, gift_id, reserved)
    return rsvp_view(db, token, ip)


def rsvp_add_wish(db: Session, token: str, ip: str, data: dict[str, Any]) -> dict[str, Any]:
    from app.modules.guests import page

    t, h, wedding = _resolve_token(db, token, ip)
    t.last_used_at = utcnow()
    page.add_wish(db, wedding.id, h.id, data)
    return rsvp_view(db, token, ip)


def rsvp_suggest_song(db: Session, token: str, ip: str, data: dict[str, Any]) -> dict[str, Any]:
    from app.modules.schedule import music

    t, h, wedding = _resolve_token(db, token, ip)
    if not _is_open(h):
        raise Conflict("Termin potwierdzeń minął. Skontaktuj się z parą młodą.", code="rsvp.closed")
    t.last_used_at = utcnow()
    artist = (data.get("artist") or "").strip() or None
    music.suggest(db, wedding.id, h.id, {"title": data["title"].strip(), "artist": artist})
    return rsvp_view(db, token, ip)


def rsvp_remove_companion(db: Session, token: str, ip: str, guest_id: UUID) -> dict[str, Any]:
    t, h, wedding = _resolve_token(db, token, ip)
    if not _is_open(h):
        raise Conflict("Termin potwierdzeń minął. Skontaktuj się z parą młodą.", code="rsvp.closed")
    g = db.get(Guest, guest_id)
    if g is None or g.household_id != h.id or not g.added_via_rsvp:
        raise Unprocessable(
            "Usunąć można tylko osobę dopisaną w tym formularzu.", code="rsvp.invalid_target"
        )
    db.delete(g)
    t.last_used_at = utcnow()
    _record(
        db, "guest", None, wedding.id, "guest", guest_id, "delete", {"via": [None, "rsvp_link"]}
    )
    db.commit()
    return rsvp_view(db, token, ip)


# --- import CSV --------------------------------------------------------------------------

_TRUE = {"1", "tak", "t", "yes", "y", "true", "x"}
_DIET_ALIASES = {
    "": "standard",
    "standard": "standard",
    "standardowa": "standard",
    "wegetarianska": "vegetarian",
    "wegetariańska": "vegetarian",
    "vegetarian": "vegetarian",
    "weganska": "vegan",
    "wegańska": "vegan",
    "vegan": "vegan",
    "bezglutenowa": "gluten_free",
    "gluten_free": "gluten_free",
    "inna": "other",
    "other": "other",
}
_LANGUAGE_ALIASES: dict[str, str | None] = {
    "": None,
    "auto": None,
    "pl": "pl",
    "polski": "pl",
    "en": "en",
    "angielski": "en",
    "english": "en",
}
_SIDE_ALIASES = {
    "": "both",
    "panna mloda": "bride",
    "panna młoda": "bride",
    "bride": "bride",
    "pan mlody": "groom",
    "pan młody": "groom",
    "groom": "groom",
    "oboje": "both",
    "both": "both",
    "inne": "other",
    "other": "other",
}
_AGE_ALIASES = {
    "": "adult",
    "dorosly": "adult",
    "dorosły": "adult",
    "adult": "adult",
    "nastolatek": "teen",
    "teen": "teen",
    "dziecko": "child",
    "child": "child",
    "niemowle": "infant",
    "niemowlę": "infant",
    "infant": "infant",
}


# --- eksport CSV (Excel) ----------------------------------------------------------------------

AGE_LABELS = {"adult": "dorosły", "teen": "nastolatek", "child": "dziecko", "infant": "maluch"}
DIET_LABELS = {
    "standard": "bez wymagań",
    "vegetarian": "wegetariańska",
    "vegan": "wegańska",
    "gluten_free": "bezglutenowa",
    "other": "inna",
}
ANSWER_LABELS = {
    "attending": "będzie",
    "declined": "nie będzie",
    "maybe": "nie wie",
    "pending": "brak odpowiedzi",
}


DELIVERY_LABELS = {
    "in_person": "osobiście",
    "post": "pocztą",
    "online": "e-mail/link",
    "other": "inaczej",
}


def export_csv(db: Session, principal: Principal, wedding_id: UUID, *, include_notes: bool) -> str:
    """Lista gości do arkusza: średnik i BOM (polski Excel), jedna osoba w wierszu.

    Uwagi dietetyczne (mogą dotyczyć zdrowia) tylko na wyraźne życzenie — wpis w audycie.
    """
    from app.modules.seating.models import SeatAssignment, SeatingTable

    authorize(db, principal.user.id, wedding_id, Action.EXPORT)
    rows = db.execute(
        select(Guest, Household)
        .join(Household, Household.id == Guest.household_id)
        .where(Guest.wedding_id == wedding_id)
        .order_by(Household.name, Guest.created_at)
    ).all()
    seats = {
        a.guest_id: (t.name, a.seat_number)
        for a, t in db.execute(
            select(SeatAssignment, SeatingTable)
            .join(SeatingTable, SeatingTable.id == SeatAssignment.table_id)
            .where(SeatAssignment.wedding_id == wedding_id)
        )
    }
    reception = db.scalars(
        select(Event.id).where(Event.wedding_id == wedding_id, Event.kind == "reception")
    ).first()
    att = attendance_map(db, [g.id for g, _ in rows])
    # Transport i noclegi (moduł logistics): kursy i pokój przy osobie.
    from app.modules.logistics.models import LodgingRoom, RoomGuest, TransportRun, TransportSeat

    runs_of: dict[UUID, list[str]] = defaultdict(list)
    for guest_id, run_name in db.execute(
        select(TransportSeat.guest_id, TransportRun.name)
        .join(TransportRun, TransportRun.id == TransportSeat.run_id)
        .where(TransportRun.wedding_id == wedding_id)
        .order_by(TransportRun.departs_at.asc().nulls_last())
    ):
        runs_of[guest_id].append(run_name)
    room_of = {
        guest_id: f"{place}, {name}"
        for guest_id, place, name in db.execute(
            select(RoomGuest.guest_id, LodgingRoom.place, LodgingRoom.name)
            .join(LodgingRoom, LodgingRoom.id == RoomGuest.room_id)
            .where(LodgingRoom.wedding_id == wedding_id)
        )
    }
    header = [
        "Zaproszenie",
        "Imię",
        "Nazwisko",
        "Wiek",
        "Przyjęcie",
        "Dieta",
        *(["Uwagi dla kuchni"] if include_notes else []),
        "Stół",
        "Miejsce",
        "Nocleg",
        "Transport",
        "E-mail zaproszenia",
        "Telefon zaproszenia",
        "Wręczenie",
        "Miejscowość",
        "Kurs",
        "Pokój",
    ]
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", lineterminator="\r\n")
    writer.writerow(header)
    for g, h in rows:
        table, seat = seats.get(g.id, ("", None))
        answer = att[g.id].get(reception, "pending") if reception else "pending"
        writer.writerow(
            [
                _csv_safe(h.name),
                _csv_safe(g.first_name),
                _csv_safe(g.last_name or ""),
                AGE_LABELS.get(g.age_group, g.age_group),
                ANSWER_LABELS.get(answer, answer),
                DIET_LABELS.get(g.dietary_preference, g.dietary_preference),
                *([_csv_safe(dietary_note(g) or "")] if include_notes else []),
                _csv_safe(table),
                seat or "",
                "tak" if g.needs_accommodation else "",
                "tak" if g.needs_transport else "",
                _csv_safe(h.contact_email or ""),
                _csv_safe(h.contact_phone or ""),
                DELIVERY_LABELS.get(h.delivery_method or "", ""),
                _csv_safe(h.delivery_place or ""),
                _csv_safe(", ".join(runs_of.get(g.id, []))),
                _csv_safe(room_of.get(g.id, "")),
            ]
        )
    _record(
        db,
        "user",
        principal.user.id,
        wedding_id,
        "guests",
        wedding_id,
        "export_csv",
        {"rows": [None, len(rows)], "include_notes": [None, include_notes]},
    )
    db.commit()
    return "\ufeff" + out.getvalue()


def import_csv(
    db: Session, principal: Principal, wedding_id: UUID, text: str, dry_run: bool
) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    text = text.lstrip("﻿")  # BOM z Excela
    first_line = text.splitlines()[0] if text.strip() else ""
    delimiter = ";" if first_line.count(";") >= first_line.count(",") else ","
    # newline="" + restkey: poprawna obsługa \r\n, pól w cudzysłowach i nadmiarowych kolumn.
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter, restkey="_extra")
    errors: list[dict[str, Any]] = []
    rows: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    try:
        headers = {(h or "").strip().lower() for h in (reader.fieldnames or [])}
        if not {"household", "first_name"} <= headers:
            raise Unprocessable(
                "CSV musi mieć kolumny household i first_name.", code="import.missing_columns"
            )
        for line_no, raw in enumerate(reader, start=2):
            if line_no > 2001:
                raise Unprocessable(
                    "Maksymalnie 2000 wierszy w jednym imporcie.", code="import.too_many_rows"
                )
            row = {
                k.strip().lower(): v.strip()
                for k, v in raw.items()
                if isinstance(k, str) and isinstance(v, str)
            }
            try:
                rows.append(_parse_row(row))
            except ValueError as exc:
                errors.append({"row": line_no, "message": str(exc)})
    except csv.Error as exc:
        raise Unprocessable(
            "Nie udało się odczytać pliku CSV (sprawdź cudzysłowy i separatory).",
            code="import.malformed",
        ) from exc

    existing = {
        h.name.strip().lower(): h
        for h in db.scalars(select(Household).where(Household.wedding_id == wedding_id))
    }

    created_h: dict[str, Household] = {}
    reused: set[str] = set()
    guests_created = 0
    if not errors:
        for key, household_data, guest_data in rows:
            h = existing.get(key) or created_h.get(key)
            if h is None:
                h = Household(wedding_id=wedding_id, **household_data)
                db.add(h)
                db.flush()
                created_h[key] = h
            elif key in existing:
                reused.add(key)
            db.add(Guest(wedding_id=wedding_id, household_id=h.id, **guest_data))
            guests_created += 1
        if dry_run:
            db.rollback()
        else:
            _record(
                db,
                "user",
                principal.user.id,
                wedding_id,
                "guest",
                wedding_id,
                "import",
                {"guests": [None, guests_created]},
            )
            db.commit()
    return {
        "dry_run": dry_run,
        "households_created": len(created_h),
        "households_reused": len(reused),
        "guests_created": guests_created,
        "errors": errors,
    }


def _parse_row(row: dict[str, str]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    household, first = row.get("household", ""), row.get("first_name", "")
    if not household or not first:
        raise ValueError("Brak household lub first_name.")
    if len(household) > 150 or len(first) > 80 or len(row.get("last_name", "")) > 80:
        raise ValueError("Za długa wartość tekstowa.")
    side = _SIDE_ALIASES.get(row.get("side", "").lower())
    age = _AGE_ALIASES.get(row.get("age_group", "").lower())
    diet = _DIET_ALIASES.get(row.get("dietary", "").lower())
    if side not in SIDES:
        raise ValueError(f"Nieznana strona: {row.get('side')!r}.")
    if age not in AGE_GROUPS:
        raise ValueError(f"Nieznana grupa wiekowa: {row.get('age_group')!r}.")
    if diet not in DIETS:
        raise ValueError(f"Nieznana dieta: {row.get('dietary')!r}.")
    email = row.get("email") or None
    if email and ("@" not in email or len(email) > 320):
        raise ValueError("Nieprawidłowy e-mail.")
    raw_language = row.get("language", "").lower()
    if raw_language not in _LANGUAGE_ALIASES:
        raise ValueError(f"Nieznany język: {row.get('language')!r} (polski albo angielski).")
    household_data = {
        "name": household,
        "side": side,
        "contact_email": email.lower() if email else None,
        "contact_phone": (row.get("phone") or None),
        "language": _LANGUAGE_ALIASES[raw_language],
    }
    guest_data = {
        "first_name": first,
        "last_name": row.get("last_name") or None,
        "age_group": age,
        "dietary_preference": diet,
        "needs_accommodation": row.get("accommodation", "").lower() in _TRUE,
        "needs_transport": row.get("transport", "").lower() in _TRUE,
    }
    return household.lower(), household_data, guest_data


# --- retencja (RODO) -------------------------------------------------------------------


def anonymize_after_wedding(db: Session) -> int:
    """Anonimizacja danych gości 90 dni po ostatnim dniu wesela (zadanie okresowe)."""
    cutoff = clock.today() - timedelta(days=RETENTION_DAYS_AFTER_WEDDING)
    done = 0
    for wedding in db.scalars(select(Wedding).where(Wedding.guests_anonymized_at.is_(None))):
        last_day = last_wedding_day(db, wedding)
        if last_day is None or last_day >= cutoff:
            continue
        for i, g in enumerate(
            db.scalars(
                select(Guest).where(Guest.wedding_id == wedding.id).order_by(Guest.created_at)
            ),
            start=1,
        ):
            g.first_name, g.last_name = f"Gość {i}", None
            g.dietary_note_encrypted, g.notes = None, None
        db.execute(
            update(Household)
            .where(Household.wedding_id == wedding.id)
            .values(
                name="Gospodarstwo",
                contact_email=None,
                contact_phone=None,
                notes=None,
                delivery_by=None,
                delivery_place=None,
            )
        )
        db.execute(
            update(RsvpToken)
            .where(
                RsvpToken.household_id.in_(
                    select(Household.id).where(Household.wedding_id == wedding.id)
                ),
                RsvpToken.revoked_at.is_(None),
            )
            .values(revoked_at=utcnow())
        )
        # Lista rezerwowa po weselu jest zbędna: usuwamy ją w całości.
        db.execute(delete(ReserveEntry).where(ReserveEntry.wedding_id == wedding.id))
        # „Kto jest kim” i kontakt w informacjach dla usługodawców to dane osób z rodziny.
        from app.modules.schedule.models import VendorBrief

        db.execute(
            update(VendorBrief)
            .where(VendorBrief.wedding_id == wedding.id)
            .values(people=[], contact=None)
        )
        wedding.guests_anonymized_at = utcnow()
        _record(db, "system", None, wedding.id, "guest", wedding.id, "anonymize_retention")
        done += 1
    db.commit()
    return done


# Nazwy miesięcy na stałe — `%B` zależy od ustawień regionalnych serwera.
EN_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)  # fmt: skip


def rsvp_mail(wedding_name: str, h: Household, link: str) -> mail_templates.Email:
    """E-mail z linkiem RSVP w języku zaproszenia (polski albo angielski)."""
    if h.language == "en":
        d = h.rsvp_deadline
        deadline = f" by {d.day} {EN_MONTHS[d.month - 1]} {d.year}" if d else ""
        return mail_templates.build(
            f"{wedding_name}: please confirm your attendance",
            heading=wedding_name,
            paragraphs=[
                f"Hello, you are invited to {wedding_name}. "
                f"Please confirm your attendance{deadline}.",
                "In the form you can also tell us about your diet and whether you need "
                "accommodation or transport.",
            ],
            action=("Confirm attendance", link),
            note="This message was sent by the Nasz dzień app on behalf of the couple. "
            "If you received it by mistake, please ignore it.",
            settings_link=False,
            lang="en",
        )
    deadline = f" do {h.rsvp_deadline.strftime('%d.%m.%Y')}" if h.rsvp_deadline else ""
    return mail_templates.build(
        f"{wedding_name}: prosimy o potwierdzenie obecności",
        heading=wedding_name,
        paragraphs=[
            f"Dzień dobry, zapraszamy na {wedding_name}. "
            f"Prosimy o potwierdzenie obecności{deadline}.",
            "W formularzu można też podać dietę i potrzebę noclegu lub transportu.",
        ],
        action=("Potwierdź obecność", link),
        note="Wiadomość wysłała aplikacja Nasz dzień na prośbę pary młodej. "
        "Jeśli to pomyłka, prosimy ją zignorować.",
        # Gość nie ma konta: bez linku do ustawień powiadomień.
        settings_link=False,
    )


# --- strona informacyjna dla gości -------------------------------------------------------------

INFO_FIELDS = (
    "welcome",
    "directions",
    "accommodation",
    "transport",
    "dress_code",
    "gifts",
    "contact",
)


def get_guest_info(db: Session, principal: Principal, wedding_id: UUID) -> GuestInfo | None:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return db.get(GuestInfo, wedding_id)


def save_guest_info(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any], version: int
) -> GuestInfo:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    info = db.get(GuestInfo, wedding_id)
    if (info.version if info else 0) != version:
        raise _conflict()
    if info is None:
        info = GuestInfo(wedding_id=wedding_id)
        db.add(info)
    for key in (*INFO_FIELDS, "published", "theme", "accent"):
        value = data.get(key)
        setattr(info, key, value.strip() or None if isinstance(value, str) else value)
    _record(db, "user", principal.user.id, wedding_id, "guest_info", wedding_id, "update")
    _commit(db)
    return info


# --- link RSVP e-mailem ------------------------------------------------------------------------


def _pending_households(db: Session, wedding_id: UUID) -> list[Household]:
    """Rodziny, w których ktoś jeszcze nie odpowiedział na żadne z wydarzeń."""
    households = list(
        db.scalars(
            select(Household).where(Household.wedding_id == wedding_id).order_by(Household.name)
        )
    )
    guests = {h.id: household_guests(db, h.id) for h in households}
    att = attendance_map(db, [g.id for gs in guests.values() for g in gs])
    return [
        h
        for h in households
        if any("pending" in att[g.id].values() or not att[g.id] for g in guests[h.id])
    ]


def rsvp_emails(
    db: Session, principal: Principal, wedding_id: UUID, *, dry_run: bool, include_with_link: bool
) -> dict[str, Any]:
    """Wysyłka linków RSVP e-mailem do rodzin bez odpowiedzi (podgląd albo wysyłka)."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    wedding = db.get_one(Wedding, wedding_id)
    pending = _pending_households(db, wedding_id)
    links = active_links(db, [h.id for h in pending])
    with_email = [h for h in pending if h.contact_email]
    targets = [h for h in with_email if include_with_link or h.id not in links]
    result = {
        "dry_run": dry_run,
        "to_send": [
            {
                "household_id": h.id,
                "name": h.name,
                "email": h.contact_email,
                "has_active_link": h.id in links,
                "last_emailed_at": h.rsvp_emailed_at,
            }
            for h in targets
        ],
        "with_link_skipped": sum(1 for h in with_email if h.id in links and not include_with_link),
        "without_email": len(pending) - len(with_email),
    }
    if dry_run or not targets:
        return result
    base = get_settings().public_app_url
    for h in targets:
        db.execute(
            update(RsvpToken)
            .where(RsvpToken.household_id == h.id, RsvpToken.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
        token, token_hash = new_token()
        expires = _rsvp_expiry(db, wedding, h)
        db.add(RsvpToken(household_id=h.id, token_hash=token_hash, expires_at=expires))
        queue_mail(db, h.contact_email or "", rsvp_mail(wedding.name, h, f"{base}/rsvp/{token}"))
        h.rsvp_emailed_at = utcnow()
        _record(db, "user", principal.user.id, wedding_id, "rsvp_link", h.id, "email")
    db.commit()
    return result
