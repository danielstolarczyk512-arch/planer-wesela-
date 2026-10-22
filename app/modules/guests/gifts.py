"""Lista prezentów: pomysły pary, które goście rezerwują na swojej stronie.

- Rzecz (item) rezerwuje jedno zaproszenie; inni goście widzą tylko „zarezerwowane”.
- Fundusz (fund, np. podróż poślubna) to informacja — bez kwot i bez rezerwacji.
- Para widzi, kto zarezerwował (żeby podziękować); gość może zwolnić tylko swoją rezerwację.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.db import utcnow
from app.core.errors import Conflict, NotFound
from app.modules.audit import service as audit
from app.modules.guests.models import GiftIdea, GuestInfo, Household
from app.modules.identity.service import Principal
from app.modules.workspace.permissions import Action, authorize


def _record(
    db: Session, wedding_id: UUID, entity_id: UUID, action: str, principal: Principal | None = None
) -> None:
    audit.record(
        db,
        actor_type="user" if principal else "guest",
        actor_id=principal.user.id if principal else None,
        entity_type="gift_idea",
        entity_id=entity_id,
        wedding_id=wedding_id,
        action=action,
    )


def _ordered(db: Session, wedding_id: UUID) -> list[GiftIdea]:
    return list(
        db.scalars(
            select(GiftIdea)
            .where(GiftIdea.wedding_id == wedding_id)
            .order_by(GiftIdea.position, GiftIdea.created_at)
        )
    )


def overview(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    names = dict(
        db.execute(
            select(Household.id, Household.name).where(Household.wedding_id == wedding_id)
        ).all()
    )
    info = db.get(GuestInfo, wedding_id)
    ideas = _ordered(db, wedding_id)
    return {
        "enabled": bool(info and info.gifts_enabled),
        "ideas": [
            {
                "id": g.id,
                "kind": g.kind,
                "title": g.title,
                "note": g.note,
                "link": g.link,
                "reserved_by": names.get(g.reserved_by) if g.reserved_by else None,
                "reserved": g.reserved_by is not None,
                "version": g.version,
            }
            for g in ideas
        ],
        "reserved_count": sum(1 for g in ideas if g.reserved_by),
    }


def _idea(db: Session, wedding_id: UUID, idea_id: UUID) -> GiftIdea:
    g = db.get(GiftIdea, idea_id)
    if g is None or g.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono prezentu.", code="gift.not_found")
    return g


def create(db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    last = db.scalar(select(func.max(GiftIdea.position)).where(GiftIdea.wedding_id == wedding_id))
    g = GiftIdea(wedding_id=wedding_id, position=0 if last is None else last + 1, **data)
    db.add(g)
    db.flush()
    _record(db, wedding_id, g.id, "create", principal)
    db.commit()


def update_idea(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    idea_id: UUID,
    data: dict[str, Any],
    version: int,
) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    g = _idea(db, wedding_id, idea_id)
    if g.version != version:
        raise Conflict("Prezent zmienił się w międzyczasie.", code="conflict.version_mismatch")
    for k, v in data.items():
        if v is not None or k in ("note", "link"):
            setattr(g, k, v)
    if g.kind == "fund":
        g.reserved_by, g.reserved_at = None, None
    _record(db, wedding_id, g.id, "update", principal)
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise Conflict(
            "Prezent zmienił się w międzyczasie.", code="conflict.version_mismatch"
        ) from exc


def delete(db: Session, principal: Principal, wedding_id: UUID, idea_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    db.delete(_idea(db, wedding_id, idea_id))
    _record(db, wedding_id, idea_id, "delete", principal)
    db.commit()


# --- strona gościa ----------------------------------------------------------------------------


def guest_list(
    db: Session, wedding_id: UUID, household_id: UUID | None
) -> list[dict[str, Any]] | None:
    info = db.get(GuestInfo, wedding_id)
    if not (info and info.gifts_enabled):
        return None
    return [
        {
            "id": g.id,
            "kind": g.kind,
            "title": g.title,
            "note": g.note,
            "link": g.link,
            "reserved": g.reserved_by is not None,
            "mine": household_id is not None and g.reserved_by == household_id,
        }
        for g in _ordered(db, wedding_id)
    ]


def reserve(db: Session, wedding_id: UUID, household_id: UUID, idea_id: UUID, on: bool) -> None:
    info = db.get(GuestInfo, wedding_id)
    if not (info and info.gifts_enabled):
        raise NotFound("Para nie prowadzi listy prezentów.", code="rsvp.gifts_disabled")
    g = _idea(db, wedding_id, idea_id)
    if g.kind != "item":
        raise Conflict("Tego pomysłu nie rezerwuje się.", code="gift.not_reservable")
    if on:
        # Warunkowa aktualizacja: dwie rodziny naraz — wygrywa pierwsza, druga dostaje 409.
        done = db.execute(
            update(GiftIdea)
            .where(GiftIdea.id == g.id, GiftIdea.reserved_by.is_(None))
            .values(reserved_by=household_id, reserved_at=utcnow(), version=GiftIdea.version + 1)
            .returning(GiftIdea.id)
        ).first()
        if done is None and g.reserved_by != household_id:
            db.rollback()
            raise Conflict("Ktoś już wybrał ten prezent.", code="gift.taken")
    elif g.reserved_by == household_id:
        g.reserved_by, g.reserved_at = None, None
    _record(db, wedding_id, g.id, "reserve" if on else "unreserve")
    db.commit()
