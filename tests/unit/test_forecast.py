from datetime import date
from uuid import uuid4

from app.modules.guests.forecast import Person, estimate, reserve_invite_by, suggest
from app.modules.guests.models import ReserveEntry


def household(*statuses, age="adult"):
    h = uuid4()
    return [Person(h, s, age) for s in statuses]


def test_everyone_answered_gives_exact_number():
    people = household("attending", "attending") + household("declined")
    e = estimate(people, 0.85, 0.5)
    assert (e.expected, e.low, e.high) == (2, 2, 2)
    assert (e.attending, e.declined) == (2, 1)


def test_pending_and_maybe_use_rates_and_range():
    people = (
        household("attending", "attending")
        + household("pending", "pending")
        + household("pending", age="child")
        + household("maybe")
    )
    e = estimate(people, 0.85, 0.5)
    # 2 + 2·0,85 + 0,85 + 0,5 = 5,05
    assert e.expected == 5
    assert (e.expected_adults, e.expected_children) == (4, 1)
    # odchylenie: √(4·0,1275 + 0,1275 + 0,25) ≈ 0,94 → 5,05 ± 1,55
    assert (e.low, e.high) == (3, 6)  # górna granica przycięta do 6 możliwych osób


def test_household_decides_together_widens_range():
    together = household(*["pending"] * 6)
    separate = [p for _ in range(6) for p in household("pending")]
    wide, narrow = estimate(together, 0.8, 0.5), estimate(separate, 0.8, 0.5)
    assert wide.expected == narrow.expected
    assert wide.high - wide.low > narrow.high - narrow.low


def test_infants_are_outside_numbers():
    e = estimate(household("attending") + household("attending", age="infant"), 0.85, 0.5)
    assert (e.expected, e.infants) == (1, 1)


def test_empty_list():
    e = estimate([], 0.85, 0.5)
    assert (e.expected, e.low, e.high) == (0, 0, 0)


def test_reserve_invite_by_is_earlier_of_two_rules():
    assert reserve_invite_by(date(2027, 8, 1), None) == date(2027, 6, 20)
    assert reserve_invite_by(date(2027, 8, 1), date(2027, 6, 15)) == date(2027, 6, 8)
    assert reserve_invite_by(None, None) is None


def test_suggest_keeps_order_and_skips_too_big():
    entries = [ReserveEntry(name=n, persons=p) for n, p in (("A", 2), ("B", 4), ("C", 1))]
    assert [e.name for e in suggest(entries, 3)] == ["A", "C"]
    assert suggest(entries, 0) == []
