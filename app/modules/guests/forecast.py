"""Prognoza frekwencji: ilu gości realnie przyjdzie i co to znaczy wobec umowy z salą.

Model (opisany też w raporcie `docs/gui/raport-prognoza-frekwencji.md`):
- potwierdzeni liczą się w całości, odmowy wcale, niemowlęta są poza liczbami (jak w wycenie);
- osoby „bez odpowiedzi” przyjdą z prawdopodobieństwem p, a „może” z prawdopodobieństwem q.
  To założenia pary (domyślnie 85% i 50%), a nie dane historyczne;
- gospodarstwo zwykle decyduje wspólnie, więc jego oczekujący to jedna decyzja z wagą równą
  liczbie osób. Wariancja = Σ n² · p · (1 - p), a przedział ok. 90% to ± 1,645 odchylenia,
  przycięty do wartości możliwych (od potwierdzonych do wszystkich, którzy nie odmówili).
Wszystko deterministycznie, bez AI.
"""

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.modules.guests.models import Guest, GuestEventAttendance, Household, ReserveEntry
from app.modules.identity.service import Principal
from app.modules.workspace.models import Event, Wedding
from app.modules.workspace.permissions import Action, authorize

Z_90 = 1.645
DEFAULT_PENDING_RATE = 0.85
DEFAULT_MAYBE_RATE = 0.5
# Zapraszanie z listy rezerwowej: najpóźniej 6 tygodni przed ślubem i tydzień przed terminem
# podania sali ostatecznej liczby (później zaproszenie wygląda na „last minute”).
RESERVE_WEEKS_BEFORE = 6
RESERVE_DAYS_BEFORE_FINAL = 7
FINAL_COUNT_TEMPLATE = "final_guest_count"
FINAL_COUNT_WARN_DAYS = 21
# Kolejność ważności statusów, gdy gość ma kilka wydarzeń typu „przyjęcie”.
_RANK = {"attending": 3, "maybe": 2, "pending": 1, "declined": 0}


@dataclass(frozen=True)
class Person:
    household_id: UUID
    status: str
    age_group: str
    guest_id: UUID | None = None


@dataclass(frozen=True)
class Estimate:
    attending: int
    declined: int
    maybe: int
    pending: int
    infants: int
    expected: int
    low: int
    high: int
    expected_adults: int
    expected_children: int


def estimate(people: list[Person], pending_rate: float, maybe_rate: float) -> Estimate:
    counted = [p for p in people if p.age_group != "infant"]
    by_status: dict[str, int] = defaultdict(int)
    for p in counted:
        by_status[p.status] += 1
    exp_adults = exp_children = 0.0
    open_by_household: dict[UUID, list[int]] = defaultdict(lambda: [0, 0])
    for p in counted:
        weight = {"attending": 1.0, "maybe": maybe_rate, "pending": pending_rate}.get(p.status, 0.0)
        if p.age_group == "child":
            exp_children += weight
        else:
            exp_adults += weight
        if p.status == "pending":
            open_by_household[p.household_id][0] += 1
        elif p.status == "maybe":
            open_by_household[p.household_id][1] += 1
    variance = sum(
        n_pending**2 * pending_rate * (1 - pending_rate)
        + n_maybe**2 * maybe_rate * (1 - maybe_rate)
        for n_pending, n_maybe in open_by_household.values()
    )
    sd = math.sqrt(variance)
    mean = exp_adults + exp_children
    attending = by_status["attending"]
    possible = attending + by_status["maybe"] + by_status["pending"]
    expected = round(mean)
    low = min(expected, max(attending, math.floor(mean - Z_90 * sd)))
    high = max(expected, min(possible, math.ceil(mean + Z_90 * sd)))
    expected_adults = min(expected, round(exp_adults))
    return Estimate(
        attending=attending,
        declined=by_status["declined"],
        maybe=by_status["maybe"],
        pending=by_status["pending"],
        infants=len(people) - len(counted),
        expected=expected,
        low=low,
        high=high,
        expected_adults=expected_adults,
        expected_children=expected - expected_adults,
    )


def reserve_invite_by(anchor: date | None, final_due: date | None) -> date | None:
    candidates = []
    if anchor:
        candidates.append(anchor - timedelta(weeks=RESERVE_WEEKS_BEFORE))
    if final_due:
        candidates.append(final_due - timedelta(days=RESERVE_DAYS_BEFORE_FINAL))
    return min(candidates) if candidates else None


def suggest(entries: list[ReserveEntry], free_places: int) -> list[ReserveEntry]:
    """Kolejno z listy, pomijając zaproszenia większe niż zostałe miejsca."""
    out, left = [], free_places
    for e in entries:
        if e.persons <= left:
            out.append(e)
            left -= e.persons
    return out


def _money(amount: Decimal) -> str:
    return f"{amount:,.0f}".replace(",", " ") + " zł"


def _statuses(db: Session, event_ids: list[UUID]) -> dict[UUID, str]:
    """Najważniejszy status gościa wśród podanych wydarzeń (brak wpisu = bez odpowiedzi)."""
    status: dict[UUID, str] = {}
    if event_ids:
        for guest_id, s in db.execute(
            select(GuestEventAttendance.guest_id, GuestEventAttendance.status).where(
                GuestEventAttendance.event_id.in_(event_ids)
            )
        ):
            if guest_id not in status or _RANK[s] > _RANK[status[guest_id]]:
                status[guest_id] = s
    return status


def _people(db: Session, wedding_id: UUID, events: list[Event]) -> list[Person]:
    reception = [e.id for e in events if e.kind == "reception"]
    considered = reception or [e.id for e in events if e.kind != "after_party"]
    status = _statuses(db, considered or [e.id for e in events])
    return [
        Person(g.household_id, status.get(g.id, "pending"), g.age_group, g.id)
        for g in db.scalars(select(Guest).where(Guest.wedding_id == wedding_id))
    ]


def _after_party(
    db: Session,
    events: list[Event],
    main: list[Person],
    pending_rate: float,
    maybe_rate: float,
) -> dict[str, Any] | None:
    """Poprawiny mają zwykle mniej gości i osobną cenę — liczymy je osobno.

    Ten sam model co dla przyjęcia; kto odmówił przyjęcia, nie przyjdzie też na poprawiny.
    """
    after = [e for e in events if e.kind == "after_party"]
    if not after or not any(e.kind != "after_party" for e in events):
        return None
    status = _statuses(db, [e.id for e in after])
    people = [
        Person(
            m.household_id,
            "declined" if m.status == "declined" else status.get(m.guest_id, "pending"),
            m.age_group,
        )
        for m in main
        if m.guest_id is not None
    ]
    est = estimate(people, pending_rate, maybe_rate)
    return {
        "event_name": after[0].name,
        "people": _people_out(est),
        "forecast": _forecast_out(est),
    }


def _people_out(est: Estimate) -> dict[str, int]:
    return {
        "attending": est.attending,
        "declined": est.declined,
        "maybe": est.maybe,
        "pending": est.pending,
        "infants": est.infants,
    }


def _forecast_out(est: Estimate) -> dict[str, int]:
    return {
        "expected": est.expected,
        "low": est.low,
        "high": est.high,
        "expected_adults": est.expected_adults,
        "expected_children": est.expected_children,
    }


def _venues(db: Session, wedding_id: UUID, est: Estimate) -> list[dict[str, Any]]:
    # Oferty zależą od gości (nie odwrotnie), więc import leniwy.
    from app.core.schemas import Money
    from app.modules.offers import pricing
    from app.modules.offers import service as offers
    from app.modules.offers.models import Offer
    from app.modules.vendors.models import Vendor

    rows = list(
        db.execute(
            select(Offer, Vendor.name)
            .join(Vendor, Vendor.id == Offer.vendor_id)
            .where(
                Offer.wedding_id == wedding_id,
                Offer.status == "selected",
                Offer.min_guests.is_not(None),
                Offer.min_guests > 0,
            )
            .order_by(Offer.created_at)
        )
    )
    comps = offers.components_of(db, [o.id for o, _ in rows])
    out = []
    for offer, vendor_name in rows:
        minimum = offer.min_guests or 0
        components = offers.priced_components(comps[offer.id])

        def unused(adults: int, children: int) -> Money | None:
            scenario = pricing.Scenario(adults=adults, children=children)
            with_min = pricing.quote(components, minimum, scenario).total  # noqa: B023
            without = pricing.quote(components, None, scenario).total  # noqa: B023
            return Money(amount=with_min - without) if with_min > without else None

        # Ostrożny wariant: ten sam udział dzieci co w prognozie.
        low_adults = round(est.low * est.expected_adults / est.expected) if est.expected else 0
        low_children = est.low - low_adults
        out.append(
            {
                "offer_id": offer.id,
                "offer_title": offer.title,
                "vendor_name": vendor_name,
                "min_guests": minimum,
                "shortfall_expected": max(0, minimum - est.expected_adults),
                "shortfall_low": max(0, minimum - low_adults),
                "unused_cost_expected": unused(est.expected_adults, est.expected_children),
                "unused_cost_low": unused(low_adults, low_children),
            }
        )
    return out


def _final_count(db: Session, wedding_id: UUID, today: date) -> dict[str, Any] | None:
    from app.modules.planner.models import Task

    task = db.scalars(
        select(Task)
        .where(
            Task.wedding_id == wedding_id,
            Task.template_code == FINAL_COUNT_TEMPLATE,
            Task.parent_task_id.is_(None),
        )
        .order_by(Task.created_at)
    ).first()
    if task is None:
        return None
    return {
        "task_id": task.id,
        "title": task.title,
        "due_date": task.due_date,
        "days_left": (task.due_date - today).days if task.due_date else None,
        "done": task.status == "done",
    }


def _overdue_households(
    db: Session, wedding_id: UUID, people: list[Person], today: date
) -> list[dict[str, Any]]:
    pending: dict[UUID, int] = defaultdict(int)
    for p in people:
        if p.status == "pending" and p.age_group != "infant":  # jak w prognozie
            pending[p.household_id] += 1
    households = db.scalars(
        select(Household)
        .where(
            Household.wedding_id == wedding_id,
            Household.rsvp_deadline.is_not(None),
            Household.rsvp_deadline < today,
        )
        .order_by(Household.rsvp_deadline, Household.name)
    )
    return [
        {
            "household_id": h.id,
            "name": h.name,
            "rsvp_deadline": h.rsvp_deadline,
            "pending": pending[h.id],
        }
        for h in households
        if pending[h.id]
    ][:20]


def build(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    *,
    pending_rate: float = DEFAULT_PENDING_RATE,
    maybe_rate: float = DEFAULT_MAYBE_RATE,
) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return compute(db, wedding_id, pending_rate=pending_rate, maybe_rate=maybe_rate)


# Alerty, które trafiają też do e-mailowego podsumowania (wymagają działania w terminie).
DIGEST_ALERTS = (
    "final_count.overdue",
    "final_count.soon",
    "venue.below_minimum",
    "guests.over_planned",
    "rsvp.overdue",
)


def digest_lines(db: Session, wedding_id: UUID) -> list[str]:
    """Wiersze do podsumowania e-mail (bez autoryzacji: wywołuje je zadanie workera)."""
    return [a["message"] for a in compute(db, wedding_id)["alerts"] if a["code"] in DIGEST_ALERTS]


def compute(
    db: Session,
    wedding_id: UUID,
    *,
    pending_rate: float = DEFAULT_PENDING_RATE,
    maybe_rate: float = DEFAULT_MAYBE_RATE,
) -> dict[str, Any]:
    from app.modules.planner.service import wedding_anchor

    wedding = db.get_one(Wedding, wedding_id)
    today = clock.today()
    events = list(
        db.scalars(select(Event).where(Event.wedding_id == wedding_id).order_by(Event.starts_at))
    )
    people = _people(db, wedding_id, events)
    est = estimate(people, pending_rate, maybe_rate)
    venues = _venues(db, wedding_id, est)
    final = _final_count(db, wedding_id, today)
    overdue = _overdue_households(db, wedding_id, people, today)
    waiting = list(
        db.scalars(
            select(ReserveEntry)
            .where(ReserveEntry.wedding_id == wedding_id, ReserveEntry.status == "waiting")
            .order_by(ReserveEntry.position, ReserveEntry.created_at)
        )
    )
    planned = wedding.guest_count_planned or None
    free_safe = planned - est.high if planned else None
    final_open = final is not None and not final["done"]
    invite_by = reserve_invite_by(
        wedding_anchor(wedding), final["due_date"] if final_open and final else None
    )
    too_late = invite_by is not None and today > invite_by
    suggestions = (
        suggest(waiting, free_safe) if free_safe and free_safe > 0 and not too_late else []
    )

    alerts: list[dict[str, str]] = []
    open_people = est.pending + est.maybe
    if final_open and final and final["days_left"] is not None:
        days = final["days_left"]
        if days < 0:
            alerts.append(
                {
                    "code": "final_count.overdue",
                    "message": f"Termin podania sali ostatecznej liczby gości minął "
                    f"{final['due_date']:%d.%m.%Y}.",
                }
            )
        elif days <= FINAL_COUNT_WARN_DAYS and open_people:
            alerts.append(
                {
                    "code": "final_count.soon",
                    "message": f"Za {days} dni sala czeka na ostateczną liczbę gości, a bez "
                    f"ostatecznej odpowiedzi jest jeszcze {open_people} os.",
                }
            )
    for v in venues:
        if v["shortfall_expected"]:
            cost = v["unused_cost_expected"]
            alerts.append(
                {
                    "code": "venue.below_minimum",
                    "message": f"Przy prognozie brakuje {v['shortfall_expected']} os. do minimum "
                    f"{v['min_guests']} w ofercie „{v['offer_title']}”"
                    + (f" — to ok. {_money(cost.amount)} za puste miejsca." if cost else "."),
                }
            )
    if planned and est.low > planned:
        alerts.append(
            {
                "code": "guests.over_planned",
                "message": f"Nawet przy ostrożnej prognozie przyjdzie więcej osób ({est.low}) "
                f"niż planowaliście ({planned}).",
            }
        )
    if overdue:
        alerts.append(
            {
                "code": "rsvp.overdue",
                "message": f"Zaproszenia po terminie odpowiedzi: {len(overdue)}. "
                "Warto zadzwonić i dopytać.",
            }
        )
    if waiting and too_late and invite_by:
        alerts.append(
            {
                "code": "reserve.late",
                "message": f"Minął zalecany termin zapraszania z listy rezerwowej "
                f"({invite_by:%d.%m.%Y}). Późne zaproszenie łatwo odebrać jako „zapchajdziurę”.",
            }
        )

    return {
        "pending_rate": pending_rate,
        "maybe_rate": maybe_rate,
        "people": _people_out(est),
        "forecast": _forecast_out(est),
        "after_party": _after_party(db, events, people, pending_rate, maybe_rate),
        "planned": planned,
        "free_places_safe": free_safe,
        "venues": venues,
        "final_count": final,
        "overdue_households": overdue,
        "reserve_waiting": sum(e.persons for e in waiting),
        "reserve_invite_by": invite_by,
        "suggestions": [
            {"entry_id": e.id, "name": e.name, "persons": e.persons} for e in suggestions
        ],
        "alerts": alerts,
    }
