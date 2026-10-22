"""Silnik wyceny: każdy wynik sprawdzony ręcznym wyliczeniem (kryterium akceptacji Etapu 4)."""

from decimal import Decimal as D  # noqa: N817 - krótki alias czytelniejszy w wyliczeniach

from hypothesis import given
from hypothesis import strategies as st

from app.modules.offers.pricing import Component, Scenario, quote


def c(label, kind, amount, **kw):
    return Component(label=label, kind=kind, amount=None if amount is None else D(amount), **kw)


VENUE = [
    c("Menu", "per_guest", "330"),
    c("Dzieci", "per_child", "165"),
    c("Poprawiny", "per_guest", "150", event_kind="after_party"),
    c("Tort", "fixed", "800"),
    c("Obsługa", "percent", "10"),
    c("Napoje", "per_guest", "0", included=True),
    c("Fontanna czekoladowa", "fixed", "900", optional=True),
    c("Wiejski stół", "fixed", None),
]


def test_venue_quote_by_hand():
    # 100 dorosłych x 330 = 33 000; 8 dzieci x 165 = 1 320; poprawiny 60 x 150 = 9 000;
    # tort 800 → suma 44 120; obsługa 10% = 4 412 → razem 48 532.
    q = quote(
        VENUE,
        min_guests=80,
        s=Scenario(adults=100, children=8, after_party_adults=60, after_party_children=0),
    )
    assert q.total == D("48532.00")
    assert q.unknown == ["Wiejski stół"]
    assert q.optional_excluded == ["Fontanna czekoladowa"]
    assert q.warnings == []
    assert q.per_adult(100) == D("485.32")


def test_minimum_guests_billed_and_warned():
    # 60 dorosłych, minimum 80 → 80 x 330 = 26 400
    q = quote([c("Menu", "per_guest", "330")], 80, Scenario(adults=60))
    assert q.total == D("26400.00")
    assert q.warnings[0].startswith("offer.min_guests_not_met")


def test_children_without_child_price_billed_as_adults():
    # brak per_child → 10 dorosłych + 4 dzieci = 14 x 200 = 2 800
    q = quote([c("Menu", "per_guest", "200")], None, Scenario(adults=10, children=4))
    assert q.total == D("2800.00")
    assert any(w.startswith("offer.no_child_price") for w in q.warnings)


def test_optional_included_when_requested():
    q = quote(
        VENUE,
        80,
        Scenario(
            adults=100,
            children=8,
            after_party_adults=60,
            after_party_children=0,
            include_optional=True,
        ),
    )
    # 44 120 + 900 = 45 020; +10% = 4 502 → 49 522
    assert q.total == D("49522.00")


def test_hours_and_units():
    comps = [
        c("DJ", "per_hour", "500"),
        c("Krzesła", "per_unit", "12", quantity=D("110")),
        c("Nadgodzina", "per_hour", "400", quantity=D("2")),
    ]
    q = quote(comps, None, Scenario(adults=100, hours=D("8")))
    # 8 x 500 = 4 000; 110 x 12 = 1 320; 2 x 400 = 800 → 6 120
    assert q.total == D("6120.00")
    unknown = quote([c("DJ", "per_hour", "500")], None, Scenario(adults=1))
    assert unknown.total == D("0.00")
    assert unknown.unknown == ["DJ (brak liczby godzin)"]


def test_rounding_half_up_to_grosze():
    q = quote(
        [c("Menu", "per_guest", "99.99"), c("Serwis", "percent", "7.5")], None, Scenario(adults=3)
    )
    # 299.97; 7.5% = 22.49775 → 22.50; razem 322.47
    assert q.total == D("322.47")


@given(
    adults=st.integers(min_value=0, max_value=500),
    extra=st.integers(min_value=1, max_value=100),
    children=st.integers(min_value=0, max_value=50),
)
def test_total_monotonic_in_guests_and_non_negative(adults, extra, children):
    s1 = Scenario(adults=adults, children=children, after_party_adults=adults // 2)
    s2 = Scenario(adults=adults + extra, children=children, after_party_adults=adults // 2)
    q1, q2 = quote(VENUE, 80, s1), quote(VENUE, 80, s2)
    assert q1.total >= 0
    assert q2.total >= q1.total
