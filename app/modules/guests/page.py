"""Strona gościa — dodatki: „Gdzie siedzimy”, komunikat dla gości i księga życzeń.

- Stół: każde zaproszenie widzi tylko swój stół i miejsca (bez nazwisk innych gości),
  i tylko gdy para to włączy (plan stołów często zmienia się do ostatniej chwili).
- Komunikat: baner na stronie gościa (np. „zmiana godziny ceremonii”). E-mail z komunikatem
  idzie do rodzin z adresem, bez linku do strony — nowy link unieważniłby stare (QR na
  zaproszeniach). Ten sam komunikat wysyłamy raz.
- Życzenia: gość pisze życzenia na swojej stronie (do 5 na zaproszenie). Para czyta,
  może ukryć lub usunąć. Życzenia zostają jako pamiątka (po usunięciu zaproszenia bez powiązania).
"""

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import mail_templates
from app.core.db import utcnow
from app.core.email import queue_mail
from app.core.errors import Conflict, NotFound
from app.modules.audit import service as audit
from app.modules.guests.models import Guest, GuestInfo, GuestWish, Household
from app.modules.identity.service import Principal
from app.modules.workspace.models import Wedding
from app.modules.workspace.permissions import Action, authorize

WISHES_LIMIT = 5


def _info(db: Session, wedding_id: UUID) -> GuestInfo:
    info = db.get(GuestInfo, wedding_id)
    if info is None:
        info = GuestInfo(wedding_id=wedding_id)
        db.add(info)
        db.flush()
    return info


def _record(
    db: Session,
    wedding_id: UUID,
    entity_type: str,
    entity_id: UUID,
    action: str,
    principal: Principal | None = None,
) -> None:
    audit.record(
        db,
        actor_type="user" if principal else "guest",
        actor_id=principal.user.id if principal else None,
        entity_type=entity_type,
        entity_id=entity_id,
        wedding_id=wedding_id,
        action=action,
    )


def _with_email(db: Session, wedding_id: UUID) -> list[Household]:
    return list(
        db.scalars(
            select(Household).where(
                Household.wedding_id == wedding_id, Household.contact_email.is_not(None)
            )
        )
    )


def settings(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    info = db.get(GuestInfo, wedding_id)
    households = db.scalar(
        select(func.count()).select_from(Household).where(Household.wedding_id == wedding_id)
    )
    from app.modules.logistics.models import TransportRun  # transport czyta gości

    runs_shown = db.scalar(
        select(func.count())
        .select_from(TransportRun)
        .where(TransportRun.wedding_id == wedding_id, TransportRun.show_to_guests.is_(True))
    )
    return {
        "info_published": bool(info and info.published),
        "show_menu": bool(info and info.show_menu),
        "song_requests": bool(info and info.song_requests),
        "gifts_enabled": bool(info and info.gifts_enabled),
        "runs_shown": runs_shown or 0,
        "show_tables": bool(info and info.show_tables),
        "wishes_enabled": bool(info and info.wishes_enabled),
        "announcement": info.announcement if info else None,
        "announcement_at": info.announcement_at if info else None,
        "announcement_emailed_at": info.announcement_emailed_at if info else None,
        "households_with_email": len(_with_email(db, wedding_id)),
        "households": households or 0,
    }


def save_settings(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]
) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    info = _info(db, wedding_id)
    for k in ("show_tables", "wishes_enabled", "gifts_enabled"):
        if data.get(k) is not None:
            setattr(info, k, data[k])
    _record(db, wedding_id, "guest_page", wedding_id, "settings", principal)
    db.commit()
    return settings(db, principal, wedding_id)


def save_announcement(
    db: Session, principal: Principal, wedding_id: UUID, text: str | None
) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    info = _info(db, wedding_id)
    text = (text or "").strip() or None
    if text != info.announcement:
        info.announcement = text
        info.announcement_at = utcnow() if text else None
        info.announcement_emailed_at = None
    _record(db, wedding_id, "guest_page", wedding_id, "announcement", principal)
    db.commit()
    return settings(db, principal, wedding_id)


def _announcement_mail(wedding: Wedding, h: Household, text: str) -> mail_templates.Email:
    if h.language == "en":
        return mail_templates.build(
            f"{wedding.name}: a message from the couple",
            heading=wedding.name,
            paragraphs=[text, "Details are on the page from your invitation."],
            note="This message was sent by the Nasz dzień app on behalf of the couple.",
            settings_link=False,
            lang="en",
        )
    return mail_templates.build(
        f"{wedding.name}: wiadomość od pary młodej",
        heading=wedding.name,
        paragraphs=[text, "Szczegóły znajdziecie na stronie z Waszego zaproszenia."],
        note="Wiadomość wysłała aplikacja Nasz dzień na prośbę pary młodej.",
        settings_link=False,
    )


def email_announcement(
    db: Session, principal: Principal, wedding_id: UUID, *, dry_run: bool
) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    info = db.get(GuestInfo, wedding_id)
    if not (info and info.announcement):
        raise Conflict("Najpierw napiszcie komunikat.", code="announcement.empty")
    targets = _with_email(db, wedding_id)
    if info.announcement_emailed_at is not None:
        raise Conflict(
            "Ten komunikat został już wysłany e-mailem.", code="announcement.already_sent"
        )
    if not dry_run:
        wedding = db.get_one(Wedding, wedding_id)
        for h in targets:
            queue_mail(db, h.contact_email or "", _announcement_mail(wedding, h, info.announcement))
        info.announcement_emailed_at = utcnow()
        _record(db, wedding_id, "guest_page", wedding_id, "announcement_email", principal)
        db.commit()
    return {"dry_run": dry_run, "recipients": len(targets)}


# --- dla strony gościa (wywołuje widok RSVP po sprawdzeniu linku) -----------------------------


def guest_extras(db: Session, wedding_id: UUID, household_id: UUID | None) -> dict[str, Any]:
    from app.modules.seating.models import SeatAssignment, SeatingTable  # stoły czytają gości

    info = db.get(GuestInfo, wedding_id)
    tables: list[dict[str, Any]] | None = None
    if info and info.show_tables and household_id:
        rows = db.execute(
            select(Guest.first_name, SeatingTable.name, SeatAssignment.seat_number)
            .join(SeatAssignment, SeatAssignment.guest_id == Guest.id)
            .join(SeatingTable, SeatingTable.id == SeatAssignment.table_id)
            .where(Guest.household_id == household_id)
            .order_by(SeatingTable.sort_order, Guest.first_name)
        )
        tables = [
            {"first_name": first, "table": table, "seat_number": seat}
            for first, table, seat in rows
        ]
    wishes = None
    if info and info.wishes_enabled:
        mine = (
            list(
                db.scalars(
                    select(GuestWish)
                    .where(GuestWish.household_id == household_id)
                    .order_by(GuestWish.created_at)
                )
            )
            if household_id
            else []
        )
        wishes = {
            "limit": WISHES_LIMIT,
            "mine": [{"author": w.author, "text": w.text} for w in mine],
        }
    announcement = (
        {"text": info.announcement, "updated_at": info.announcement_at}
        if info and info.announcement
        else None
    )
    from app.modules.guests import gifts

    return {
        "tables": tables,
        "wishes": wishes,
        "announcement": announcement,
        "gifts": gifts.guest_list(db, wedding_id, household_id),
    }


def add_wish(db: Session, wedding_id: UUID, household_id: UUID, data: dict[str, Any]) -> None:
    info = db.get(GuestInfo, wedding_id)
    if not (info and info.wishes_enabled):
        raise NotFound("Para nie zbiera życzeń na tej stronie.", code="rsvp.wishes_disabled")
    count = db.scalar(
        select(func.count()).select_from(GuestWish).where(GuestWish.household_id == household_id)
    )
    if (count or 0) >= WISHES_LIMIT:
        raise Conflict("Można zostawić najwyżej 5 wpisów.", code="rsvp.wishes_limit")
    w = GuestWish(
        wedding_id=wedding_id,
        household_id=household_id,
        author=data["author"].strip(),
        text=data["text"].strip(),
    )
    db.add(w)
    db.flush()
    _record(db, wedding_id, "guest_wish", w.id, "create")
    db.commit()


# --- księga życzeń: para ------------------------------------------------------------------------


def wishes(db: Session, principal: Principal, wedding_id: UUID) -> list[dict[str, Any]]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    rows = db.execute(
        select(GuestWish, Household.name)
        .outerjoin(Household, Household.id == GuestWish.household_id)
        .where(GuestWish.wedding_id == wedding_id)
        .order_by(GuestWish.created_at)
    )
    return [
        {
            "id": w.id,
            "author": w.author,
            "text": w.text,
            "hidden": w.hidden,
            "household_name": name,
            "created_at": w.created_at,
        }
        for w, name in rows
    ]


def _wish(db: Session, wedding_id: UUID, wish_id: UUID) -> GuestWish:
    w = db.get(GuestWish, wish_id)
    if w is None or w.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono wpisu.", code="guest_wish.not_found")
    return w


def set_hidden(
    db: Session, principal: Principal, wedding_id: UUID, wish_id: UUID, hidden: bool
) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    w = _wish(db, wedding_id, wish_id)
    w.hidden = hidden
    _record(db, wedding_id, "guest_wish", w.id, "hide" if hidden else "show", principal)
    db.commit()


def delete_wish(db: Session, principal: Principal, wedding_id: UUID, wish_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    db.delete(_wish(db, wedding_id, wish_id))
    _record(db, wedding_id, "guest_wish", wish_id, "delete", principal)
    db.commit()
