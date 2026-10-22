"""Strażnik waloryzacji: ile może kosztować wesele, jeśli umowy pozwalają podnieść cenę.

Salę i zespół rezerwuje się często 1,5-2 lata wcześniej, a umowy mają klauzule typu „cena
wg wskaźnika inflacji GUS” albo „wg cennika z roku wesela”. Liczymy trzy warianty:
- dziś: szacowany koszt bez podwyżek;
- prognoza: niezapłacona część pozycji z klauzulą rośnie o założoną inflację roczną
  przez lata od ustalenia ceny do ślubu; przy limicie — nie więcej niż limit;
- najgorszy przypadek: wyższa założona inflacja albo pełny limit.
Stopy to założenia pary (domyślnie 5% i 10% rocznie), nie dane GUS. Zapłacone kwoty są stałe.
"""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.modules.budget import service as budget
from app.modules.budget.models import BudgetItem
from app.modules.identity.service import Principal
from app.modules.workspace.models import Wedding
from app.modules.workspace.permissions import Action, authorize

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
DEFAULT_EXPECTED = 0.05
DEFAULT_WORST = 0.10
REVIEW_HORIZON_DAYS = 30


def years_between(start: date, end: date) -> Decimal:
    return (Decimal(max((end - start).days, 0)) / Decimal("365.25")).quantize(Decimal("0.01"))


def growth(rate: Decimal, years: Decimal) -> Decimal:
    """Łączny wzrost przy stopie rocznej (procent składany): (1 + r)^lata - 1."""
    return (1 + rate) ** years - 1


def increases(
    kind: str,
    remaining: Decimal,
    years: Decimal | None,
    cap_percent: Decimal | None,
    expected_rate: Decimal,
    worst_rate: Decimal,
) -> tuple[Decimal, Decimal]:
    """(podwyżka w prognozie, podwyżka w najgorszym przypadku) dla jednej pozycji."""
    if kind == "none" or years is None or remaining <= 0:
        return ZERO, ZERO
    expected = remaining * growth(expected_rate, years)
    worst = remaining * growth(worst_rate, years)
    if kind == "cap":
        limit = remaining * (cap_percent or ZERO) / 100
        expected, worst = min(expected, limit), limit
    return expected.quantize(CENT, ROUND_HALF_UP), worst.quantize(CENT, ROUND_HALF_UP)


def overview(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    *,
    expected_rate: float = DEFAULT_EXPECTED,
    worst_rate: float = DEFAULT_WORST,
) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    wedding = db.get_one(Wedding, wedding_id)
    day = wedding.wedding_date or wedding.planned_month
    counts = budget.guest_counts(db, wedding)
    items = list(
        db.scalars(
            select(BudgetItem)
            .where(BudgetItem.wedding_id == wedding_id)
            .order_by(BudgetItem.created_at)
        )
    )
    paid = budget.paid_by_item(db, [i.id for i in items])
    e_rate, w_rate = Decimal(str(expected_rate)), Decimal(str(worst_rate))
    today_total = expected_extra = worst_extra = ZERO
    rows: list[dict[str, Any]] = []
    for item in items:
        estimate, _ = budget.item_estimate(item, counts)
        today_total += estimate
        if item.indexation == "none" or item.status == "cancelled":
            continue
        remaining = max(estimate - paid[item.id], ZERO)
        start = item.price_fixed_on or item.created_at.date()
        years = years_between(start, day) if day else None
        exp, worst = increases(
            item.indexation, remaining, years, item.indexation_cap_percent, e_rate, w_rate
        )
        expected_extra += exp
        worst_extra += worst
        rows.append(
            {
                "item_id": item.id,
                "name": item.name,
                "indexation": item.indexation,
                "indexation_cap_percent": item.indexation_cap_percent,
                "price_fixed_on": item.price_fixed_on,
                "price_review_on": item.price_review_on,
                "remaining": remaining,
                "years": years,
                "expected_increase": exp,
                "worst_increase": worst,
            }
        )
    horizon = clock.today() + timedelta(days=REVIEW_HORIZON_DAYS)
    soon = [r for r in rows if (d := r["price_review_on"]) is not None and d <= horizon]
    return {
        "expected_rate": expected_rate,
        "worst_rate": worst_rate,
        "wedding_day": day,
        "approximate": wedding.wedding_date is None and day is not None,
        "today_total": today_total,
        "expected_total": today_total + expected_extra,
        "worst_total": today_total + worst_extra,
        "items": rows,
        "reviews_soon": soon,
    }


def reviews_due(db: Session, wedding_id: UUID, horizon: date) -> list[BudgetItem]:
    """Pozycje z terminem aneksu do `horizon` (podsumowanie e-mail)."""
    return list(
        db.scalars(
            select(BudgetItem)
            .where(
                BudgetItem.wedding_id == wedding_id,
                BudgetItem.indexation != "none",
                BudgetItem.price_review_on.is_not(None),
                BudgetItem.price_review_on <= horizon,
                BudgetItem.status != "cancelled",
            )
            .order_by(BudgetItem.price_review_on)
        )
    )
