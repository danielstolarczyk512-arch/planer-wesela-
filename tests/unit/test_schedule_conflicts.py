from datetime import UTC, datetime, timedelta
from uuid import uuid4

from hypothesis import given
from hypothesis import strategies as st

from app.modules.schedule.conflicts import Item, detect, shifted

T0 = datetime(2027, 8, 21, 13, 0, tzinfo=UTC)


def item(title, minute, duration, **kw):
    return Item(
        id=kw.pop("id", uuid4()),
        title=title,
        starts_at=T0 + timedelta(minutes=minute),
        duration_minutes=duration,
        **kw,
    )


def codes(items):
    return sorted(c.code for c in detect(items))


def test_vendor_in_two_places_with_travel_buffer():
    band = uuid4()
    church = item("Oprawa ceremonii", 0, 60, vendor_id=band, buffer_after_minutes=30)
    venue = item("Powitanie na sali", 75, 30, vendor_id=band)
    # koniec 14:00 + 30 min dojazdu = 14:30 > start 14:15 → konflikt
    assert codes([church, venue]) == ["vendor_double_booked"]
    later = item("Powitanie na sali", 95, 30, vendor_id=band)
    assert codes([church, later]) == []


def test_adjacent_items_do_not_conflict():
    p = "kasia"
    assert codes([item("A", 0, 30, person=p), item("B", 30, 30, person=p)]) == []
    assert codes([item("A", 0, 31, person=p), item("B", 30, 30, person=p)]) == [
        "person_double_booked"
    ]


def test_dependency_order_and_event_window_and_not_booked():
    ceremony = item("Ceremonia", 0, 60, buffer_after_minutes=10)
    wishes = item("Życzenia", 65, 30, depends_on=(ceremony.id,))
    assert codes([ceremony, wishes]) == ["dependency_order"]
    early = item("Pierwszy taniec", -30, 10, event_window=(T0, T0 + timedelta(hours=8)))
    assert codes([early]) == ["outside_event"]
    assert codes([item("DJ", 0, 10, vendor_id=uuid4(), vendor_booked=False)]) == [
        "vendor_not_booked"
    ]


def test_shift_moves_only_later_items():
    a, b, c = item("A", 0, 10), item("B", 60, 10), item("C", 120, 10)
    moved = shifted([a, b, c], b.starts_at, 30)
    assert set(moved) == {b.id, c.id}
    assert moved[b.id] == b.starts_at + timedelta(minutes=30)


@given(
    st.lists(st.tuples(st.integers(0, 600), st.integers(0, 120)), max_size=8),
    st.integers(-300, 300),
)
def test_uniform_shift_preserves_conflicts(spec, minutes):
    person = "ola"
    items = [item(f"P{i}", m, d, person=person) for i, (m, d) in enumerate(spec)]
    before = codes(items)
    start = min((i.starts_at for i in items), default=T0)
    moved = shifted(items, start, minutes)
    after_items = [
        Item(
            id=i.id,
            title=i.title,
            starts_at=moved.get(i.id, i.starts_at),
            duration_minutes=i.duration_minutes,
            person=i.person,
        )
        for i in items
    ]
    assert codes(after_items) == before
