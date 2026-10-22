"""Wycena oferty dla zadanego scenariusza gości. Deterministycznie, bez AI, tylko Decimal.

Reguły (opisane też w docs/etap-4-raport.md):
- `per_guest`: za osobę dorosłą; przy minimalnej liczbie gości rozliczane jest minimum.
  Jeśli oferta nie ma ceny dla dzieci (`per_child`) dla danego wydarzenia, dzieci liczone są
  jak dorośli i pojawia się ostrzeżenie.
- `per_child`: za dziecko. Niemowlęta (age_group=infant) nie są liczone, typowo bezpłatne.
- `per_crew`: za posiłek dla obsługi (muzycy, fotograf) x liczba osób obsługi w scenariuszu.
- `fixed`: kwota x ilość (domyślnie 1). `per_unit`: kwota x ilość (wymagana).
- `per_hour`: kwota x liczba godzin (z oferty lub scenariusza).
- `percent`: procent od sumy pozostałych pozycji (np. opłata serwisowa 10%).
- `included`: w cenie (informacyjnie, 0 zł). `optional`: tylko gdy include_optional.
- Brak kwoty: pozycja trafia do „nieznane”, nigdy nie jest liczona jako 0 zł.
- Pozycje z event_kind="after_party" liczone od liczby gości poprawin.
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


@dataclass(frozen=True)
class Component:
    label: str
    kind: str
    amount: Decimal | None
    quantity: Decimal | None = None
    included: bool = False
    optional: bool = False
    event_kind: str | None = None


@dataclass(frozen=True)
class Scenario:
    adults: int
    children: int = 0
    after_party_adults: int | None = None
    after_party_children: int | None = None
    hours: Decimal | None = None
    include_optional: bool = False
    crew: int = 0


@dataclass
class Line:
    label: str
    kind: str
    amount: Decimal
    quantity: Decimal
    subtotal: Decimal
    note: str | None = None


@dataclass
class Quote:
    total: Decimal
    lines: list[Line] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    optional_excluded: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def per_adult(self, adults: int) -> Decimal | None:
        return (self.total / adults).quantize(CENT, ROUND_HALF_UP) if adults > 0 else None


def _q(value: Decimal) -> Decimal:
    return value.quantize(CENT, ROUND_HALF_UP)


def quote(components: list[Component], min_guests: int | None, s: Scenario) -> Quote:
    result = Quote(total=ZERO)
    child_priced = {
        c.event_kind == "after_party"
        for c in components
        if c.kind == "per_child" and not c.included
    }
    after_adults = s.adults if s.after_party_adults is None else s.after_party_adults
    after_children = s.children if s.after_party_children is None else s.after_party_children
    warned_children: set[bool] = set()
    percent_items: list[Component] = []

    for c in components:
        if c.included:
            result.lines.append(
                Line(c.label, c.kind, c.amount or ZERO, Decimal(1), ZERO, "w cenie")
            )
            continue
        if c.optional and not s.include_optional:
            result.optional_excluded.append(c.label)
            continue
        if c.amount is None:
            result.unknown.append(c.label)
            continue
        if c.kind == "percent":
            percent_items.append(c)
            continue
        is_after = c.event_kind == "after_party"
        adults = after_adults if is_after else s.adults
        children = after_children if is_after else s.children
        note = None
        if c.kind == "per_guest":
            billed = adults
            if min_guests and not is_after and adults < min_guests:
                billed = min_guests
                note = f"minimum {min_guests} os."
                result.warnings.append(
                    f"offer.min_guests_not_met: minimum {min_guests} osób, "
                    f"rozliczenie wg {min_guests} zamiast {adults}"
                )
            if children and is_after not in child_priced:
                billed += children
                if is_after not in warned_children:
                    warned_children.add(is_after)
                    result.warnings.append(
                        "offer.no_child_price: brak ceny dla dzieci, liczone jak dorośli"
                    )
            qty = Decimal(billed)
        elif c.kind == "per_child":
            qty = Decimal(children)
        elif c.kind == "per_crew":
            qty = Decimal(s.crew)
        elif c.kind == "per_hour":
            hours = c.quantity if c.quantity is not None else s.hours
            if hours is None:
                result.unknown.append(f"{c.label} (brak liczby godzin)")
                continue
            qty = hours
        elif c.kind == "per_unit":
            if c.quantity is None:
                result.unknown.append(f"{c.label} (brak ilości)")
                continue
            qty = c.quantity
        else:  # fixed
            qty = c.quantity if c.quantity is not None else Decimal(1)
        subtotal = _q(c.amount * qty)
        result.lines.append(Line(c.label, c.kind, c.amount, qty, subtotal, note))
        result.total += subtotal

    base = result.total
    for c in percent_items:
        percent = c.amount or ZERO  # trafiają tu tylko pozycje z kwotą
        subtotal = _q(base * percent / 100)
        result.lines.append(
            Line(c.label, c.kind, percent, Decimal(1), subtotal, f"{percent}% od {base}")
        )
        result.total += subtotal
    result.total = _q(result.total)
    return result
