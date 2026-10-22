"""Plan wydatków po miesiącach i koszt jednego gościa.

Plan wydatków (z perspektywy pary):
- zaplanowane płatności w każdym miesiącu do ślubu — osobno pary i sponsorów (płatność
  z przypisanym sponsorem płaci sponsor);
- płatności po terminie (niezapłacone, z datą w przeszłości) — osobna kwota „po terminie”;
- „do zaplanowania”: część kosztu, dla której nie ma jeszcze żadnej płatności;
- ile odkładać miesięcznie: to, co zostało parze (jej zaplanowane płatności + do zaplanowania
  minus to, co sponsorzy zadeklarowali, a jeszcze nie przypisali), podzielone na miesiące do ślubu.

Koszt gościa: średni (szacowany koszt ÷ goście) i krańcowy — o ile wzrośnie koszt, gdy
przyjdzie jedna dorosła osoba albo jedno dziecko więcej. Krańcowy liczymy wyceną ofert
(z minimum gości i ceną dziecięcą) oraz pozycjami budżetu „za osobę” spoza ofert.
"""

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.modules.budget import funders
from app.modules.budget import service as budget
from app.modules.budget.models import BudgetItem, Payment
from app.modules.identity.service import Principal
from app.modules.workspace.models import Wedding
from app.modules.workspace.permissions import Action, authorize

ZERO = Decimal("0")
CENT = Decimal("0.01")
MAX_MONTHS = 36


def _month(d: date) -> date:
    return d.replace(day=1)


def _add_month(d: date) -> date:
    return date(d.year + d.month // 12, d.month % 12 + 1, 1)


def months_between(start: date, end: date) -> list[date]:
    out: list[date] = []
    m = _month(start)
    while m <= _month(end) and len(out) < MAX_MONTHS:
        out.append(m)
        m = _add_month(m)
    return out


def cashflow(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    wedding = db.get_one(Wedding, wedding_id)
    today = clock.today()
    o = budget.overview(db, principal, wedding_id)
    payments = list(
        db.scalars(
            select(Payment).where(Payment.wedding_id == wedding_id, Payment.status == "scheduled")
        )
    )
    end = wedding.wedding_date or wedding.planned_month
    last_due = max((p.due_date for p in payments if p.due_date), default=None)
    horizon = max(d for d in (end, last_due, today) if d is not None)
    months = months_between(today, horizon)
    couple: dict[date, Decimal] = defaultdict(lambda: ZERO)
    sponsors: dict[date, Decimal] = defaultdict(lambda: ZERO)
    overdue = undated = ZERO
    for p in payments:
        if p.due_date is None:
            undated += p.amount
        elif p.due_date < today:
            overdue += p.amount
        else:
            (sponsors if p.funder_id else couple)[_month(p.due_date)] += p.amount
    scheduled_total = sum((p.amount for p in payments), ZERO)
    not_scheduled = max(o["remaining_to_pay"] - scheduled_total, ZERO)
    f = funders.overview(db, principal, wedding_id)
    pledged_open = sum(
        (x["to_settle"] for x in f["funders"] if x["to_settle"] and x["to_settle"] > 0), ZERO
    )
    couple_scheduled = sum((p.amount for p in payments if p.funder_id is None), ZERO)
    couple_need = max(couple_scheduled + not_scheduled - pledged_open, ZERO)
    saving_months = len(months_between(today, end)) if end and end >= today else 0
    return {
        "months": [
            {
                "month": m,
                "couple": couple[m],
                "sponsors": sponsors[m],
                "total": couple[m] + sponsors[m],
            }
            for m in months
        ],
        "overdue": overdue,
        "undated": undated,
        "not_scheduled": not_scheduled,
        "pledged_open": pledged_open,
        "couple_need": couple_need,
        "saving_months": saving_months,
        "saving_per_month": (couple_need / saving_months).quantize(CENT, ROUND_HALF_UP)
        if saving_months
        else None,
        "peak_month": max(months, key=lambda m: couple[m]) if any(couple.values()) else None,
    }


def guest_cost(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    from app.modules.offers import pricing
    from app.modules.offers import service as offers
    from app.modules.offers.models import Offer

    wedding = db.get_one(Wedding, wedding_id)
    counts = budget.guest_counts(db, wedding)
    basis = next((b for b in ("confirmed", "invited") if counts[b] > 0), None)
    adults = counts.get(f"{basis}_adults", 0) if basis else (wedding.guest_count_planned or 0)
    children = counts.get(f"{basis}_children", 0) if basis else 0
    o = budget.overview(db, principal, wedding_id)
    selected = list(
        db.scalars(select(Offer).where(Offer.wedding_id == wedding_id, Offer.status == "selected"))
    )
    comps = offers.components_of(db, [x.id for x in selected])
    per_adult = per_child = ZERO
    sources: list[dict[str, Any]] = []
    for offer in selected:
        components = offers.priced_components(comps[offer.id])
        minimum = offer.min_guests or None

        def total(a: int, c: int) -> Decimal:
            return pricing.quote(components, minimum, pricing.Scenario(adults=a, children=c)).total  # noqa: B023

        base = total(adults, children)
        add_adult, add_child = (
            total(adults + 1, children) - base,
            total(adults, children + 1) - base,
        )
        if add_adult or add_child:
            per_adult += add_adult
            per_child += add_child
            sources.append({"name": offer.title, "per_adult": add_adult, "per_child": add_child})
    offer_ids = {x.id for x in selected}
    for item in db.scalars(
        select(BudgetItem).where(
            BudgetItem.wedding_id == wedding_id,
            BudgetItem.cost_mode == "per_guest",
            BudgetItem.status != "cancelled",
            BudgetItem.unit_price.is_not(None),
        )
    ):
        if item.offer_id in offer_ids:
            continue  # już policzone wyceną oferty
        unit = item.unit_price or ZERO
        child = item.child_unit_price if item.child_unit_price is not None else unit
        per_adult += unit
        per_child += child
        sources.append({"name": item.name, "per_adult": unit, "per_child": child})
    return {
        "average": o["cost_per_guest"],
        "average_basis": o["cost_per_guest_basis"],
        "adults": adults,
        "children": children,
        "per_adult": per_adult.quantize(CENT, ROUND_HALF_UP),
        "per_child": per_child.quantize(CENT, ROUND_HALF_UP),
        "sources": sources,
    }
