"""Wręczanie zaproszeń osobiście: objazdy po miejscowościach, kto wręcza, odhaczanie.

W Polsce zaproszenia rodzinie wręcza się zwykle osobiście. To dziesiątki wizyt w kilku
miejscowościach, rozłożone na weekendy. Zapisujemy tylko miejscowość (bez adresu).
"""

import math
from collections import defaultdict
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import NotFound
from app.modules.guests.models import Guest, Household, ReserveEntry
from app.modules.guests.service import _record
from app.modules.identity.service import Principal
from app.modules.workspace.permissions import Action, authorize

INVITATIONS_TASK = "invitations_send"
SPARE_SHARE = 0.10  # zapas na pomyłki, dopisanych gości i pamiątkę
SPARE_MIN = 3


def print_order(households: list[Household], reserve_waiting: int) -> dict[str, int]:
    """Ile zaproszeń zamówić w drukarni: jedno na zaproszenie (rodzinę), bez wysyłanych online.

    Zaproszenia bez ustalonego sposobu liczymy jako papierowe. Do zapasu dochodzą osoby z listy
    rezerwowej, które jeszcze czekają (każda pozycja to jedno zaproszenie).
    """
    printed = sum(1 for h in households if h.delivery_method != "online")
    spare = max(SPARE_MIN, math.ceil(printed * SPARE_SHARE)) if printed else 0
    return {
        "printed": printed,
        "spare": spare,
        "reserve": reserve_waiting,
        "total": printed + spare + reserve_waiting,
    }


def weekends_between(start: date, end: date) -> int:
    """Ile sobót jest od `start` do `end` włącznie (weekendy na objazdy)."""
    if end < start:
        return 0
    first_saturday = start + timedelta(days=(5 - start.weekday()) % 7)
    return 0 if first_saturday > end else (end - first_saturday).days // 7 + 1


def _place_key(place: str | None) -> str:
    return " ".join((place or "").split()).casefold()


def _deadline(db: Session, wedding_id: UUID, households: list[Household]) -> date | None:
    from app.modules.planner.models import Task  # plan zależy od wesela, goście tylko czytają

    task_due = db.scalar(
        select(Task.due_date).where(
            Task.wedding_id == wedding_id,
            Task.template_code == INVITATIONS_TASK,
            Task.status.in_(("todo", "in_progress")),
        )
    )
    if task_due:
        return task_due
    deadlines = [h.rsvp_deadline for h in households if h.rsvp_deadline]
    return min(deadlines) if deadlines else None


def overview(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    households = list(
        db.scalars(
            select(Household).where(Household.wedding_id == wedding_id).order_by(Household.name)
        )
    )
    counts = dict(
        db.execute(
            select(Guest.household_id, func.count())
            .where(Guest.wedding_id == wedding_id)
            .group_by(Guest.household_id)
        ).all()
    )
    by_method: dict[str, int] = defaultdict(int)
    groups: dict[str, list[Household]] = defaultdict(list)
    names: dict[str, str | None] = {}
    for h in households:
        by_method[h.delivery_method or "none"] += 1
        if h.delivery_method == "in_person":
            key = _place_key(h.delivery_place)
            groups[key].append(h)
            names.setdefault(key, " ".join(h.delivery_place.split()) if h.delivery_place else None)
    in_person = [h for hs in groups.values() for h in hs]
    reserve_waiting = db.scalar(
        select(func.count())
        .select_from(ReserveEntry)
        .where(ReserveEntry.wedding_id == wedding_id, ReserveEntry.status == "waiting")
    )
    delivered = sum(1 for h in in_person if h.invitation_status == "delivered")
    deadline = _deadline(db, wedding_id, in_person)
    out_groups: list[dict[str, Any]] = []
    for key, hs in groups.items():
        remaining = sum(1 for h in hs if h.invitation_status != "delivered")
        out_groups.append(
            {
                "place": names[key],
                "remaining": remaining,
                "planned_on": sorted({h.delivery_planned_on for h in hs if h.delivery_planned_on}),
                "households": [
                    {
                        "id": h.id,
                        "name": h.name,
                        "side": h.side,
                        "guests": counts.get(h.id, 0),
                        "delivery_by": h.delivery_by,
                        "delivery_planned_on": h.delivery_planned_on,
                        "delivered_on": h.delivered_on,
                        "invitation_status": h.invitation_status,
                        "version": h.version,
                    }
                    for h in hs
                ],
            }
        )
    # Najpierw miejscowości z największą liczbą niewręczonych, „bez miejscowości” na końcu.
    out_groups.sort(key=lambda g: (g["place"] is None, -g["remaining"], g["place"] or ""))
    return {
        "in_person_total": len(in_person),
        "in_person_delivered": delivered,
        "by_method": dict(by_method),
        "deadline": deadline,
        "weekends_left": weekends_between(clock.today(), deadline) if deadline else None,
        "groups": out_groups,
        "print_order": print_order(households, reserve_waiting or 0),
    }


def _selected(db: Session, wedding_id: UUID, ids: list[UUID]) -> list[Household]:
    households = list(
        db.scalars(
            select(Household).where(Household.wedding_id == wedding_id, Household.id.in_(ids))
        )
    )
    if len(households) != len(set(ids)):
        raise NotFound("Nie znaleziono części zaproszeń.", code="household.not_found")
    return households


def plan(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]
) -> list[Household]:
    """Zaplanowanie objazdu: dzień i/lub kto wręcza dla wielu zaproszeń naraz."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    households = _selected(db, wedding_id, data["household_ids"])
    for h in households:
        if "planned_on" in data:
            h.delivery_planned_on = data["planned_on"]
        if data.get("delivery_by") is not None:
            h.delivery_by = data["delivery_by"] or None
        h.delivery_method = h.delivery_method or "in_person"
        _record(db, "user", principal.user.id, wedding_id, "household", h.id, "delivery_plan")
    db.commit()
    return households


def mark_delivered(
    db: Session, principal: Principal, wedding_id: UUID, ids: list[UUID], on: date | None
) -> list[Household]:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    households = _selected(db, wedding_id, ids)
    day = on or clock.today()
    for h in households:
        h.invitation_status, h.delivered_on = "delivered", day
        h.delivery_method = h.delivery_method or "in_person"
        _record(db, "user", principal.user.id, wedding_id, "household", h.id, "delivered")
    db.commit()
    return households
