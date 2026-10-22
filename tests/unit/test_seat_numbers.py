"""Numery miejsc przy stole: rodziny obok siebie, para razem, dzieci przy rodzicu."""

from uuid import UUID, uuid4

import pytest

from app.modules.seating.engine import G, SeatingError, number_seats, seat_order


def family(name: str, *people: tuple[str, str]) -> list[G]:
    hid = uuid4()
    return [
        G(id=uuid4(), household_id=hid, age_group=age, name=f"{first} {name}")
        for first, age in people
    ]


def seats_of(guests: list[G], numbers: dict[UUID, int]) -> list[int]:
    return [numbers[g.id] for g in guests]


def adjacent(a: int, b: int, capacity: int) -> bool:
    return abs(a - b) == 1 or {a, b} == {1, capacity}


def test_family_together_adults_first_then_children():
    kowalscy = family("Kowalski", ("Zosia", "child"), ("Anna", "adult"), ("Jan", "adult"))
    nowak = family("Nowak", ("Ewa", "adult"))
    order = seat_order(kowalscy + nowak)
    assert [g.name for g in order[:3]] == ["Anna Kowalski", "Jan Kowalski", "Zosia Kowalski"]
    numbers = number_seats(kowalscy + nowak, capacity=8)
    anna, zosia, jan = (numbers[g.id] for g in kowalscy[1:2] + kowalscy[:1] + kowalscy[2:])
    assert adjacent(anna, jan, 8)  # para obok siebie
    assert adjacent(zosia, jan, 8) or adjacent(zosia, anna, 8)  # dziecko przy rodzicu
    assert sorted(numbers.values()) == [1, 2, 3, 4]


def test_keeps_existing_numbers_and_fills_largest_gap_with_family():
    a = family("A", ("Ala", "adult"))
    b = family("B", ("Bartek", "adult"))
    c = family("C", ("Cela", "adult"), ("Czesio", "adult"), ("Cyryl", "child"))
    existing = {a[0].id: 2, b[0].id: 4}  # wolne: 1, 3, 5, 6, 7, 8
    numbers = number_seats(a + b + c, capacity=8, existing=existing)
    assert numbers[a[0].id] == 2
    assert numbers[b[0].id] == 4
    # Rodzina C w ciągłym bloku 5-6-7 (nie rozbita przez zajęte 2 i 4).
    assert sorted(seats_of(c, numbers)) == [5, 6, 7]


def test_round_table_wraps_around():
    a = family("A", ("Ala", "adult"))
    b = family("B", ("Basia", "adult"), ("Bolek", "adult"), ("Bartek", "child"))
    numbers = number_seats(a + b, capacity=4, existing={a[0].id: 3})
    # Wolne 4, 1, 2 tworzą jeden ciąg przez „szew” stołu.
    assert sorted(seats_of(b, numbers)) == [1, 2, 4]


def test_too_many_people_and_duplicate_numbers():
    a = family("A", ("Ala", "adult"), ("Adam", "adult"), ("Ania", "adult"))
    with pytest.raises(SeatingError):
        number_seats(a, capacity=2)
    x = family("X", ("Xenia", "adult"))
    y = family("Y", ("Yvette", "adult"))
    numbers = number_seats(x + y, capacity=4, existing={x[0].id: 1, y[0].id: 1})
    assert sorted(numbers.values()) == [1, 2]
