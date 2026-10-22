"""Plan przygotowań: fryzjer i makijaż liczone wstecz od godziny, na którą wszyscy mają być gotowi.

Kolejność na liście to kolejność siadania na fotel — ostatnia osoba (zwykle Panna Młoda) kończy
tuż przed godziną „gotowi”. Każda osoba ma najpierw fryzurę, potem makijaż; nie może siedzieć
u dwóch osób naraz, a każda fryzjerka i makijażystka obsługuje jedną osobę w danej chwili.
Liczymy zachłannie od końca (bez optymalizacji): wynik to propozycja do rozmowy z fryzjerką
i makijażystką, którą para może poprawić kolejnością lub liczbą osób obsługujących.
"""

from dataclasses import dataclass
from datetime import time
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.errors import Conflict, NotFound
from app.modules.audit import service as audit
from app.modules.identity.service import Principal
from app.modules.schedule.models import PrepPerson, PrepPlan
from app.modules.workspace.permissions import Action, authorize

PREP_CATEGORIES = ("hairdresser", "makeup")
DAY = 24 * 60


@dataclass(frozen=True)
class Slot:
    start: int  # minuty od północy (mogą być ujemne: dzień wcześniej — tylko ostrzegamy)
    end: int
    artist: int  # numer osoby obsługującej (od 1)


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def hhmm(m: int) -> str:
    m %= DAY
    return f"{m // 60:02d}:{m % 60:02d}"


def compute(
    ready_by: int, hair_artists: int, makeup_artists: int, people: list[tuple[int, int]]
) -> list[tuple[Slot | None, Slot | None]]:
    """Dla każdej osoby (minuty fryzury, minuty makijażu) → (fryzura, makijaż) lub None."""
    hair_free = [ready_by] * hair_artists
    makeup_free = [ready_by] * makeup_artists
    out: list[tuple[Slot | None, Slot | None]] = [(None, None)] * len(people)
    for i in range(len(people) - 1, -1, -1):
        hair_min, makeup_min = people[i]
        person_end = ready_by
        makeup = hair = None
        if makeup_min and makeup_free:
            k = max(range(len(makeup_free)), key=lambda j: makeup_free[j])
            end = min(makeup_free[k], person_end)
            makeup = Slot(end - makeup_min, end, k + 1)
            makeup_free[k] = person_end = makeup.start
        if hair_min and hair_free:
            k = max(range(len(hair_free)), key=lambda j: hair_free[j])
            end = min(hair_free[k], person_end)
            hair = Slot(end - hair_min, end, k + 1)
            hair_free[k] = hair.start
        out[i] = (hair, makeup)
    return out


def _plan(db: Session, wedding_id: UUID) -> PrepPlan | None:
    return db.get(PrepPlan, wedding_id)


def _people(db: Session, wedding_id: UUID) -> list[PrepPerson]:
    return list(
        db.scalars(
            select(PrepPerson)
            .where(PrepPerson.wedding_id == wedding_id)
            .order_by(PrepPerson.position, PrepPerson.created_at)
        )
    )


def _slot_out(s: Slot | None) -> dict[str, Any] | None:
    return None if s is None else {"start": hhmm(s.start), "end": hhmm(s.end), "artist": s.artist}


def schedule(db: Session, wedding_id: UUID) -> dict[str, Any]:
    """Wynik bez autoryzacji (używa go też link fryzjerki i makijażystki)."""
    plan = _plan(db, wedding_id)
    ready_by = plan.ready_by if plan else time(13, 0)
    hair_n = plan.hair_artists if plan else 1
    makeup_n = plan.makeup_artists if plan else 1
    people = _people(db, wedding_id)
    slots = compute(
        _minutes(ready_by), hair_n, makeup_n, [(p.hair_minutes, p.makeup_minutes) for p in people]
    )
    starts = [s.start for pair in slots for s in pair if s]
    hair_starts = [h.start for h, _ in slots if h]
    makeup_starts = [m.start for _, m in slots if m]
    warnings = []
    if starts and min(starts) < 0:
        warnings.append(
            "Przygotowania musiałyby zacząć się przed północą — dodajcie osobę obsługującą "
            "albo skróćcie czas."
        )
    elif starts and min(starts) < 6 * 60:
        warnings.append(
            "Start przed 6:00 — rozważcie drugą fryzjerkę lub makijażystkę albo późniejszą godzinę."
        )
    if any(p.hair_minutes for p in people) and not hair_n:
        warnings.append("Są fryzury, ale nie ma fryzjerki (liczba osób obsługujących to 0).")
    if any(p.makeup_minutes for p in people) and not makeup_n:
        warnings.append("Są makijaże, ale nie ma makijażystki (liczba osób obsługujących to 0).")
    return {
        "ready_by": hhmm(_minutes(ready_by)),
        "hair_artists": hair_n,
        "makeup_artists": makeup_n,
        "version": plan.version if plan else 0,
        "start": hhmm(min(starts)) if starts else None,
        "hair_start": hhmm(min(hair_starts)) if hair_starts else None,
        "makeup_start": hhmm(min(makeup_starts)) if makeup_starts else None,
        "people": [
            {
                "id": p.id,
                "name": p.name,
                "hair_minutes": p.hair_minutes,
                "makeup_minutes": p.makeup_minutes,
                "version": p.version,
                "hair": _slot_out(h),
                "makeup": _slot_out(m),
            }
            for p, (h, m) in zip(people, slots, strict=True)
        ],
        "warnings": warnings,
    }


def overview(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.DAY_READ)
    return schedule(db, wedding_id)


def _record(
    db: Session, principal: Principal, wedding_id: UUID, entity_id: UUID, action: str
) -> None:
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="prep",
        entity_id=entity_id,
        wedding_id=wedding_id,
        action=action,
    )


def save_plan(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any], version: int
) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    plan = _plan(db, wedding_id)
    if plan is None:
        if version != 0:
            raise Conflict("Plan zmienił się w międzyczasie.", code="conflict.version_mismatch")
        plan = PrepPlan(wedding_id=wedding_id)
        db.add(plan)
    elif plan.version != version:
        raise Conflict("Plan zmienił się w międzyczasie.", code="conflict.version_mismatch")
    for k, v in data.items():
        if v is not None:
            setattr(plan, k, v)
    _record(db, principal, wedding_id, wedding_id, "plan")
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise Conflict(
            "Plan zmienił się w międzyczasie.", code="conflict.version_mismatch"
        ) from exc


def _person(db: Session, wedding_id: UUID, person_id: UUID) -> PrepPerson:
    p = db.get(PrepPerson, person_id)
    if p is None or p.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono osoby.", code="prep.not_found")
    return p


def add_person(db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    last = db.scalar(
        select(func.max(PrepPerson.position)).where(PrepPerson.wedding_id == wedding_id)
    )
    p = PrepPerson(wedding_id=wedding_id, position=0 if last is None else last + 1, **data)
    db.add(p)
    db.flush()
    _record(db, principal, wedding_id, p.id, "create")
    db.commit()


def update_person(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    person_id: UUID,
    data: dict[str, Any],
    version: int,
) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    p = _person(db, wedding_id, person_id)
    if p.version != version:
        raise Conflict("Osoba zmieniła się w międzyczasie.", code="conflict.version_mismatch")
    for k, v in data.items():
        if v is not None:
            setattr(p, k, v)
    _record(db, principal, wedding_id, p.id, "update")
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise Conflict(
            "Osoba zmieniła się w międzyczasie.", code="conflict.version_mismatch"
        ) from exc


def delete_person(db: Session, principal: Principal, wedding_id: UUID, person_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    db.delete(_person(db, wedding_id, person_id))
    _record(db, principal, wedding_id, person_id, "delete")
    db.commit()


def move_person(
    db: Session, principal: Principal, wedding_id: UUID, person_id: UUID, up: bool
) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    people = _people(db, wedding_id)
    i = next((k for k, p in enumerate(people) if p.id == person_id), None)
    if i is None:
        raise NotFound("Nie znaleziono osoby.", code="prep.not_found")
    j = i - 1 if up else i + 1
    if 0 <= j < len(people):
        people[i], people[j] = people[j], people[i]
        for pos, p in enumerate(people):
            p.position = pos
        _record(db, principal, wedding_id, person_id, "move")
    db.commit()


def vendor_list(db: Session, wedding_id: UUID, category: str) -> list[dict[str, Any]]:
    """Fryzjerka widzi tylko fryzury, makijażystka tylko makijaże: kto, godziny, stanowisko."""
    if category not in PREP_CATEGORIES:
        return []
    key = "hair" if category == "hairdresser" else "makeup"
    data = schedule(db, wedding_id)
    rows = [{"name": p["name"], **p[key]} for p in data["people"] if p[key] is not None]
    return sorted(rows, key=lambda r: (r["start"], r["artist"]))
