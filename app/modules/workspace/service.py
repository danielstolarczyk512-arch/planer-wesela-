"""Logika przestrzeni wesela: wesela, wydarzenia, członkowie, zaproszenia."""

from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core import clock, mail_templates, ratelimit
from app.core.config import get_settings
from app.core.db import utcnow
from app.core.email import queue_mail
from app.core.errors import Conflict, Forbidden, NotFound, Unprocessable
from app.core.schemas import Money, decode_cursor, encode_cursor
from app.core.security import hash_token, new_token
from app.modules.audit import service as audit
from app.modules.identity.models import User
from app.modules.identity.service import Principal
from app.modules.workspace.models import Event, Wedding, WeddingInvitation, WeddingMember
from app.modules.workspace.permissions import Action, authorize

MAX_PENDING_INVITATIONS = 10


def _version_conflict() -> Conflict:
    return Conflict(
        "Dane zmieniły się w międzyczasie. Pobierz aktualną wersję i spróbuj ponownie.",
        code="conflict.version_mismatch",
    )


def month_to_date(value: str | None) -> date | None:
    if value is None:
        return None
    year, month = value.split("-")
    return date(int(year), int(month), 1)


def _wedding_values(data: dict[str, Any]) -> dict[str, Any]:
    """Mapowanie pól API → kolumny (pieniądze, planowany miesiąc)."""
    values = dict(data)
    if "planned_month" in values:
        values["planned_month"] = month_to_date(values["planned_month"])
    if "total_budget" in values:
        money = values.pop("total_budget")
        values["total_budget"] = money["amount"] if money else None
        if money:
            values["currency"] = money["currency"]
    return values


def wedding_to_dict(w: Wedding, role: str) -> dict[str, Any]:
    return {
        "id": w.id,
        "name": w.name,
        "wedding_date": w.wedding_date,
        "planned_month": w.planned_month.strftime("%Y-%m") if w.planned_month else None,
        "ceremony_type": w.ceremony_type,
        "city": w.city,
        "region": w.region,
        "guest_count_planned": w.guest_count_planned,
        # Koordynator dnia i sponsor nie widzą budżetu.
        "total_budget": (
            Money(amount=w.total_budget, currency="PLN")
            if w.total_budget is not None and role not in ("coordinator", "sponsor")
            else None
        ),
        "style": w.style,
        "colors": w.colors,
        "priorities": w.priorities,
        "timezone": w.timezone,
        "status": w.status,
        "my_role": role,
        "version": w.version,
        "created_at": w.created_at,
        "updated_at": w.updated_at,
    }


# --- wesela --------------------------------------------------------------------------


def create_wedding(db: Session, principal: Principal, data: dict[str, Any]) -> Wedding:
    wedding = Wedding(**_wedding_values(data))
    db.add(wedding)
    db.flush()
    db.add(WeddingMember(wedding_id=wedding.id, user_id=principal.user.id, role="owner"))
    # Import lokalny: planer i budżet zależą od workspace, nie odwrotnie.
    from app.modules.budget import service as budget
    from app.modules.planner import service as planner

    planner.generate_for_wedding(db, wedding)
    budget.create_default_categories(db, wedding)
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="wedding",
        entity_id=wedding.id,
        wedding_id=wedding.id,
        action="create",
    )
    db.commit()
    return wedding


def list_weddings(
    db: Session, principal: Principal, *, limit: int, cursor: str | None
) -> tuple[list[tuple[Wedding, str]], str | None]:
    stmt = (
        select(Wedding, WeddingMember.role)
        .join(WeddingMember, WeddingMember.wedding_id == Wedding.id)
        .where(WeddingMember.user_id == principal.user.id)
        .order_by(Wedding.id)
        .limit(limit + 1)
    )
    if cursor:
        stmt = stmt.where(Wedding.id > decode_cursor(cursor))
    rows = [(w, role) for w, role in db.execute(stmt).all()]
    next_cursor = encode_cursor(rows[limit - 1][0].id) if len(rows) > limit else None
    return rows[:limit], next_cursor


def get_wedding(db: Session, principal: Principal, wedding_id: UUID) -> tuple[Wedding, str]:
    member = authorize(db, principal.user.id, wedding_id, Action.BASIC)
    return db.get_one(Wedding, wedding_id), member.role


def update_wedding(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any], version: int
) -> tuple[Wedding, str]:
    member = authorize(db, principal.user.id, wedding_id, Action.WRITE)
    wedding = db.get_one(Wedding, wedding_id)
    if wedding.version != version:
        raise _version_conflict()
    values = _wedding_values(data)
    if values.get("wedding_date") is not None:
        values["planned_month"] = None  # konkretna data zastępuje planowany miesiąc
    from app.modules.planner import service as planner

    old_anchor = planner.wedding_anchor(wedding)
    before = {k: getattr(wedding, k) for k in values}
    for key, value in values.items():
        if key in ("colors", "priorities") and value is None:
            value = []
        setattr(wedding, key, value)
    try:
        planner.on_anchor_change(db, wedding, old_anchor)
    except Conflict:
        db.rollback()
        raise
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="wedding",
        entity_id=wedding.id,
        wedding_id=wedding.id,
        action="update",
        changes=audit.diff(before, values),
    )
    try:
        db.commit()
    except StaleDataError as exc:  # równoległa zmiana między odczytem a zapisem
        db.rollback()
        raise _version_conflict() from exc
    return wedding, member.role


def _delete_wedding_row(db: Session, wedding: Wedding) -> None:
    """Usunięcie wesela (kaskada w bazie) + zlecenie usunięcia plików przez workera."""
    from app.modules.documents import service as documents

    documents.on_wedding_deleted(db, wedding.id)
    db.delete(wedding)


def delete_wedding(db: Session, principal: Principal, wedding_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.DELETE)
    wedding = db.get_one(Wedding, wedding_id)
    _delete_wedding_row(db, wedding)
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="wedding",
        entity_id=wedding_id,
        wedding_id=wedding_id,
        action="delete",
    )
    db.commit()


# --- wydarzenia ------------------------------------------------------------------------


def _get_event(db: Session, wedding_id: UUID, event_id: UUID) -> Event:
    event = db.get(Event, event_id)
    if event is None or event.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono wydarzenia.", code="event.not_found")
    return event


def list_events(db: Session, principal: Principal, wedding_id: UUID) -> list[Event]:
    authorize(db, principal.user.id, wedding_id, Action.DAY_READ)
    return list(
        db.scalars(
            select(Event)
            .where(Event.wedding_id == wedding_id)
            .order_by(Event.starts_at.asc().nulls_last(), Event.id)
        )
    )


def create_event(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]
) -> Event:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    event = Event(wedding_id=wedding_id, **data)
    db.add(event)
    db.flush()
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="event",
        entity_id=event.id,
        wedding_id=wedding_id,
        action="create",
    )
    db.commit()
    return event


def get_event(db: Session, principal: Principal, wedding_id: UUID, event_id: UUID) -> Event:
    authorize(db, principal.user.id, wedding_id, Action.DAY_READ)
    return _get_event(db, wedding_id, event_id)


def update_event(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    event_id: UUID,
    data: dict[str, Any],
    version: int,
) -> Event:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    event = _get_event(db, wedding_id, event_id)
    if event.version != version:
        raise _version_conflict()
    before = {k: getattr(event, k) for k in data}
    for key, value in data.items():
        if key in ("kind", "name") and value is None:
            continue
        setattr(event, key, value)
    if event.starts_at and event.ends_at and event.ends_at <= event.starts_at:
        db.rollback()
        raise Unprocessable(
            "Koniec wydarzenia musi być po jego rozpoczęciu.", code="event.invalid_time_range"
        )
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="event",
        entity_id=event.id,
        wedding_id=wedding_id,
        action="update",
        changes=audit.diff(before, data),
    )
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise _version_conflict() from exc
    return event


def delete_event(db: Session, principal: Principal, wedding_id: UUID, event_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    event = _get_event(db, wedding_id, event_id)
    db.delete(event)
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="event",
        entity_id=event_id,
        wedding_id=wedding_id,
        action="delete",
    )
    db.commit()


# --- członkowie ------------------------------------------------------------------------


def _owner_count(db: Session, wedding_id: UUID) -> int:
    return (
        db.scalar(
            select(func.count()).where(
                WeddingMember.wedding_id == wedding_id, WeddingMember.role == "owner"
            )
        )
        or 0
    )


def list_members(
    db: Session, principal: Principal, wedding_id: UUID
) -> list[tuple[WeddingMember, User]]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    rows = db.execute(
        select(WeddingMember, User)
        .join(User, User.id == WeddingMember.user_id)
        .where(WeddingMember.wedding_id == wedding_id)
        .order_by(WeddingMember.joined_at)
    ).all()
    return [(m, u) for m, u in rows]


def _sponsor_funder(
    db: Session, wedding_id: UUID, role: str, funder_id: UUID | None
) -> UUID | None:
    """Rola sponsor wymaga źródła finansowania z tego wesela; inne role go nie mają."""
    if role != "sponsor":
        return None
    from app.modules.budget.models import Funder  # budżet zależy od wesela, nie odwrotnie

    funder = db.get(Funder, funder_id) if funder_id else None
    if funder is None or funder.wedding_id != wedding_id:
        raise Unprocessable(
            "Wybierz, czyj wkład ma widzieć sponsor (np. „Rodzice Panny Młodej”).",
            code="member.funder_required",
        )
    return funder.id


def change_member_role(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    user_id: UUID,
    role: str,
    *,
    funder_id: UUID | None = None,
) -> tuple[WeddingMember, User]:
    authorize(db, principal.user.id, wedding_id, Action.MANAGE_MEMBERS)
    funder = _sponsor_funder(db, wedding_id, role, funder_id)
    member = db.get(WeddingMember, (wedding_id, user_id))
    if member is None:
        raise NotFound("Nie znaleziono członka.", code="member.not_found")
    if member.role == "owner" and role != "owner" and _owner_count(db, wedding_id) <= 1:
        raise Conflict(
            "Wesele musi mieć co najmniej jednego właściciela.", code="wedding.last_owner"
        )
    old = member.role
    member.role, member.funder_id = role, funder
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="member",
        entity_id=user_id,
        wedding_id=wedding_id,
        action="change_role",
        changes={"role": [old, role]},
    )
    db.commit()
    return member, db.get_one(User, user_id)


def remove_member(db: Session, principal: Principal, wedding_id: UUID, user_id: UUID) -> None:
    leaving_self = user_id == principal.user.id
    if leaving_self:
        authorize(db, principal.user.id, wedding_id, Action.BASIC)
    else:
        authorize(db, principal.user.id, wedding_id, Action.MANAGE_MEMBERS)
    member = db.get(WeddingMember, (wedding_id, user_id))
    if member is None:
        raise NotFound("Nie znaleziono członka.", code="member.not_found")
    if member.role == "owner" and _owner_count(db, wedding_id) <= 1:
        raise Conflict(
            "Jesteś jedynym właścicielem. Przekaż rolę właściciela albo usuń wesele.",
            code="wedding.last_owner",
        )
    db.delete(member)
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="member",
        entity_id=user_id,
        wedding_id=wedding_id,
        action="leave" if leaving_self else "remove",
    )
    db.commit()


# --- zaproszenia ------------------------------------------------------------------------


def list_invitations(
    db: Session, principal: Principal, wedding_id: UUID
) -> list[WeddingInvitation]:
    authorize(db, principal.user.id, wedding_id, Action.MANAGE_MEMBERS)
    return list(
        db.scalars(
            select(WeddingInvitation)
            .where(WeddingInvitation.wedding_id == wedding_id)
            .order_by(WeddingInvitation.created_at.desc())
        )
    )


def create_invitation(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    *,
    email: str,
    role: str,
    funder_id: UUID | None = None,
) -> WeddingInvitation:
    authorize(db, principal.user.id, wedding_id, Action.MANAGE_MEMBERS)
    funder = _sponsor_funder(db, wedding_id, role, funder_id)
    if not principal.user.email_verified:
        raise Forbidden("Najpierw potwierdź swój adres e-mail.", code="auth.email_not_verified")
    ratelimit.hit(
        db, ratelimit.key_for("invite:user", str(principal.user.id)), 20, timedelta(days=1)
    )
    now = utcnow()
    pending = (
        db.scalar(
            select(func.count()).where(
                WeddingInvitation.wedding_id == wedding_id,
                WeddingInvitation.accepted_at.is_(None),
                WeddingInvitation.revoked_at.is_(None),
                WeddingInvitation.expires_at > now,
            )
        )
        or 0
    )
    if pending >= MAX_PENDING_INVITATIONS:
        raise Conflict("Zbyt wiele oczekujących zaproszeń.", code="invitation.too_many_pending")

    settings = get_settings()
    token, token_hash = new_token()
    invitation = WeddingInvitation(
        wedding_id=wedding_id,
        email=email,
        role=role,
        funder_id=funder,
        token_hash=token_hash,
        invited_by_user_id=principal.user.id,
        expires_at=now + timedelta(days=settings.invitation_ttl_days),
    )
    db.add(invitation)
    db.flush()
    inviter = principal.user.display_name or "Twój partner"
    queue_mail(
        db,
        email,
        mail_templates.build(
            "Zaproszenie do wspólnego planowania wesela",
            heading="Zaproszenie do wspólnego planowania wesela",
            paragraphs=[
                f"{inviter} zaprasza Cię do podglądu Waszego wkładu w wesele w Nasz dzień: "
                "ile obiecaliście, co już zapłacone i jakie płatności są przed Wami."
                if role == "sponsor"
                else f"{inviter} zaprasza Cię do wspólnego planowania wesela w Nasz dzień."
            ],
            action=(
                "Przyjmij zaproszenie",
                f"{settings.public_app_url}/invitations/accept?token={token}",
            ),
            note=f"Zaproszenie jest ważne {settings.invitation_ttl_days} dni. "
            "Aby je przyjąć, zaloguj się na konto z tym adresem e-mail.",
            settings_link=False,
        ),
    )
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="invitation",
        entity_id=invitation.id,
        wedding_id=wedding_id,
        action="create",
        changes={"role": [None, role]},
    )
    db.commit()
    return invitation


def revoke_invitation(
    db: Session, principal: Principal, wedding_id: UUID, invitation_id: UUID
) -> None:
    authorize(db, principal.user.id, wedding_id, Action.MANAGE_MEMBERS)
    invitation = db.get(WeddingInvitation, invitation_id)
    if (
        invitation is None
        or invitation.wedding_id != wedding_id
        or invitation.accepted_at is not None
        or invitation.revoked_at is not None
    ):
        raise NotFound("Nie znaleziono aktywnego zaproszenia.", code="invitation.not_found")
    invitation.revoked_at = utcnow()
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="invitation",
        entity_id=invitation_id,
        wedding_id=wedding_id,
        action="revoke",
    )
    db.commit()


def accept_invitation(db: Session, principal: Principal, token: str) -> tuple[Wedding, str]:
    invitation = db.scalars(
        select(WeddingInvitation)
        .where(WeddingInvitation.token_hash == hash_token(token))
        .with_for_update()
    ).first()
    user = principal.user
    # Jeden komunikat dla wszystkich przypadków, by nie ujawniać szczegółów zaproszenia.
    not_found = NotFound("Zaproszenie jest nieprawidłowe lub wygasło.", code="invitation.not_found")
    if (
        invitation is None
        or invitation.revoked_at is not None
        or invitation.accepted_at is not None
        or invitation.expires_at <= utcnow()
        or invitation.email != user.email
    ):
        raise not_found
    if not user.email_verified:
        raise Forbidden("Najpierw potwierdź swój adres e-mail.", code="auth.email_not_verified")

    member = db.get(WeddingMember, (invitation.wedding_id, user.id))
    if member is None:
        member = WeddingMember(
            wedding_id=invitation.wedding_id,
            user_id=user.id,
            role=invitation.role,
            funder_id=invitation.funder_id,
        )
        db.add(member)
    invitation.accepted_at = utcnow()
    invitation.accepted_by_user_id = user.id
    audit.record(
        db,
        actor_type="user",
        actor_id=user.id,
        entity_type="invitation",
        entity_id=invitation.id,
        wedding_id=invitation.wedding_id,
        action="accept",
    )
    db.commit()
    return db.get_one(Wedding, invitation.wedding_id), member.role


# --- integracja z modułem identity (RODO) ---------------------------------------------


def export_for_user(db: Session, user_id: UUID) -> list[dict[str, Any]]:
    rows = db.execute(
        select(Wedding, WeddingMember.role)
        .join(WeddingMember, WeddingMember.wedding_id == Wedding.id)
        .where(WeddingMember.user_id == user_id)
    ).all()
    return [
        {
            "id": str(w.id),
            "name": w.name,
            "role": role,
            "wedding_date": w.wedding_date.isoformat() if w.wedding_date else None,
            "note": "Pełny eksport danych wesela: POST /api/v1/weddings/{id}/export "
            "(planowany w Etapie 3).",
        }
        for w, role in rows
    ]


def _memberships(db: Session, user_id: UUID) -> list[WeddingMember]:
    return list(db.scalars(select(WeddingMember).where(WeddingMember.user_id == user_id)))


def _member_count(db: Session, wedding_id: UUID) -> int:
    return db.scalar(select(func.count()).where(WeddingMember.wedding_id == wedding_id)) or 0


def ensure_user_can_be_deleted(db: Session, user_id: UUID) -> None:
    """Jedyny właściciel wesela z innymi członkami musi najpierw przekazać rolę."""
    for m in _memberships(db, user_id):
        if (
            m.role == "owner"
            and _owner_count(db, m.wedding_id) <= 1
            and _member_count(db, m.wedding_id) > 1
        ):
            raise Conflict(
                "Jesteś jedynym właścicielem wesela, które współdzielisz. "
                "Przekaż rolę właściciela, zanim usuniesz konto.",
                code="account.sole_owner",
            )


def remove_user_everywhere(db: Session, user_id: UUID) -> None:
    for m in _memberships(db, user_id):
        if _member_count(db, m.wedding_id) <= 1:
            wedding = db.get(Wedding, m.wedding_id)
            if wedding is not None:
                _delete_wedding_row(db, wedding)
                audit.record(
                    db,
                    actor_type="system",
                    actor_id=None,
                    entity_type="wedding",
                    entity_id=m.wedding_id,
                    wedding_id=m.wedding_id,
                    action="delete_with_account",
                )
        else:
            db.delete(m)


def last_wedding_day(db: Session, wedding: Wedding) -> date | None:
    """Ostatni dzień wesela: data wesela albo koniec ostatniego wydarzenia (np. poprawin)."""
    last_event = db.scalar(
        select(func.max(func.coalesce(Event.ends_at, Event.starts_at))).where(
            Event.wedding_id == wedding.id
        )
    )
    candidates = [
        d
        for d in (
            wedding.wedding_date,
            last_event.astimezone(clock.WARSAW).date() if last_event else None,
        )
        if d is not None
    ]
    return max(candidates) if candidates else None


def access_end(last_day: date, days_after: int) -> datetime:
    """Koniec ważności linku bez logowania: `days_after` dni po ostatnim dniu wesela, 23:59."""
    return datetime.combine(
        last_day + timedelta(days=days_after), time(23, 59), tzinfo=clock.WARSAW
    )


def link_active(db: Session, wedding: Wedding, days_after: int) -> bool:
    """Link bez logowania działa do `days_after` dni po weselu; bez daty wesela — bez limitu."""
    last = last_wedding_day(db, wedding)
    return last is None or access_end(last, days_after) > utcnow()
