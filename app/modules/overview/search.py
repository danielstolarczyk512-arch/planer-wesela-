"""Wyszukiwarka w weselu: zadania, goście i rodziny, usługodawcy, wydatki.

Proste dopasowanie fragmentu nazwy (bez rozróżniania wielkości liter, znaki % i _ dosłownie).
Wyniki prowadzą do ekranu, na którym obiekt się edytuje; budżet tylko dla ról, które go widzą
(koordynator dnia i sponsor nie mają dostępu do tej wyszukiwarki — wymaga roli z odczytem).
"""

from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.budget.models import BudgetItem
from app.modules.guests.models import Guest, Household
from app.modules.identity.service import Principal
from app.modules.planner.models import Task
from app.modules.vendors.models import Vendor
from app.modules.workspace.permissions import Action, authorize

LIMIT = 6
MIN_LENGTH = 2


def _like(q: str) -> str:
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def search(db: Session, principal: Principal, wedding_id: UUID, q: str) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    q = " ".join(q.split())
    if len(q) < MIN_LENGTH:
        return {"query": q, "results": []}
    pattern = _like(q)
    results: list[dict[str, Any]] = []
    for t in db.scalars(
        select(Task)
        .where(Task.wedding_id == wedding_id, Task.title.ilike(pattern, escape="\\"))
        .order_by(Task.status == "done", Task.due_date.asc().nulls_last())
        .limit(LIMIT)
    ):
        results.append(
            {
                "kind": "task",
                "id": t.id,
                "title": t.title,
                "subtitle": "zrobione" if t.status == "done" else "zadanie",
            }
        )
    for g, household in db.execute(
        select(Guest, Household.name)
        .join(Household, Household.id == Guest.household_id)
        .where(
            Guest.wedding_id == wedding_id,
            or_(
                Guest.first_name.ilike(pattern, escape="\\"),
                Guest.last_name.ilike(pattern, escape="\\"),
                Household.name.ilike(pattern, escape="\\"),
            ),
        )
        .order_by(Household.name, Guest.first_name)
        .limit(LIMIT)
    ):
        name = f"{g.first_name} {g.last_name}" if g.last_name else g.first_name
        results.append(
            {"kind": "guest", "id": g.household_id, "title": name, "subtitle": household}
        )
    for v in db.scalars(
        select(Vendor)
        .where(Vendor.wedding_id == wedding_id, Vendor.name.ilike(pattern, escape="\\"))
        .order_by(Vendor.name)
        .limit(LIMIT)
    ):
        results.append({"kind": "vendor", "id": v.id, "title": v.name, "subtitle": "usługodawca"})
    for i in db.scalars(
        select(BudgetItem)
        .where(BudgetItem.wedding_id == wedding_id, BudgetItem.name.ilike(pattern, escape="\\"))
        .order_by(BudgetItem.name)
        .limit(LIMIT)
    ):
        results.append({"kind": "expense", "id": i.id, "title": i.name, "subtitle": "wydatek"})
    return {"query": q, "results": results}
