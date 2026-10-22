"""„Co zabrać” na dzień ślubu: rzeczy do zabrania z osobą odpowiedzialną, odhaczane w dniu ślubu.

Para układa listę (albo wczytuje typową), koordynator dnia (np. świadek) odhacza ją w trakcie.
Koperty dla usługodawców podpowiadamy z płatności zaplanowanych na dzień ślubu — bez kwot,
bo koordynator nie widzi budżetu.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.errors import Conflict, NotFound
from app.modules.audit import service as audit
from app.modules.identity.service import Principal
from app.modules.schedule.models import DayChecklistItem
from app.modules.workspace.models import Wedding
from app.modules.workspace.permissions import Action, authorize

# Typowa lista (para usuwa lub dopisuje swoje). Kto zwykle bierze — podpowiedź, do zmiany.
TYPICAL: tuple[tuple[str, str | None], ...] = (
    ("Obrączki", "świadek"),
    ("Dowody osobiste pary i świadków", None),
    ("Dokumenty z USC / parafii (jeśli wymagane w dniu ślubu)", None),
    ("Buty na zmianę i plastry", None),
    ("Zestaw ratunkowy: igła z nitką, agrafki, chusteczki, leki", "świadkowa"),
    ("Ładowarka i powerbank", None),
    ("Wydruki: plan stołów, program dnia, lista kontaktów", "koordynator"),
    ("Winietki i drobne dekoracje do przekazania sali", None),
    ("Prezenty i podziękowania dla rodziców", None),
    ("Przekąska i woda dla pary", None),
)
PAYMENT_LABEL = {
    "deposit_zadatek": "zadatek",
    "advance_zaliczka": "zaliczka",
    "installment": "rata",
    "final": "dopłata",
    "other": "płatność",
}


def _item(db: Session, wedding_id: UUID, item_id: UUID) -> DayChecklistItem:
    i = db.get(DayChecklistItem, item_id)
    if i is None or i.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono pozycji.", code="day_checklist.not_found")
    return i


def _record(
    db: Session, principal: Principal, wedding_id: UUID, entity_id: UUID, action: str
) -> None:
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="day_checklist",
        entity_id=entity_id,
        wedding_id=wedding_id,
        action=action,
    )


def _ordered(db: Session, wedding_id: UUID) -> list[DayChecklistItem]:
    return list(
        db.scalars(
            select(DayChecklistItem)
            .where(DayChecklistItem.wedding_id == wedding_id)
            .order_by(DayChecklistItem.position, DayChecklistItem.created_at)
        )
    )


def list_items(db: Session, principal: Principal, wedding_id: UUID) -> list[DayChecklistItem]:
    authorize(db, principal.user.id, wedding_id, Action.DAY_READ)
    return _ordered(db, wedding_id)


def _next_position(db: Session, wedding_id: UUID) -> int:
    last = db.scalar(
        select(func.max(DayChecklistItem.position)).where(DayChecklistItem.wedding_id == wedding_id)
    )
    return 0 if last is None else last + 1


def create(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]
) -> DayChecklistItem:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    i = DayChecklistItem(wedding_id=wedding_id, position=_next_position(db, wedding_id), **data)
    db.add(i)
    db.flush()
    _record(db, principal, wedding_id, i.id, "create")
    db.commit()
    return i


def update(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    item_id: UUID,
    data: dict[str, Any],
    version: int,
) -> DayChecklistItem:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    i = _item(db, wedding_id, item_id)
    if i.version != version:
        raise Conflict("Pozycja zmieniła się w międzyczasie.", code="conflict.version_mismatch")
    for k, v in data.items():
        if v is not None or k == "who":
            setattr(i, k, v)
    _record(db, principal, wedding_id, i.id, "update")
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise Conflict(
            "Pozycja zmieniła się w międzyczasie.", code="conflict.version_mismatch"
        ) from exc
    return i


def delete(db: Session, principal: Principal, wedding_id: UUID, item_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    db.delete(_item(db, wedding_id, item_id))
    _record(db, principal, wedding_id, item_id, "delete")
    db.commit()


def set_done(
    db: Session, principal: Principal, wedding_id: UUID, item_id: UUID, done: bool
) -> DayChecklistItem:
    """Odhaczenie w dniu ślubu: także koordynator dnia (prowadzenie dnia)."""
    authorize(db, principal.user.id, wedding_id, Action.DAY_RUN)
    i = _item(db, wedding_id, item_id)
    i.done = done
    _record(db, principal, wedding_id, i.id, "done" if done else "undone")
    db.commit()
    return i


def add_typical(db: Session, principal: Principal, wedding_id: UUID) -> list[DayChecklistItem]:
    """Typowa lista i koperty z płatności na dzień ślubu; pozycje o tej samej nazwie pomijamy."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    from app.modules.budget.models import BudgetItem, Payment  # tylko odczyt płatności

    wedding = db.get_one(Wedding, wedding_id)
    have = {i.title.casefold() for i in _ordered(db, wedding_id)}
    titles: list[tuple[str, str | None]] = list(TYPICAL)
    if wedding.wedding_date:
        for kind, name in db.execute(
            select(Payment.kind, BudgetItem.name)
            .join(BudgetItem, BudgetItem.id == Payment.budget_item_id)
            .where(
                Payment.wedding_id == wedding_id,
                Payment.status == "scheduled",
                Payment.due_date == wedding.wedding_date,
            )
        ):
            titles.append((f"Koperta: {name} ({PAYMENT_LABEL.get(kind, 'płatność')})", None))
    position = _next_position(db, wedding_id)
    added = 0
    for title, who in titles:
        if title.casefold() in have:
            continue
        db.add(DayChecklistItem(wedding_id=wedding_id, title=title, who=who, position=position))
        have.add(title.casefold())
        position += 1
        added += 1
    if added:
        _record(db, principal, wedding_id, wedding_id, "add_typical")
    db.commit()
    return _ordered(db, wedding_id)
