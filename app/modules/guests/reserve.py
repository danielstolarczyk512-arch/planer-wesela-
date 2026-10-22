"""Lista rezerwowa: kolejka osób do zaproszenia, gdy ktoś odmówi („druga fala” zaproszeń)."""

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import Conflict, NotFound
from app.core.ids import uuid7
from app.modules.guests.models import Guest, Household, ReserveEntry
from app.modules.guests.service import _commit, _conflict, _record
from app.modules.identity.service import Principal
from app.modules.workspace.permissions import Action, authorize


def _entry(db: Session, wedding_id: UUID, entry_id: UUID) -> ReserveEntry:
    e = db.get(ReserveEntry, entry_id)
    if e is None or e.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono osoby na liście rezerwowej.", code="reserve.not_found")
    return e


def _ordered(db: Session, wedding_id: UUID) -> list[ReserveEntry]:
    return list(
        db.scalars(
            select(ReserveEntry)
            .where(ReserveEntry.wedding_id == wedding_id)
            .order_by(ReserveEntry.position, ReserveEntry.created_at, ReserveEntry.id)
        )
    )


def list_entries(db: Session, principal: Principal, wedding_id: UUID) -> list[ReserveEntry]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return _ordered(db, wedding_id)


def create_entry(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]
) -> ReserveEntry:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    last = db.scalar(
        select(func.max(ReserveEntry.position)).where(ReserveEntry.wedding_id == wedding_id)
    )
    e = ReserveEntry(wedding_id=wedding_id, position=0 if last is None else last + 1, **data)
    db.add(e)
    db.flush()
    _record(db, "user", principal.user.id, wedding_id, "reserve_entry", e.id, "create")
    db.commit()
    return e


def update_entry(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    entry_id: UUID,
    data: dict[str, Any],
    version: int,
) -> ReserveEntry:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    e = _entry(db, wedding_id, entry_id)
    if e.version != version:
        raise _conflict()
    position = data.pop("position", None)
    for k, v in data.items():
        if v is not None or k == "note":
            setattr(e, k, v)
    if position is not None:
        # Przesunięcie w kolejce: wpis trafia na wskazane miejsce, reszta jest przenumerowana.
        rest = [x for x in _ordered(db, wedding_id) if x.id != e.id]
        rest.insert(min(position, len(rest)), e)
        for i, x in enumerate(rest):
            if x.position != i:
                x.position = i
    _record(
        db,
        "user",
        principal.user.id,
        wedding_id,
        "reserve_entry",
        e.id,
        "update",
        {"fields": sorted([*data, *(["position"] if position is not None else [])])},
    )
    _commit(db)
    return e


def delete_entry(db: Session, principal: Principal, wedding_id: UUID, entry_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    e = _entry(db, wedding_id, entry_id)
    db.delete(e)
    _record(db, "user", principal.user.id, wedding_id, "reserve_entry", entry_id, "delete")
    db.commit()


def invite(
    db: Session, principal: Principal, wedding_id: UUID, entry_id: UUID, data: dict[str, Any]
) -> tuple[ReserveEntry, UUID]:
    """Zaproszenie z listy rezerwowej: powstaje zwykłe gospodarstwo z gośćmi (jedna transakcja)."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    e = _entry(db, wedding_id, entry_id)
    if e.status != "waiting":
        raise Conflict("Ta osoba jest już zaproszona.", code="reserve.already_invited")
    h = Household(
        wedding_id=wedding_id,
        name=e.name,
        side=e.side,
        notes=e.note,
        rsvp_deadline=data.get("rsvp_deadline"),
    )
    db.add(h)
    db.flush()
    for g in data["guests"]:
        db.add(Guest(id=uuid7(), wedding_id=wedding_id, household_id=h.id, **g))
    e.status, e.household_id, e.invited_at = "invited", h.id, utcnow()
    db.flush()
    _record(db, "user", principal.user.id, wedding_id, "household", h.id, "create")
    _record(db, "user", principal.user.id, wedding_id, "reserve_entry", e.id, "invite")
    _commit(db)
    return e, h.id
