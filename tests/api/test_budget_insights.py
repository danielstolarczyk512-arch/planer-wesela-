"""Plan wydatków po miesiącach i koszt jednego gościa (N2, N3 z analizy 08)."""

from datetime import date

from app.core import clock
from tests.api.test_offers import SALA_A, offer, pln, vendor

API = "/api/v1"


def _wedding(client, alice, **kw):
    return client.post(
        f"{API}/weddings",
        headers=alice,
        json={"name": "Plan", "ceremony_type": "civil", "wedding_date": "2028-07-01", **kw},
    ).json()


def test_cashflow_months_overdue_sponsors_and_saving(client, alice, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2028, 1, 10))
    w = _wedding(client, alice)
    url = f"{API}/weddings/{w['id']}"
    cat = client.get(f"{url}/budget/categories", headers=alice).json()[0]["id"]
    item = client.post(
        f"{url}/budget/items",
        headers=alice,
        json={"category_id": cat, "name": "Sala", "planned": pln("30000")},
    ).json()
    pay = f"{url}/budget/items/{item['id']}/payments"
    funder = client.post(
        f"{url}/funders", headers=alice, json={"name": "Rodzice", "pledged_amount": pln("10000")}
    ).json()["funder"]
    for body in (
        {"kind": "advance_zaliczka", "amount": pln("5000"), "due_date": "2028-03-15"},
        {"kind": "installment", "amount": pln("3000"), "due_date": "2028-01-05"},
        {
            "kind": "installment",
            "amount": pln("4000"),
            "due_date": "2028-05-01",
            "funder_id": funder["id"],
        },
    ):
        assert client.post(pay, headers=alice, json=body).status_code == 201

    o = client.get(f"{url}/budget/cashflow", headers=alice).json()
    assert [m["month"] for m in o["months"]][:2] == ["2028-01-01", "2028-02-01"]
    assert len(o["months"]) == 7  # od stycznia do lipca
    march = next(m for m in o["months"] if m["month"] == "2028-03-01")
    may = next(m for m in o["months"] if m["month"] == "2028-05-01")
    assert march["couple"]["amount"] == "5000.00"
    assert (may["couple"]["amount"], may["sponsors"]["amount"]) == ("0.00", "4000.00")
    assert o["overdue"]["amount"] == "3000.00"
    assert o["not_scheduled"]["amount"] == "18000.00"
    assert o["pledged_open"]["amount"] == "6000.00"
    # Para: 5000 + 3000 zaplanowane + 18000 do zaplanowania minus 6000 jeszcze od rodziców.
    assert o["couple_need"]["amount"] == "20000.00"
    assert o["saving_months"] == 7
    assert o["saving_per_month"]["amount"] == "2857.14"
    assert o["peak_month"] == "2028-03-01"


def test_guest_cost_marginal_from_offer_and_items(client, alice):
    w = _wedding(client, alice)
    url = f"{API}/weddings/{w['id']}"
    h = client.post(f"{url}/households", headers=alice, json={"name": "Nowakowie"}).json()
    for name in ("Jan", "Ewa"):
        client.post(f"{url}/households/{h['id']}/guests", headers=alice, json={"first_name": name})
    sala = vendor(client, alice, w, "Sala")
    o = offer(client, alice, w, sala["id"], components=SALA_A)
    assert client.post(f"{url}/offers/{o['id']}/select", headers=alice, json={}).is_success
    cat = client.get(f"{url}/budget/categories", headers=alice).json()[0]["id"]
    client.post(
        f"{url}/budget/items",
        headers=alice,
        json={
            "category_id": cat,
            "name": "Tort",
            "cost_mode": "per_guest",
            "unit_price": pln("15"),
            "guest_basis": "invited",
        },
    )
    r = client.get(f"{url}/budget/guest-cost", headers=alice)
    assert r.status_code == 200, r.text
    c = r.json()
    assert (c["adults"], c["children"]) == (2, 0)
    # Menu 330 + poprawiny 150 z oferty + tort 15 za osobę.
    assert c["per_adult"]["amount"] == "495.00"
    assert {s["name"] for s in c["sources"]} == {"Pakiet", "Tort"}
    assert c["average"] is not None


def test_guest_cost_below_venue_minimum_is_free(client, alice):
    w = _wedding(client, alice)
    url = f"{API}/weddings/{w['id']}"
    sala = vendor(client, alice, w, "Sala")
    o = offer(client, alice, w, sala["id"], min_guests=80, components=SALA_A)
    assert client.post(f"{url}/offers/{o['id']}/select", headers=alice, json={}).is_success
    c = client.get(f"{url}/budget/guest-cost", headers=alice).json()
    # Poniżej minimum sali menu na przyjęciu nic nie dodaje (i tak płacicie za 80);
    # minimum nie obejmuje poprawin, więc zostaje ich cena za osobę.
    assert c["per_adult"]["amount"] == "150.00"
