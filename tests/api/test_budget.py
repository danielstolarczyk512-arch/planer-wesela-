from datetime import date
from decimal import Decimal

from app.core import clock

API = "/api/v1"


def pln(amount: str) -> dict[str, str]:
    return {"amount": amount, "currency": "PLN"}


def category_id(client, headers, wedding, name):
    cats = client.get(f"{API}/weddings/{wedding['id']}/budget/categories", headers=headers)
    return next(c["id"] for c in cats.json() if c["name"] == name)


def add_guests(client, headers, wedding, n, attending_event=None):
    url = f"{API}/weddings/{wedding['id']}"
    h = client.post(f"{url}/households", headers=headers, json={"name": "Rodzina"}).json()
    ids = []
    for i in range(n):
        g = client.post(
            f"{url}/households/{h['id']}/guests", headers=headers, json={"first_name": f"Gość{i}"}
        ).json()
        ids.append(g["id"])
        if attending_event:
            client.put(
                f"{url}/guests/{g['id']}/attendance/{attending_event}",
                headers=headers,
                json={"status": "attending"},
            )
    return ids


def test_default_categories_and_split(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}/budget"
    cats = client.get(f"{url}/categories", headers=alice).json()
    assert len(cats) == 12
    assert any(c["is_reserve"] for c in cats)

    preview = client.post(f"{url}/apply-split", headers=alice, json={"dry_run": True}).json()
    sala = next(p for p in preview["proposals"] if p["name"] == "Sala i catering")
    assert sala["new_planned"] == pln("29250.00")  # 45% z 65 000
    total = sum(Decimal(p["new_planned"]["amount"]) for p in preview["proposals"])
    assert total == Decimal("65000.00")
    assert client.get(f"{url}/categories", headers=alice).json()[0]["planned"] == pln("0.00")

    client.post(f"{url}/apply-split", headers=alice, json={"dry_run": False})
    assert category_id(client, alice, wedding, "Sala i catering")
    planned = {
        c["name"]: c["planned"] for c in client.get(f"{url}/categories", headers=alice).json()
    }
    assert planned["Rezerwa"] == pln("6500.00")


def test_split_requires_total_budget(client, alice):
    w = client.post(f"{API}/weddings", headers=alice, json={"name": "Bez budżetu"}).json()
    r = client.post(
        f"{API}/weddings/{w['id']}/budget/apply-split", headers=alice, json={"dry_run": True}
    )
    assert r.status_code == 422
    assert r.json()["code"] == "budget.total_missing"


def test_per_guest_item_follows_guest_counts(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    event = client.post(
        f"{url}/events", headers=alice, json={"kind": "reception", "name": "Przyjęcie"}
    ).json()
    sala = category_id(client, alice, wedding, "Sala i catering")
    item = client.post(
        f"{url}/budget/items",
        headers=alice,
        json={
            "category_id": sala,
            "name": "Menu",
            "cost_mode": "per_guest",
            "unit_price": pln("330"),
            "guest_basis": "planned",
        },
    ).json()
    assert item["estimated"] == pln("36300.00")  # 330 zł x 110 planowanych
    assert item["guest_count_used"] == 110

    add_guests(client, alice, wedding, 3, attending_event=event["id"])
    r = client.patch(
        f"{url}/budget/items/{item['id']}",
        headers={**alice, "If-Match": '"1"'},
        json={"guest_basis": "confirmed"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["estimated"] == pln("990.00")
    # Kwota potwierdzona ma pierwszeństwo przed wyliczeniem.
    r = client.patch(
        f"{url}/budget/items/{item['id']}",
        headers={**alice, "If-Match": '"2"'},
        json={"confirmed": pln("1000")},
    )
    assert r.json()["estimated"] == pln("1000.00")


def test_item_validation(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}/budget/items"
    sala = category_id(client, alice, wedding, "Sala i catering")
    bad = [
        {"category_id": sala, "name": "X", "cost_mode": "fixed"},
        {"category_id": sala, "name": "X", "cost_mode": "per_guest", "unit_price": pln("1")},
        {"category_id": sala, "name": "X", "planned": pln("-5")},
        {"category_id": sala, "name": "X", "planned": pln("1.234")},
    ]
    for body in bad:
        assert client.post(url, headers=alice, json=body).status_code == 422, body


def test_payments_overview_and_overdue(client, alice, wedding, monkeypatch):
    url = f"{API}/weddings/{wedding['id']}"
    muzyka = category_id(client, alice, wedding, "Muzyka")
    item = client.post(
        f"{url}/budget/items",
        headers=alice,
        json={"category_id": muzyka, "name": "Zespół", "planned": pln("9000")},
    ).json()
    zadatek = client.post(
        f"{url}/budget/items/{item['id']}/payments",
        headers=alice,
        json={"kind": "deposit_zadatek", "amount": pln("2000"), "due_date": "2027-01-10"},
    ).json()
    client.post(
        f"{url}/budget/items/{item['id']}/payments",
        headers=alice,
        json={"kind": "final", "amount": pln("7000"), "due_date": "2027-08-01"},
    )
    assert zadatek["status"] == "scheduled"

    monkeypatch.setattr(clock, "today", lambda: date(2027, 1, 15))
    overview = client.get(f"{url}/budget/overview", headers=alice).json()
    assert overview["estimated_total"] == pln("9000.00")
    assert overview["paid_total"] == pln("0.00")
    assert [p["kind"] for p in overview["overdue_payments"]] == ["deposit_zadatek"]
    assert overview["unallocated"] == pln("56000.00")
    assert overview["over_budget"] is False

    r = client.post(f"{url}/payments/{zadatek['id']}/mark-paid", headers=alice, json={})
    assert r.json()["status"] == "paid"
    assert r.json()["paid_on"] == "2027-01-15"
    overview = client.get(f"{url}/budget/overview", headers=alice).json()
    assert overview["paid_total"] == pln("2000.00")
    assert overview["remaining_to_pay"] == pln("7000.00")
    assert overview["overdue_payments"] == []
    schedule = client.get(f"{url}/payments/schedule", headers=alice).json()
    assert [p["kind"] for p in schedule] == ["deposit_zadatek", "final"]

    history = client.get(f"{url}/budget/history", headers=alice).json()
    assert {"mark_paid", "create"} <= {h["action"] for h in history}


def test_over_budget_and_cancelled_items(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    sala = category_id(client, alice, wedding, "Sala i catering")
    item = client.post(
        f"{url}/budget/items",
        headers=alice,
        json={"category_id": sala, "name": "Pałac", "planned": pln("70000")},
    ).json()
    assert client.get(f"{url}/budget/overview", headers=alice).json()["over_budget"] is True
    client.patch(
        f"{url}/budget/items/{item['id']}",
        headers={**alice, "If-Match": '"1"'},
        json={"status": "cancelled"},
    )
    assert client.get(f"{url}/budget/overview", headers=alice).json()["over_budget"] is False


def test_category_rules(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}/budget"
    r = client.post(f"{url}/categories", headers=alice, json={"name": "muzyka"})
    assert r.status_code == 409
    new = client.post(
        f"{url}/categories",
        headers=alice,
        json={"name": "Wieczór panieński", "planned": pln("800")},
    ).json()
    client.post(
        f"{url}/items",
        headers=alice,
        json={"category_id": new["id"], "name": "Bilety", "planned": pln("300")},
    )
    r = client.delete(f"{url}/categories/{new['id']}", headers=alice)
    assert r.status_code == 409
    assert r.json()["code"] == "budget.category_not_empty"


def test_payment_validation_and_version(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    cat = category_id(client, alice, wedding, "Inne")
    item = client.post(
        f"{url}/budget/items",
        headers=alice,
        json={"category_id": cat, "name": "X", "planned": pln("100")},
    ).json()
    r = client.post(
        f"{url}/budget/items/{item['id']}/payments",
        headers=alice,
        json={"kind": "other", "amount": pln("0")},
    )
    assert r.status_code == 422
    r = client.post(
        f"{url}/budget/items/{item['id']}/payments",
        headers=alice,
        json={"kind": "zadatek", "amount": pln("10")},
    )
    assert r.status_code == 422
    p = client.post(
        f"{url}/budget/items/{item['id']}/payments",
        headers=alice,
        json={"kind": "advance_zaliczka", "amount": pln("10")},
    ).json()
    stale = client.patch(
        f"{url}/payments/{p['id']}", headers={**alice, "If-Match": '"9"'}, json={"notes": "x"}
    )
    assert stale.status_code == 409
    ok = client.patch(
        f"{url}/payments/{p['id']}",
        headers={**alice, "If-Match": '"1"'},
        json={"status": "cancelled"},
    )
    assert ok.json()["status"] == "cancelled"
    assert (
        client.post(f"{url}/payments/{p['id']}/mark-paid", headers=alice, json={}).status_code
        == 409
    )


def test_per_guest_item_with_child_price(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    sala = category_id(client, alice, wedding, "Sala i catering")
    h = client.post(f"{url}/households", headers=alice, json={"name": "Nowakowie"}).json()
    for first, age in (
        ("Jan", "adult"),
        ("Ewa", "adult"),
        ("Ola", "teen"),
        ("Zosia", "child"),
        ("Kuba", "infant"),
    ):
        client.post(
            f"{url}/households/{h['id']}/guests",
            headers=alice,
            json={"first_name": first, "age_group": age},
        )
    r = client.post(
        f"{url}/budget/items",
        headers=alice,
        json={
            "category_id": sala,
            "name": "Menu",
            "cost_mode": "per_guest",
            "unit_price": pln("300"),
            "child_unit_price": pln("150"),
            "guest_basis": "invited",
        },
    )
    assert r.status_code == 201, r.text
    item = r.json()
    # 3 dorosłych (z nastolatką) x 300 + 1 dziecko x 150; maluch bez opłaty.
    assert item["estimated"] == pln("1050.00")
    assert (item["guest_count_used"], item["children_used"]) == (4, 1)
    assert item["child_unit_price"] == pln("150.00")

    # Liczba planowana nie zna wieku gości: cena dziecięca nie działa.
    r = client.patch(
        f"{url}/budget/items/{item['id']}",
        headers={**alice, "If-Match": '"1"'},
        json={"guest_basis": "planned"},
    )
    assert r.json()["estimated"] == pln("33000.00")  # 300 zł x 110 planowanych
    assert r.json()["children_used"] is None

    # Bez ceny dziecięcej — wszyscy zaproszeni po cenie pełnej (jak dotąd, z maluchem).
    r = client.patch(
        f"{url}/budget/items/{item['id']}",
        headers={**alice, "If-Match": '"2"'},
        json={"guest_basis": "invited", "child_unit_price": None},
    )
    assert r.json()["estimated"] == pln("1500.00")
    bad = client.post(
        f"{url}/budget/items",
        headers=alice,
        json={
            "category_id": sala,
            "name": "X",
            "cost_mode": "per_guest",
            "unit_price": pln("1"),
            "child_unit_price": pln("-5"),
            "guest_basis": "invited",
        },
    )
    assert bad.status_code == 422


def test_budget_csv_export_items_and_payments(client, alice, bob, wedding, monkeypatch):
    import csv
    import io

    url = f"{API}/weddings/{wedding['id']}"
    muzyka = category_id(client, alice, wedding, "Muzyka")
    sala = category_id(client, alice, wedding, "Sala i catering")
    item = client.post(
        f"{url}/budget/items",
        headers=alice,
        json={"category_id": muzyka, "name": "=Zespół", "planned": pln("9000.50")},
    ).json()
    client.post(
        f"{url}/budget/items",
        headers=alice,
        json={
            "category_id": sala,
            "name": "Menu",
            "cost_mode": "per_guest",
            "unit_price": pln("250"),
            "guest_basis": "invited",
        },
    )
    add_guests(client, alice, wedding, 3)
    zadatek = client.post(
        f"{url}/budget/items/{item['id']}/payments",
        headers=alice,
        json={"kind": "deposit_zadatek", "amount": pln("2000"), "due_date": "2027-01-10"},
    ).json()
    client.post(f"{url}/payments/{zadatek['id']}/mark-paid", headers=alice, json={})

    def rows(part: str) -> list[list[str]]:
        r = client.get(f"{url}/budget/export.csv", headers=alice, params={"part": part})
        assert r.status_code == 200, r.text
        assert r.content.startswith("﻿".encode())
        return list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))

    items = rows("items")
    assert items[0][:3] == ["Kategoria", "Pozycja", "Koszt"]
    # Kolejność kategorii jak w aplikacji; kwoty z przecinkiem; formuła zneutralizowana.
    assert [r[1] for r in items[1:]] == ["Menu", "'=Zespół"]
    menu, zespol = items[1], items[2]
    assert menu[2:5] == ["za osobę (zaproszeni)", "250,00", "3"]
    assert menu[8] == "750,00"
    assert zespol[5] == "9000,50"
    assert zespol[9:12] == ["2000,00", "7000,50", "planowana"]

    monkeypatch.setattr(clock, "today", lambda: date(2027, 1, 15))
    payments = rows("payments")
    assert payments[0][:4] == ["Pozycja", "Kategoria", "Rodzaj", "Kwota (zł)"]
    assert payments[1][:6] == [
        "'=Zespół",
        "Muzyka",
        "zadatek",
        "2000,00",
        "2027-01-10",
        "zapłacona",
    ]

    assert client.get(f"{url}/budget/export.csv", headers=bob).status_code == 404
    assert (
        client.get(f"{url}/budget/export.csv", headers=alice, params={"part": "x"}).status_code
        == 422
    )
