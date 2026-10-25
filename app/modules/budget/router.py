from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.core.deps import CurrentPrincipal, DbSession, IfMatchVersion, etag
from app.core.schemas import Money, SignedMoney
from app.modules.budget import funders, indexation, insights, service
from app.modules.budget.models import BudgetCategory, BudgetItem, Payment
from app.modules.budget.schemas import (
    BudgetOverview,
    Cashflow,
    CashflowMonth,
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    ContributionCreate,
    ContributionOut,
    FunderCreate,
    FunderDetail,
    FunderPayment,
    FundersOverview,
    FunderSummary,
    FunderUpdate,
    GuestCost,
    GuestCostSource,
    HistoryEntry,
    IndexationAssumptions,
    IndexationAssumptionsIn,
    IndexationItem,
    IndexationOverview,
    ItemCreate,
    ItemOut,
    ItemUpdate,
    MarkPaidIn,
    PaymentCreate,
    PaymentOut,
    PaymentStatus,
    PaymentUpdate,
    SplitIn,
    SplitOut,
)
from app.modules.workspace.models import Wedding

router = APIRouter(tags=["budżet"])

Responses = dict[int | str, dict[str, Any]]
_READ: Responses = {
    401: {"description": "Brak uwierzytelnienia"},
    404: {"description": "Nie znaleziono lub brak dostępu"},
}
_WRITE: Responses = {
    **_READ,
    403: {"description": "Rola tylko do odczytu"},
    409: {"description": "Konflikt"},
    422: {"description": "Błąd walidacji"},
}
_PATCH: Responses = {**_WRITE, 428: {"description": "Brak If-Match"}}
W = "/weddings/{wedding_id}"


def _m(value: Decimal | None) -> Money | None:
    return Money(amount=value) if value is not None else None


def _category_out(c: BudgetCategory) -> CategoryOut:
    return CategoryOut(
        id=c.id,
        name=c.name,
        planned=Money(amount=c.planned_amount),
        sort_order=c.sort_order,
        is_reserve=c.is_reserve,
        version=c.version,
    )


def _item_out(db: DbSession, item: BudgetItem) -> ItemOut:
    wedding = db.get_one(Wedding, item.wedding_id)
    counts = service.guest_counts(db, wedding)
    estimate, used = service.item_estimate(item, counts)
    paid = service.paid_by_item(db, [item.id])[item.id]
    return ItemOut.model_validate(
        {
            "id": item.id,
            "category_id": item.category_id,
            "name": item.name,
            "cost_mode": item.cost_mode,
            "planned": _m(item.planned_amount),
            "unit_price": _m(item.unit_price),
            "child_unit_price": _m(item.child_unit_price),
            "guest_basis": item.guest_basis,
            "guest_count_used": used,
            "children_used": service.children_used(item, counts),
            "confirmed": _m(item.confirmed_amount),
            "actual": _m(item.actual_amount),
            "estimated": Money(amount=estimate),
            "paid": Money(amount=paid),
            "status": item.status,
            "notes": item.notes,
            "indexation": item.indexation,
            "indexation_cap_percent": item.indexation_cap_percent,
            "price_fixed_on": item.price_fixed_on,
            "price_review_on": item.price_review_on,
            "version": item.version,
        }
    )


def payment_out(p: Payment, item_name: str) -> PaymentOut:
    return PaymentOut.model_validate(
        {
            "id": p.id,
            "budget_item_id": p.budget_item_id,
            "item_name": item_name,
            "kind": p.kind,
            "amount": Money(amount=p.amount),
            "due_date": p.due_date,
            "paid_on": p.paid_on,
            "status": p.status,
            "is_overdue": service.is_payment_overdue(p),
            "notes": p.notes,
            "funder_id": p.funder_id,
            "version": p.version,
        }
    )


def _payments_out(db: DbSession, payments: list[Payment]) -> list[PaymentOut]:
    names = service.item_names(db, {p.budget_item_id for p in payments})
    return [payment_out(p, names.get(p.budget_item_id, "")) for p in payments]


# --- kategorie ------------------------------------------------------------------------------


@router.get(f"{W}/budget/categories", responses=_READ, summary="Kategorie budżetu")
def list_categories(
    wedding_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> list[CategoryOut]:
    return [_category_out(c) for c in service.list_categories(db, principal, wedding_id)]


@router.post(f"{W}/budget/categories", status_code=201, responses=_WRITE, summary="Nowa kategoria")
def create_category(
    wedding_id: UUID, body: CategoryCreate, principal: CurrentPrincipal, db: DbSession
) -> CategoryOut:
    return _category_out(service.create_category(db, principal, wedding_id, body.model_dump()))


@router.patch(
    f"{W}/budget/categories/{{category_id}}",
    responses=_PATCH,
    summary="Edycja kategorii (If-Match)",
)
def update_category(
    wedding_id: UUID,
    category_id: UUID,
    principal: CurrentPrincipal,
    body: CategoryUpdate,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> CategoryOut:
    c = service.update_category(
        db, principal, wedding_id, category_id, body.model_dump(exclude_unset=True), version
    )
    response.headers["ETag"] = etag(c.version)
    return _category_out(c)


@router.delete(
    f"{W}/budget/categories/{{category_id}}",
    status_code=204,
    responses=_WRITE,
    summary="Usunięcie pustej kategorii",
)
def delete_category(
    wedding_id: UUID, category_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.delete_category(db, principal, wedding_id, category_id)


@router.post(
    f"{W}/budget/apply-split",
    responses=_WRITE,
    summary="Orientacyjny podział budżetu na kategorie domyślne (dry_run)",
)
def apply_split(
    wedding_id: UUID, body: SplitIn, principal: CurrentPrincipal, db: DbSession
) -> SplitOut:
    proposals = service.apply_split(db, principal, wedding_id, body.dry_run)
    return SplitOut.model_validate(
        {
            "dry_run": body.dry_run,
            "proposals": [
                {
                    **p,
                    "old_planned": Money(amount=p["old_planned"]),
                    "new_planned": Money(amount=p["new_planned"]),
                }
                for p in proposals
            ],
        }
    )


# --- pozycje ------------------------------------------------------------------------------


@router.get(f"{W}/budget/items", responses=_READ, summary="Pozycje kosztowe")
def list_items(
    wedding_id: UUID, principal: CurrentPrincipal, db: DbSession, category_id: UUID | None = None
) -> list[ItemOut]:
    return [_item_out(db, i) for i in service.list_items(db, principal, wedding_id, category_id)]


@router.post(
    f"{W}/budget/items",
    status_code=201,
    responses=_WRITE,
    summary="Nowa pozycja (koszt stały lub za osobę)",
)
def create_item(
    wedding_id: UUID, body: ItemCreate, principal: CurrentPrincipal, db: DbSession
) -> ItemOut:
    return _item_out(db, service.create_item(db, principal, wedding_id, body.model_dump()))


@router.get(f"{W}/budget/items/{{item_id}}", responses=_READ, summary="Pozycja kosztowa")
def get_item(
    wedding_id: UUID, item_id: UUID, principal: CurrentPrincipal, db: DbSession, response: Response
) -> ItemOut:
    item = service.get_item(db, principal, wedding_id, item_id)
    response.headers["ETag"] = etag(item.version)
    return _item_out(db, item)


@router.patch(
    f"{W}/budget/items/{{item_id}}", responses=_PATCH, summary="Edycja pozycji (If-Match)"
)
def update_item(
    wedding_id: UUID,
    item_id: UUID,
    principal: CurrentPrincipal,
    body: ItemUpdate,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> ItemOut:
    item = service.update_item(
        db, principal, wedding_id, item_id, body.model_dump(exclude_unset=True), version
    )
    response.headers["ETag"] = etag(item.version)
    return _item_out(db, item)


@router.delete(
    f"{W}/budget/items/{{item_id}}",
    status_code=204,
    responses=_WRITE,
    summary="Usunięcie pozycji (wraz z płatnościami)",
)
def delete_item(
    wedding_id: UUID, item_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.delete_item(db, principal, wedding_id, item_id)


# --- płatności -------------------------------------------------------------------------------


@router.get(f"{W}/budget/items/{{item_id}}/payments", responses=_READ, summary="Płatności pozycji")
def list_item_payments(
    wedding_id: UUID, item_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> list[PaymentOut]:
    return _payments_out(db, service.list_item_payments(db, principal, wedding_id, item_id))


@router.post(
    f"{W}/budget/items/{{item_id}}/payments",
    status_code=201,
    responses=_WRITE,
    summary="Nowa płatność: zadatek, zaliczka, rata, dopłata",
)
def create_payment(
    wedding_id: UUID, item_id: UUID, body: PaymentCreate, principal: CurrentPrincipal, db: DbSession
) -> PaymentOut:
    p = service.create_payment(db, principal, wedding_id, item_id, body.model_dump())
    return _payments_out(db, [p])[0]


@router.patch(
    f"{W}/payments/{{payment_id}}", responses=_PATCH, summary="Edycja płatności (If-Match)"
)
def update_payment(
    wedding_id: UUID,
    payment_id: UUID,
    principal: CurrentPrincipal,
    body: PaymentUpdate,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> PaymentOut:
    p = service.update_payment(
        db, principal, wedding_id, payment_id, body.model_dump(exclude_unset=True), version
    )
    response.headers["ETag"] = etag(p.version)
    return _payments_out(db, [p])[0]


@router.post(
    f"{W}/payments/{{payment_id}}/mark-paid",
    responses=_WRITE,
    summary="Oznacz płatność jako zapłaconą",
)
def mark_paid(
    wedding_id: UUID, payment_id: UUID, body: MarkPaidIn, principal: CurrentPrincipal, db: DbSession
) -> PaymentOut:
    p = service.mark_paid(db, principal, wedding_id, payment_id, body.paid_on)
    return _payments_out(db, [p])[0]


@router.delete(
    f"{W}/payments/{{payment_id}}", status_code=204, responses=_WRITE, summary="Usunięcie płatności"
)
def delete_payment(
    wedding_id: UUID, payment_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.delete_payment(db, principal, wedding_id, payment_id)


@router.get(
    f"{W}/payments/schedule",
    responses=_READ,
    summary="Harmonogram płatności (z oznaczeniem zaległych)",
)
def payment_schedule(
    wedding_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    status: PaymentStatus | None = None,
) -> list[PaymentOut]:
    return _payments_out(db, service.payment_schedule(db, principal, wedding_id, status))


# --- podsumowanie i historia --------------------------------------------------------------


@router.get(
    f"{W}/budget/overview",
    responses=_READ,
    summary="Podsumowanie: koszty, zapłacone, do zapłaty, koszt na osobę",
)
def overview(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> BudgetOverview:
    o = service.overview(db, principal, wedding_id)
    wedding = o.pop("wedding")
    payments = o["overdue_payments"] + o["upcoming_payments_30d"]
    names = service.item_names(db, {p.budget_item_id for p in payments})
    money_keys = (
        "planned_in_categories",
        "estimated_total",
        "paid_total",
        "remaining_to_pay",
        "reserve_planned",
        "cost_per_guest",
    )
    return BudgetOverview.model_validate(
        {
            **{k: (_m(o[k]) if k in money_keys else o[k]) for k in o},
            "unallocated": SignedMoney(amount=o["unallocated"])
            if o["unallocated"] is not None
            else None,
            "total_budget": _m(wedding.total_budget),
            "overdue_payments": [
                payment_out(p, names.get(p.budget_item_id, "")) for p in o["overdue_payments"]
            ],
            "upcoming_payments_30d": [
                payment_out(p, names.get(p.budget_item_id, "")) for p in o["upcoming_payments_30d"]
            ],
            "categories": [
                {
                    **c,
                    "planned": Money(amount=c["planned"]),
                    "estimated": Money(amount=c["estimated"]),
                    "paid": Money(amount=c["paid"]),
                }
                for c in o["categories"]
            ],
        }
    )


@router.get(
    f"{W}/budget/export.csv",
    responses=_READ,
    response_class=Response,
    summary="Budżet do arkusza: pozycje albo płatności (CSV, średnik, UTF-8 z BOM)",
)
def export_budget_csv(
    wedding_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    part: Literal["items", "payments"] = "items",
) -> Response:
    data = service.export_csv(db, principal, wedding_id, part)
    name = "budzet-platnosci.csv" if part == "payments" else "budzet.csv"
    return Response(
        content=data.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(f"{W}/budget/history", responses=_READ, summary="Historia zmian budżetu (audyt)")
def history(
    wedding_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[HistoryEntry]:
    return [
        HistoryEntry(
            occurred_at=e.occurred_at,
            actor_id=e.actor_id,
            action=e.action,
            entity_type=e.entity_type,
            entity_id=e.entity_id,
            changes=e.changes,
        )
        for e in service.history(db, principal, wedding_id, limit)
    ]


# --- portfel sponsorów ---------------------------------------------------------------------

_MONEY_FIELDS = (
    "pledged_amount",
    "paid_direct",
    "scheduled_direct",
    "given",
    "reported",
    "covered",
    "to_settle",
)


def _funder_summary(d: dict[str, Any]) -> FunderSummary:
    return FunderSummary.model_validate(
        {k: ({"amount": v} if k in _MONEY_FIELDS and v is not None else v) for k, v in d.items()}
    )


def _funder_detail(d: dict[str, Any]) -> FunderDetail:
    return FunderDetail(
        funder=_funder_summary(d["funder"]),
        payments=[
            FunderPayment.model_validate({**p, "amount": Money(amount=p["amount"])})
            for p in d["payments"]
        ],
        contributions=[
            ContributionOut.model_validate({**c, "amount": Money(amount=c["amount"])})
            for c in d["contributions"]
        ],
    )


def _pledged(data: dict[str, Any]) -> dict[str, Any]:
    if "pledged_amount" in data:
        money = data["pledged_amount"]
        data["pledged_amount"] = Decimal(money["amount"]) if money else None
    return data


@router.get(f"{W}/funders", responses=_READ, summary="Portfel sponsorów: kto i ile dokłada")
def list_funders(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> FundersOverview:
    o = funders.overview(db, principal, wedding_id)
    return FundersOverview(
        funders=[_funder_summary(f) for f in o["funders"]],
        pledged_total=Money(amount=o["pledged_total"]),
        covered_total=Money(amount=o["covered_total"]),
        couple_paid=Money(amount=o["couple_paid"]),
        couple_scheduled=Money(amount=o["couple_scheduled"]),
    )


@router.post(f"{W}/funders", status_code=201, responses=_WRITE, summary="Nowy sponsor")
def create_funder(
    wedding_id: UUID, body: FunderCreate, principal: CurrentPrincipal, db: DbSession
) -> FunderDetail:
    f = funders.create(db, principal, wedding_id, _pledged(body.model_dump()))
    return _funder_detail(funders.detail(db, wedding_id, f))


@router.get(f"{W}/funders/{{funder_id}}", responses=_READ, summary="Wkład sponsora")
def get_funder(
    wedding_id: UUID, funder_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> FunderDetail:
    return _funder_detail(funders.get_detail(db, principal, wedding_id, funder_id))


@router.patch(f"{W}/funders/{{funder_id}}", responses=_PATCH, summary="Edycja sponsora (If-Match)")
def update_funder(
    wedding_id: UUID,
    funder_id: UUID,
    body: FunderUpdate,
    principal: CurrentPrincipal,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> FunderDetail:
    f = funders.update(
        db, principal, wedding_id, funder_id, _pledged(body.model_dump(exclude_unset=True)), version
    )
    response.headers["ETag"] = etag(f.version)
    return _funder_detail(funders.detail(db, wedding_id, f))


@router.delete(
    f"{W}/funders/{{funder_id}}",
    status_code=204,
    responses=_WRITE,
    summary="Usunięcie sponsora (jego płatności wracają do pary)",
)
def delete_funder(
    wedding_id: UUID, funder_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    funders.delete(db, principal, wedding_id, funder_id)


@router.post(
    f"{W}/funders/{{funder_id}}/contributions",
    status_code=201,
    responses=_WRITE,
    summary="Wpłata od sponsora (pieniądze przekazane parze)",
)
def add_contribution(
    wedding_id: UUID,
    funder_id: UUID,
    body: ContributionCreate,
    principal: CurrentPrincipal,
    db: DbSession,
) -> FunderDetail:
    data = body.model_dump()
    data["amount"] = Decimal(data["amount"]["amount"])
    funders.add_contribution(db, principal, wedding_id, funder_id, data)
    return _funder_detail(funders.get_detail(db, principal, wedding_id, funder_id))


@router.delete(
    f"{W}/funders/{{funder_id}}/contributions/{{contribution_id}}",
    status_code=204,
    responses=_WRITE,
    summary="Usunięcie wpłaty sponsora",
)
def delete_contribution(
    wedding_id: UUID,
    funder_id: UUID,
    contribution_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
) -> None:
    funders.delete_contribution(db, principal, wedding_id, funder_id, contribution_id)


@router.get(
    f"{W}/my-contribution",
    responses={**_READ, 403: {"description": "Tylko rola sponsor"}},
    summary="Widok sponsora: tylko jego wkład",
)
def my_contribution(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> FunderDetail:
    return _funder_detail(funders.my_contribution(db, principal, wedding_id))


# --- strażnik waloryzacji ------------------------------------------------------------------

_INDEX_MONEY = ("remaining", "expected_increase", "worst_increase")


def _index_item(r: dict[str, Any]) -> IndexationItem:
    return IndexationItem.model_validate(
        {k: (Money(amount=v) if k in _INDEX_MONEY else v) for k, v in r.items()}
    )


@router.get(
    f"{W}/budget/indexation",
    responses=_READ,
    summary="Strażnik waloryzacji: koszt dziś, z prognozowanymi podwyżkami i w najgorszym razie",
)
def budget_indexation(
    wedding_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    expected_rate: Annotated[
        float | None, Query(ge=0, le=0.5, description="Bez parametru — założenie zapisane")
    ] = None,
    worst_rate: Annotated[float | None, Query(ge=0, le=0.5)] = None,
) -> IndexationOverview:
    o = indexation.overview(
        db, principal, wedding_id, expected_rate=expected_rate, worst_rate=worst_rate
    )
    return IndexationOverview(
        expected_rate=o["expected_rate"],
        worst_rate=o["worst_rate"],
        assumptions=IndexationAssumptions(
            expected_rate=o["saved_expected_rate"],
            worst_rate=o["saved_worst_rate"],
            saved=o["assumptions_saved"],
        ),
        wedding_day=o["wedding_day"],
        approximate=o["approximate"],
        today_total=Money(amount=o["today_total"]),
        expected_total=Money(amount=o["expected_total"]),
        worst_total=Money(amount=o["worst_total"]),
        items=[_index_item(r) for r in o["items"]],
        reviews_soon=[_index_item(r) for r in o["reviews_soon"]],
    )


@router.put(
    f"{W}/budget/indexation/assumptions",
    responses=_WRITE,
    summary="Zapisanie założeń inflacji dla strażnika waloryzacji (wspólne dla Budżetu i Dziś)",
)
def save_indexation_assumptions(
    wedding_id: UUID, body: IndexationAssumptionsIn, principal: CurrentPrincipal, db: DbSession
) -> IndexationAssumptions:
    expected, worst, saved = indexation.save_assumptions(
        db,
        principal,
        wedding_id,
        expected_rate=body.expected_rate,
        worst_rate=body.worst_rate,
    )
    return IndexationAssumptions(expected_rate=expected, worst_rate=worst, saved=saved)


@router.post(
    f"{W}/funders/{{funder_id}}/contributions/{{contribution_id}}/confirm",
    responses=_WRITE,
    summary="Potwierdzenie przelewu zgłoszonego przez sponsora",
)
def confirm_contribution(
    wedding_id: UUID,
    funder_id: UUID,
    contribution_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
) -> FunderDetail:
    funders.confirm_contribution(db, principal, wedding_id, funder_id, contribution_id)
    return _funder_detail(funders.get_detail(db, principal, wedding_id, funder_id))


@router.post(
    f"{W}/my-contribution/reports",
    status_code=201,
    responses={**_WRITE, 403: {"description": "Tylko rola sponsor"}},
    summary="Sponsor zgłasza przelew dla pary (czeka na potwierdzenie)",
)
def report_transfer(
    wedding_id: UUID, body: ContributionCreate, principal: CurrentPrincipal, db: DbSession
) -> FunderDetail:
    data = body.model_dump()
    data["amount"] = Decimal(data["amount"]["amount"])
    return _funder_detail(funders.report_transfer(db, principal, wedding_id, data))


def _money(value: Decimal) -> Money:
    return Money(amount=value)


@router.get(
    f"{W}/budget/cashflow",
    responses=_READ,
    summary="Plan wydatków po miesiącach i ile odkładać miesięcznie",
)
def budget_cashflow(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> Cashflow:
    o = insights.cashflow(db, principal, wedding_id)
    return Cashflow(
        months=[
            CashflowMonth(
                month=m["month"],
                couple=_money(m["couple"]),
                sponsors=_money(m["sponsors"]),
                total=_money(m["total"]),
            )
            for m in o["months"]
        ],
        overdue=_money(o["overdue"]),
        undated=_money(o["undated"]),
        not_scheduled=_money(o["not_scheduled"]),
        pledged_open=_money(o["pledged_open"]),
        couple_need=_money(o["couple_need"]),
        saving_months=o["saving_months"],
        saving_per_month=_money(o["saving_per_month"])
        if o["saving_per_month"] is not None
        else None,
        peak_month=o["peak_month"],
    )


@router.get(
    f"{W}/budget/guest-cost",
    responses=_READ,
    summary="Koszt jednego gościa: średni i każda kolejna osoba",
)
def budget_guest_cost(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> GuestCost:
    o = insights.guest_cost(db, principal, wedding_id)
    return GuestCost(
        average=_money(o["average"]) if o["average"] is not None else None,
        average_basis=o["average_basis"],
        adults=o["adults"],
        children=o["children"],
        per_adult=_money(o["per_adult"]),
        per_child=_money(o["per_child"]),
        sources=[
            GuestCostSource(
                name=s["name"], per_adult=_money(s["per_adult"]), per_child=_money(s["per_child"])
            )
            for s in o["sources"]
        ],
    )
