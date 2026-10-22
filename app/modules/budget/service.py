"""Budżet: kategorie, pozycje kosztowe, płatności i podsumowanie. Wyłącznie Decimal."""

from collections import defaultdict
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core import clock
from app.core.errors import Conflict, NotFound, Unprocessable
from app.core.spreadsheet import amount_pl, csv_safe, to_csv
from app.modules.audit import service as audit
from app.modules.audit.models import AuditLog
from app.modules.budget.models import BudgetCategory, BudgetItem, Payment
from app.modules.identity.service import Principal
from app.modules.workspace.models import Wedding
from app.modules.workspace.permissions import Action, authorize

ZERO = Decimal("0.00")
CENT = Decimal("0.01")

# Domyślne kategorie i orientacyjny podział budżetu [hipoteza, do weryfikacji z parami].
DEFAULT_CATEGORIES: tuple[tuple[str, Decimal, bool], ...] = (
    ("Sala i catering", Decimal("45"), False),
    ("Muzyka", Decimal("8"), False),
    ("Foto i wideo", Decimal("9"), False),
    ("Strój i uroda", Decimal("7"), False),
    ("Dekoracje i kwiaty", Decimal("6"), False),
    ("Atrakcje", Decimal("4"), False),
    ("Obrączki", Decimal("3"), False),
    ("Noclegi", Decimal("3"), False),
    ("Transport", Decimal("2"), False),
    ("Papeteria", Decimal("1"), False),
    ("Inne", Decimal("2"), False),
    ("Rezerwa", Decimal("10"), True),
)
BUDGET_ENTITIES = ("budget_category", "budget_item", "payment")


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


def _money(data: dict[str, Any] | None) -> Decimal | None:
    return Decimal(data["amount"]) if data else None


def _record(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    entity: str,
    entity_id: UUID,
    action: str,
    changes: dict[str, Any] | None = None,
) -> None:
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type=entity,
        entity_id=entity_id,
        wedding_id=wedding_id,
        action=action,
        changes=changes,
    )


def create_default_categories(db: Session, wedding: Wedding) -> None:
    for order, (name, _share, reserve) in enumerate(DEFAULT_CATEGORIES):
        db.add(
            BudgetCategory(
                wedding_id=wedding.id,
                name=name,
                sort_order=order * 10,
                is_reserve=reserve,
                planned_amount=ZERO,
            )
        )


# --- liczba gości i koszty ---------------------------------------------------------------


def guest_counts(db: Session, wedding: Wedding) -> dict[str, int]:
    """Liczby gości dla budżetu oraz podział dorośli/dzieci (dla ceny dziecięcej)."""
    from app.modules.guests import service as guests  # goście nie zależą od budżetu

    counts = guests.counts(db, wedding)
    for basis in ("invited", "confirmed"):
        adults, children = guests.age_breakdown(db, wedding, basis)
        counts[f"{basis}_adults"], counts[f"{basis}_children"] = adults, children
    return counts


def children_used(item: BudgetItem, counts: dict[str, int]) -> int | None:
    """Ile dzieci liczy się po cenie dziecięcej (None: bez ceny dziecięcej / liczba planowana)."""
    if (
        item.cost_mode != "per_guest"
        or item.child_unit_price is None
        or item.guest_basis not in ("invited", "confirmed")
    ):
        return None
    return counts.get(f"{item.guest_basis}_children", 0)


def item_estimate(item: BudgetItem, counts: dict[str, int]) -> tuple[Decimal, int | None]:
    """Szacowany koszt pozycji: rzeczywisty → potwierdzony → planowany (za osobę x goście)."""
    if item.status == "cancelled":
        return ZERO, None
    used: int | None = None
    children = children_used(item, counts)
    if children is not None and item.unit_price is not None and item.child_unit_price is not None:
        # Dorośli (z nastolatkami) po cenie pełnej, dzieci po dziecięcej, maluchy bez opłaty.
        adults = counts.get(f"{item.guest_basis}_adults", 0)
        used = adults + children
        planned = (item.unit_price * adults + item.child_unit_price * children).quantize(
            CENT, ROUND_HALF_UP
        )
    elif item.cost_mode == "per_guest" and item.unit_price is not None and item.guest_basis:
        used = counts[item.guest_basis]
        planned = (item.unit_price * used).quantize(CENT, ROUND_HALF_UP)
    else:
        planned = item.planned_amount or ZERO
    for value in (item.actual_amount, item.confirmed_amount, planned):
        if value is not None:
            return value, used
    return ZERO, used


def is_payment_overdue(p: Payment) -> bool:
    return p.status == "scheduled" and p.due_date is not None and p.due_date < clock.today()


def paid_by_item(db: Session, item_ids: list[UUID]) -> dict[UUID, Decimal]:
    result: dict[UUID, Decimal] = defaultdict(lambda: ZERO)
    if not item_ids:
        return result
    rows = db.execute(
        select(Payment.budget_item_id, func.sum(Payment.amount))
        .where(Payment.budget_item_id.in_(item_ids), Payment.status == "paid")
        .group_by(Payment.budget_item_id)
    ).all()
    for item_id, total in rows:
        result[item_id] = total
    return result


# --- kategorie ----------------------------------------------------------------------------


def _category(db: Session, wedding_id: UUID, category_id: UUID) -> BudgetCategory:
    c = db.get(BudgetCategory, category_id)
    if c is None or c.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono kategorii.", code="budget.category_not_found")
    return c


def list_categories(db: Session, principal: Principal, wedding_id: UUID) -> list[BudgetCategory]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return list(
        db.scalars(
            select(BudgetCategory)
            .where(BudgetCategory.wedding_id == wedding_id)
            .order_by(BudgetCategory.sort_order, BudgetCategory.name)
        )
    )


def _unique_name(db: Session, wedding_id: UUID, name: str, exclude: UUID | None = None) -> None:
    stmt = select(BudgetCategory.id).where(
        BudgetCategory.wedding_id == wedding_id, func.lower(BudgetCategory.name) == name.lower()
    )
    if exclude:
        stmt = stmt.where(BudgetCategory.id != exclude)
    if db.scalars(stmt).first():
        raise Conflict("Kategoria o tej nazwie już istnieje.", code="budget.category_exists")


def create_category(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]
) -> BudgetCategory:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    _unique_name(db, wedding_id, data["name"])
    c = BudgetCategory(
        wedding_id=wedding_id,
        name=data["name"],
        planned_amount=_money(data["planned"]) or ZERO,
        sort_order=data["sort_order"],
        is_reserve=data["is_reserve"],
    )
    db.add(c)
    db.flush()
    _record(
        db,
        principal,
        wedding_id,
        "budget_category",
        c.id,
        "create",
        {"planned": [None, str(c.planned_amount)]},
    )
    db.commit()
    return c


def update_category(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    category_id: UUID,
    data: dict[str, Any],
    version: int,
) -> BudgetCategory:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    c = _category(db, wedding_id, category_id)
    if c.version != version:
        raise _conflict()
    values: dict[str, Any] = {}
    if data.get("name"):
        _unique_name(db, wedding_id, data["name"], exclude=c.id)
        values["name"] = data["name"]
    if data.get("planned") is not None:
        values["planned_amount"] = _money(data["planned"])
    for key in ("sort_order", "is_reserve"):
        if data.get(key) is not None:
            values[key] = data[key]
    before = {k: getattr(c, k) for k in values}
    for k, v in values.items():
        setattr(c, k, v)
    _record(
        db, principal, wedding_id, "budget_category", c.id, "update", audit.diff(before, values)
    )
    _commit(db)
    return c


def delete_category(db: Session, principal: Principal, wedding_id: UUID, category_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    c = _category(db, wedding_id, category_id)
    if db.scalars(select(BudgetItem.id).where(BudgetItem.category_id == c.id)).first():
        raise Conflict(
            "Kategoria ma pozycje kosztowe. Przenieś je lub usuń.", code="budget.category_not_empty"
        )
    db.delete(c)
    _record(db, principal, wedding_id, "budget_category", category_id, "delete")
    db.commit()


def apply_split(
    db: Session, principal: Principal, wedding_id: UUID, dry_run: bool
) -> list[dict[str, Any]]:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    wedding = db.get_one(Wedding, wedding_id)
    if wedding.total_budget is None:
        raise Unprocessable("Najpierw ustaw budżet całkowity wesela.", code="budget.total_missing")
    shares = {name: share for name, share, _ in DEFAULT_CATEGORIES}
    proposals: list[dict[str, Any]] = []
    for c in list_categories(db, principal, wedding_id):
        if c.name not in shares:
            continue
        new = (wedding.total_budget * shares[c.name] / 100).quantize(CENT, ROUND_HALF_UP)
        proposals.append(
            {
                "category_id": c.id,
                "name": c.name,
                "share_percent": shares[c.name],
                "old_planned": c.planned_amount,
                "new_planned": new,
                "obj": c,
            }
        )
    if not dry_run:
        for p in proposals:
            p["obj"].planned_amount = p["new_planned"]
        _record(
            db,
            principal,
            wedding_id,
            "budget_category",
            wedding_id,
            "apply_split",
            {"categories": [None, len(proposals)]},
        )
        _commit(db)
    for p in proposals:
        p.pop("obj")
    return proposals


# --- pozycje -----------------------------------------------------------------------------


def _item(db: Session, wedding_id: UUID, item_id: UUID) -> BudgetItem:
    i = db.get(BudgetItem, item_id)
    if i is None or i.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono pozycji budżetu.", code="budget.item_not_found")
    return i


def list_items(
    db: Session, principal: Principal, wedding_id: UUID, category_id: UUID | None
) -> list[BudgetItem]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    stmt = select(BudgetItem).where(BudgetItem.wedding_id == wedding_id)
    if category_id:
        stmt = stmt.where(BudgetItem.category_id == category_id)
    return list(db.scalars(stmt.order_by(BudgetItem.created_at)))


def get_item(db: Session, principal: Principal, wedding_id: UUID, item_id: UUID) -> BudgetItem:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return _item(db, wedding_id, item_id)


def _item_values(data: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    mapping = {
        "planned": "planned_amount",
        "unit_price": "unit_price",
        "child_unit_price": "child_unit_price",
        "confirmed": "confirmed_amount",
        "actual": "actual_amount",
    }
    for key, column in mapping.items():
        if key in data:
            values[column] = _money(data[key])
    for key in (
        "category_id",
        "name",
        "cost_mode",
        "guest_basis",
        "status",
        "notes",
        "indexation",
        "indexation_cap_percent",
        "price_fixed_on",
        "price_review_on",
    ):
        if key in data:
            values[key] = data[key]
    return values


def _validate_item(item: BudgetItem) -> None:
    if item.cost_mode == "per_guest" and (item.unit_price is None or not item.guest_basis):
        raise Unprocessable(
            "Koszt za osobę wymaga unit_price i guest_basis.", code="budget.item_incomplete"
        )
    if item.cost_mode == "fixed" and item.planned_amount is None:
        raise Unprocessable("Koszt stały wymaga kwoty planned.", code="budget.item_incomplete")
    if item.indexation == "cap" and item.indexation_cap_percent is None:
        raise Unprocessable(
            "Przy limicie podwyżki podajcie maksymalny procent.", code="budget.indexation_cap"
        )


def create_item(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]
) -> BudgetItem:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    _category(db, wedding_id, data["category_id"])
    item = BudgetItem(wedding_id=wedding_id, **_item_values(data))
    _validate_item(item)
    db.add(item)
    db.flush()
    _record(
        db,
        principal,
        wedding_id,
        "budget_item",
        item.id,
        "create",
        audit.diff({}, _item_values(data)),
    )
    db.commit()
    return item


def update_item(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    item_id: UUID,
    data: dict[str, Any],
    version: int,
) -> BudgetItem:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    item = _item(db, wedding_id, item_id)
    if item.version != version:
        raise _conflict()
    values = _item_values(data)
    if values.get("category_id"):
        _category(db, wedding_id, values["category_id"])
    before = {k: getattr(item, k) for k in values}
    for k, v in values.items():
        if k in ("category_id", "name", "cost_mode", "status", "indexation") and v is None:
            continue
        setattr(item, k, v)
    if item.cost_mode == "fixed":
        item.unit_price, item.guest_basis = None, None
    try:
        _validate_item(item)
    except Unprocessable:
        db.rollback()
        raise
    _record(db, principal, wedding_id, "budget_item", item.id, "update", audit.diff(before, values))
    _commit(db)
    return item


def delete_item(db: Session, principal: Principal, wedding_id: UUID, item_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    item = _item(db, wedding_id, item_id)
    db.delete(item)
    _record(db, principal, wedding_id, "budget_item", item_id, "delete")
    db.commit()


# --- płatności ---------------------------------------------------------------------------


def _payment(db: Session, wedding_id: UUID, payment_id: UUID) -> Payment:
    p = db.get(Payment, payment_id)
    if p is None or p.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono płatności.", code="budget.payment_not_found")
    return p


def item_names(db: Session, item_ids: set[UUID]) -> dict[UUID, str]:
    if not item_ids:
        return {}
    rows = db.execute(select(BudgetItem.id, BudgetItem.name).where(BudgetItem.id.in_(item_ids)))
    return {item_id: name for item_id, name in rows}


def list_item_payments(
    db: Session, principal: Principal, wedding_id: UUID, item_id: UUID
) -> list[Payment]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    _item(db, wedding_id, item_id)
    return list(
        db.scalars(
            select(Payment)
            .where(Payment.budget_item_id == item_id)
            .order_by(Payment.due_date.asc().nulls_last(), Payment.created_at)
        )
    )


def create_payment(
    db: Session, principal: Principal, wedding_id: UUID, item_id: UUID, data: dict[str, Any]
) -> Payment:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    _item(db, wedding_id, item_id)
    from app.modules.budget import funders  # moduł portfela korzysta z modeli budżetu

    funders.check_funder(db, wedding_id, data.get("funder_id"))
    p = Payment(
        wedding_id=wedding_id,
        budget_item_id=item_id,
        kind=data["kind"],
        amount=_money(data["amount"]),
        due_date=data.get("due_date"),
        paid_on=data.get("paid_on"),
        notes=data.get("notes"),
        funder_id=data.get("funder_id"),
        status="paid" if data.get("paid_on") else "scheduled",
    )
    db.add(p)
    db.flush()
    _record(
        db,
        principal,
        wedding_id,
        "payment",
        p.id,
        "create",
        {
            "kind": [None, p.kind],
            "amount": [None, str(p.amount)],
            "due_date": [None, str(p.due_date) if p.due_date else None],
        },
    )
    db.commit()
    return p


def update_payment(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    payment_id: UUID,
    data: dict[str, Any],
    version: int,
) -> Payment:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    p = _payment(db, wedding_id, payment_id)
    if p.version != version:
        raise _conflict()
    values: dict[str, Any] = {}
    if data.get("amount") is not None:
        amount = _money(data["amount"])
        if amount is None or amount <= 0:
            raise Unprocessable("Kwota płatności musi być dodatnia.", code="budget.amount")
        values["amount"] = amount
    if "funder_id" in data:
        from app.modules.budget import funders

        funders.check_funder(db, wedding_id, data["funder_id"])
    for key in ("kind", "due_date", "notes", "status", "funder_id"):
        if key in data and (data[key] is not None or key in ("due_date", "notes", "funder_id")):
            values[key] = data[key]
    if values.get("status") == "scheduled":
        values["paid_on"] = None
    before = {k: getattr(p, k) for k in values}
    for k, v in values.items():
        setattr(p, k, v)
    _record(db, principal, wedding_id, "payment", p.id, "update", audit.diff(before, values))
    _commit(db)
    return p


def mark_paid(
    db: Session, principal: Principal, wedding_id: UUID, payment_id: UUID, paid_on: Any
) -> Payment:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    p = _payment(db, wedding_id, payment_id)
    if p.status == "cancelled":
        raise Conflict("Płatność jest anulowana.", code="budget.payment_cancelled")
    old = p.status
    p.status, p.paid_on = "paid", paid_on or clock.today()
    _record(
        db,
        principal,
        wedding_id,
        "payment",
        p.id,
        "mark_paid",
        {"status": [old, "paid"], "paid_on": [None, str(p.paid_on)]},
    )
    db.commit()
    return p


def delete_payment(db: Session, principal: Principal, wedding_id: UUID, payment_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    p = _payment(db, wedding_id, payment_id)
    db.delete(p)
    _record(db, principal, wedding_id, "payment", payment_id, "delete")
    db.commit()


def payment_schedule(
    db: Session, principal: Principal, wedding_id: UUID, status: str | None
) -> list[Payment]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    stmt = select(Payment).where(Payment.wedding_id == wedding_id)
    if status:
        stmt = stmt.where(Payment.status == status)
    return list(db.scalars(stmt.order_by(Payment.due_date.asc().nulls_last(), Payment.created_at)))


# --- podsumowanie i historia ------------------------------------------------------------


def overview(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    wedding = db.get_one(Wedding, wedding_id)
    counts = guest_counts(db, wedding)
    categories = list_categories(db, principal, wedding_id)
    items = list(db.scalars(select(BudgetItem).where(BudgetItem.wedding_id == wedding_id)))
    payments = list(db.scalars(select(Payment).where(Payment.wedding_id == wedding_id)))
    paid = paid_by_item(db, [i.id for i in items])

    est_by_cat: dict[UUID, Decimal] = defaultdict(lambda: ZERO)
    paid_by_cat: dict[UUID, Decimal] = defaultdict(lambda: ZERO)
    for item in items:
        est, _ = item_estimate(item, counts)
        est_by_cat[item.category_id] += est
        paid_by_cat[item.category_id] += paid[item.id]

    estimated_total = sum(est_by_cat.values(), ZERO)
    paid_total = sum(paid_by_cat.values(), ZERO)
    basis = next((b for b in ("confirmed", "invited", "planned") if counts[b] > 0), None)
    today = clock.today()
    horizon = today + timedelta(days=30)
    unallocated = (
        wedding.total_budget - estimated_total if wedding.total_budget is not None else None
    )
    return {
        "wedding": wedding,
        "guest_counts": counts,
        "planned_in_categories": sum((c.planned_amount for c in categories), ZERO),
        "estimated_total": estimated_total,
        "paid_total": paid_total,
        "remaining_to_pay": max(estimated_total - paid_total, ZERO),
        "unallocated": unallocated,
        "over_budget": unallocated is not None and unallocated < 0,
        "reserve_planned": sum((c.planned_amount for c in categories if c.is_reserve), ZERO),
        "cost_per_guest": (estimated_total / counts[basis]).quantize(CENT, ROUND_HALF_UP)
        if basis
        else None,
        "cost_per_guest_basis": basis,
        "overdue_payments": [p for p in payments if is_payment_overdue(p)],
        "upcoming_payments_30d": sorted(
            (
                p
                for p in payments
                if p.status == "scheduled"
                and p.due_date is not None
                and today <= p.due_date <= horizon
            ),
            key=lambda p: p.due_date or today,
        ),
        "categories": [
            {
                "id": c.id,
                "name": c.name,
                "planned": c.planned_amount,
                "estimated": est_by_cat[c.id],
                "paid": paid_by_cat[c.id],
                "over_plan": est_by_cat[c.id] > c.planned_amount > 0,
            }
            for c in categories
        ],
    }


def history(db: Session, principal: Principal, wedding_id: UUID, limit: int) -> list[AuditLog]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.wedding_id == wedding_id, AuditLog.entity_type.in_(BUDGET_ENTITIES))
            .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
            .limit(limit)
        )
    )


# --- eksport do arkusza --------------------------------------------------------------------

ITEM_STATUS_LABELS = {
    "planned": "planowana",
    "confirmed": "potwierdzona",
    "paid": "opłacona",
    "cancelled": "anulowana",
}
PAYMENT_KIND_LABELS = {
    "deposit_zadatek": "zadatek",
    "advance_zaliczka": "zaliczka",
    "installment": "rata",
    "final": "dopłata",
    "other": "płatność",
}
PAYMENT_STATUS_LABELS = {
    "scheduled": "do zapłaty",
    "paid": "zapłacona",
    "cancelled": "anulowana",
    "refunded": "zwrócona",
}
BASIS_LABELS = {"planned": "planowana", "invited": "zaproszeni", "confirmed": "potwierdzeni"}


def export_csv(db: Session, principal: Principal, wedding_id: UUID, part: str) -> str:
    """Budżet do arkusza: pozycje kosztowe (`items`) albo harmonogram płatności (`payments`)."""
    authorize(db, principal.user.id, wedding_id, Action.EXPORT)
    wedding = db.get_one(Wedding, wedding_id)
    categories = {c.id: c.name for c in list_categories(db, principal, wedding_id)}
    items = list(
        db.scalars(
            select(BudgetItem)
            .where(BudgetItem.wedding_id == wedding_id)
            .order_by(BudgetItem.created_at)
        )
    )
    if part == "payments":
        by_id = {i.id: i for i in items}
        payments = payment_schedule(db, principal, wedding_id, None)
        header = ["Pozycja", "Kategoria", "Rodzaj", "Kwota (zł)", "Termin", "Status"]
        header += ["Zapłacono dnia", "Po terminie", "Uwagi"]
        rows: list[list[object]] = []
        for p in payments:
            item = by_id.get(p.budget_item_id)
            rows.append(
                [
                    csv_safe(item.name if item else ""),
                    csv_safe(categories.get(item.category_id, "") if item else ""),
                    PAYMENT_KIND_LABELS.get(p.kind, p.kind),
                    amount_pl(p.amount),
                    p.due_date.isoformat() if p.due_date else "",
                    PAYMENT_STATUS_LABELS.get(p.status, p.status),
                    p.paid_on.isoformat() if p.paid_on else "",
                    "tak" if is_payment_overdue(p) else "",
                    csv_safe(p.notes or ""),
                ]
            )
    else:
        counts = guest_counts(db, wedding)
        paid = paid_by_item(db, [i.id for i in items])
        order = {cid: n for n, cid in enumerate(categories)}
        items.sort(key=lambda i: order.get(i.category_id, len(order)))
        header = ["Kategoria", "Pozycja", "Koszt", "Cena za osobę (zł)", "Liczba osób"]
        header += ["Plan (zł)", "Umowa (zł)", "Rzeczywisty (zł)", "Szacunek (zł)"]
        header += ["Zapłacono (zł)", "Do zapłaty (zł)", "Status", "Uwagi"]
        rows = []
        for i in items:
            estimate, used = item_estimate(i, counts)
            per_guest = i.cost_mode == "per_guest"
            basis = BASIS_LABELS.get(i.guest_basis or "", "") if per_guest else ""
            rows.append(
                [
                    csv_safe(categories.get(i.category_id, "")),
                    csv_safe(i.name),
                    f"za osobę ({basis})"
                    if per_guest and basis
                    else "za osobę"
                    if per_guest
                    else "stały",
                    amount_pl(i.unit_price) if per_guest else "",
                    used if used is not None else "",
                    amount_pl(i.planned_amount),
                    amount_pl(i.confirmed_amount),
                    amount_pl(i.actual_amount),
                    amount_pl(estimate),
                    amount_pl(paid[i.id]),
                    amount_pl(max(estimate - paid[i.id], ZERO)),
                    ITEM_STATUS_LABELS.get(i.status, i.status),
                    csv_safe(i.notes or ""),
                ]
            )
    _record(db, principal, wedding_id, "budget", wedding_id, "export_csv", {"part": [None, part]})
    db.commit()
    return to_csv(header, rows)
