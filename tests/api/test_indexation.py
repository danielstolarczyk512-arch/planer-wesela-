"""Strażnik waloryzacji cen (propozycja 1 z docs/analysis/05)."""

from datetime import date
from decimal import Decimal

from app.core import clock
from app.modules.budget.indexation import growth, increases, years_between
from tests.api.test_offers import pln
from tests.api.test_workspace import invite_and_accept

API = "/api/v1"


def test_math():
    assert years_between(date(2026, 7, 1), date(2028, 7, 1)) == Decimal("2.00")
    assert years_between(date(2029, 1, 1), date(2028, 7, 1)) == Decimal("0.00")
    assert growth(Decimal("0.05"), Decimal("2")).quantize(Decimal("0.0001")) == Decimal("0.1025")
    # Inflacja: 40 000 zł przez 2 lata (5% / 10%).
    assert increases(
        "cpi", Decimal("40000"), Decimal("2"), None, Decimal("0.05"), Decimal("0.10")
    ) == (Decimal("4100.00"), Decimal("8400.00"))
    # Limit 6% łącznie: prognoza nie więcej niż limit, najgorszy przypadek = limit.
    assert increases(
        "cap", Decimal("40000"), Decimal("2"), Decimal("6"), Decimal("0.05"), Decimal("0.10")
    ) == (Decimal("2400.00"), Decimal("2400.00"))
    assert increases(
        "none", Decimal("40000"), Decimal("2"), None, Decimal("0.05"), Decimal("0.1")
    ) == (
        Decimal("0.00"),
        Decimal("0.00"),
    )
    assert increases("cpi", Decimal("100"), None, None, Decimal("0.05"), Decimal("0.1"))[0] == 0


def test_overview_three_variants_and_reviews(client, alice, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2026, 10, 22))
    w = client.post(
        f"{API}/weddings",
        headers=alice,
        json={"name": "W", "ceremony_type": "civil", "wedding_date": "2028-07-01"},
    ).json()
    url = f"{API}/weddings/{w['id']}"
    cat = client.get(f"{url}/budget/categories", headers=alice).json()[0]["id"]
    sala = client.post(
        f"{url}/budget/items",
        headers=alice,
        json={
            "category_id": cat,
            "name": "Sala",
            "planned": pln("50000"),
            "indexation": "cpi",
            "price_fixed_on": "2026-07-01",
            "price_review_on": "2026-11-10",
        },
    )
    assert sala.status_code == 201, sala.text
    assert sala.json()["indexation"] == "cpi"
    # Zadatek zapłacony: tej części podwyżka nie obejmie.
    client.post(
        f"{url}/budget/items/{sala.json()['id']}/payments",
        headers=alice,
        json={"kind": "deposit_zadatek", "amount": pln("10000"), "paid_on": "2026-07-01"},
    )
    bad = client.post(
        f"{url}/budget/items",
        headers=alice,
        json={"category_id": cat, "name": "Zespół", "planned": pln("12000"), "indexation": "cap"},
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "budget.indexation_cap"
    client.post(
        f"{url}/budget/items",
        headers=alice,
        json={
            "category_id": cat,
            "name": "Zespół",
            "planned": pln("12000"),
            "indexation": "cap",
            "indexation_cap_percent": "5",
            "price_fixed_on": "2026-07-01",
        },
    )
    client.post(
        f"{url}/budget/items",
        headers=alice,
        json={"category_id": cat, "name": "Obrączki", "planned": pln("4000")},
    )

    r = client.get(f"{url}/budget/indexation", headers=alice)
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["today_total"] == pln("66000.00")
    assert [i["name"] for i in o["items"]] == ["Sala", "Zespół"]
    s = o["items"][0]
    assert s["remaining"] == pln("40000.00")
    assert s["years"] == "2.00"
    assert s["expected_increase"] == pln("4100.00")
    assert s["worst_increase"] == pln("8400.00")
    band = o["items"][1]
    assert band["worst_increase"] == pln("600.00")  # 5% z 12 000 zł
    assert o["expected_total"] == pln("70700.00")  # 66 000 + 4 100 + 600
    assert o["worst_total"] == pln("75000.00")  # 66 000 + 8 400 + 600
    assert [i["name"] for i in o["reviews_soon"]] == ["Sala"]
    # Założenia pary zmieniają prognozę; zła stopa jest odrzucana.
    zero = client.get(f"{url}/budget/indexation?expected_rate=0&worst_rate=0", headers=alice)
    assert zero.json()["expected_total"] == pln("66000.00")
    assert client.get(f"{url}/budget/indexation?worst_rate=2", headers=alice).status_code == 422


def test_assumptions_saved_on_wedding(client, alice, bob):
    w = client.post(
        f"{API}/weddings",
        headers=alice,
        json={"name": "W", "ceremony_type": "civil", "wedding_date": "2028-07-01"},
    ).json()
    url = f"{API}/weddings/{w['id']}/budget/indexation"
    first = client.get(url, headers=alice).json()
    assert first["assumptions"] == {"expected_rate": 0.05, "worst_rate": 0.1, "saved": False}
    assert (first["expected_rate"], first["worst_rate"]) == (0.05, 0.1)

    r = client.put(
        f"{url}/assumptions", headers=alice, json={"expected_rate": 0.07, "worst_rate": 0.15}
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"expected_rate": 0.07, "worst_rate": 0.15, "saved": True}
    # Bez parametrów liczymy wg zapisanych; parametry to podgląd innego wariantu bez zapisu.
    saved = client.get(url, headers=alice).json()
    assert (saved["expected_rate"], saved["worst_rate"]) == (0.07, 0.15)
    peek = client.get(f"{url}?expected_rate=0.03", headers=alice).json()
    assert (peek["expected_rate"], peek["worst_rate"]) == (0.03, 0.15)
    assert peek["assumptions"]["expected_rate"] == 0.07

    bad = client.put(
        f"{url}/assumptions", headers=alice, json={"expected_rate": 0.7, "worst_rate": 0.1}
    )
    assert bad.status_code == 422
    # Osoba z podglądem widzi założenia, ale ich nie zmienia.
    invite_and_accept(client, alice, bob, w, "bob@example.com", "viewer")
    assert client.get(url, headers=bob).json()["assumptions"]["saved"] is True
    denied = client.put(
        f"{url}/assumptions", headers=bob, json={"expected_rate": 0.03, "worst_rate": 0.08}
    )
    assert denied.status_code == 403
