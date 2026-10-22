"""Portfel sponsorów i rola „sponsor” (propozycja 6 z docs/analysis/05)."""

from tests.api.test_offers import pln
from tests.api.test_workspace import invite_and_accept

API = "/api/v1"


def item_with_payments(client, headers, url):
    cats = client.get(f"{url}/budget/categories", headers=headers).json()
    item = client.post(
        f"{url}/budget/items",
        headers=headers,
        json={"name": "Sala", "category_id": cats[0]["id"], "planned": pln("40000")},
    ).json()
    return item


def test_funders_summary_payments_and_contributions(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    r = client.post(
        f"{url}/funders",
        headers=alice,
        json={"name": "Rodzice Panny Młodej", "side": "bride", "pledged_amount": pln("20000")},
    )
    assert r.status_code == 201, r.text
    parents = r.json()["funder"]
    item = item_with_payments(client, alice, url)
    pay = f"{url}/budget/items/{item['id']}/payments"
    paid = client.post(
        pay,
        headers=alice,
        json={
            "kind": "deposit_zadatek",
            "amount": pln("5000"),
            "paid_on": "2026-10-01",
            "funder_id": parents["id"],
        },
    )
    assert paid.status_code == 201, paid.text
    assert paid.json()["funder_id"] == parents["id"]
    later = client.post(
        pay,
        headers=alice,
        json={"kind": "final", "amount": pln("8000"), "due_date": "2027-07-01"},
    ).json()
    # Para przypisuje drugą płatność rodzicom (PATCH z If-Match).
    moved = client.patch(
        f"{url}/payments/{later['id']}",
        headers={**alice, "If-Match": f'"{later["version"]}"'},
        json={"funder_id": parents["id"]},
    )
    assert moved.status_code == 200, moved.text
    gift = client.post(
        f"{url}/funders/{parents['id']}/contributions",
        headers=alice,
        json={"amount": pln("3000"), "received_on": "2026-09-15", "note": "Przelew na konto"},
    )
    assert gift.status_code == 201, gift.text
    client.post(
        pay, headers=alice, json={"kind": "other", "amount": pln("1000"), "paid_on": "2026-10-02"}
    )

    o = client.get(f"{url}/funders", headers=alice).json()
    f = o["funders"][0]
    assert f["paid_direct"] == pln("5000.00")
    assert f["scheduled_direct"] == pln("8000.00")
    assert f["given"] == pln("3000.00")
    assert f["covered"] == pln("8000.00")
    assert f["to_settle"] == {"amount": "4000.00", "currency": "PLN"}  # 20 000 - 16 000
    assert o["couple_paid"] == pln("1000.00")
    assert o["pledged_total"] == pln("20000.00")

    detail = client.get(f"{url}/funders/{parents['id']}", headers=alice).json()
    assert [p["item_name"] for p in detail["payments"]] == ["Sala", "Sala"]
    assert detail["contributions"][0]["note"] == "Przelew na konto"

    # Płatność przypisana do sponsora z innego wesela jest odrzucana.
    bad = client.post(
        pay,
        headers=alice,
        json={
            "kind": "other",
            "amount": pln("1"),
            "funder_id": "0192aaaa-0000-7000-8000-000000000000",
        },
    )
    assert bad.status_code == 404
    assert bad.json()["code"] == "funder.not_found"

    # Usunięcie sponsora: płatności wracają do pary.
    assert client.delete(f"{url}/funders/{parents['id']}", headers=alice).status_code == 204
    o = client.get(f"{url}/funders", headers=alice).json()
    assert o["funders"] == []
    assert o["couple_paid"] == pln("6000.00")


def test_sponsor_sees_only_own_contribution(client, alice, user_factory, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    mine = client.post(
        f"{url}/funders", headers=alice, json={"name": "Rodzice Pana Młodego"}
    ).json()
    other = client.post(f"{url}/funders", headers=alice, json={"name": "Dziadkowie"}).json()
    item = item_with_payments(client, alice, url)
    client.post(
        f"{url}/budget/items/{item['id']}/payments",
        headers=alice,
        json={
            "kind": "final",
            "amount": pln("7000"),
            "due_date": "2027-07-01",
            "funder_id": mine["funder"]["id"],
        },
    )

    # Zaproszenie sponsora wymaga wskazania wkładu.
    no_funder = client.post(
        f"{url}/invitations", headers=alice, json={"email": "tata@example.com", "role": "sponsor"}
    )
    assert no_funder.status_code == 422
    assert no_funder.json()["code"] == "member.funder_required"

    dad = user_factory("tata@example.com")
    invite_and_accept(
        client,
        alice,
        dad,
        wedding,
        "tata@example.com",
        role="sponsor",
        funder_id=mine["funder"]["id"],
    )
    w = client.get(url, headers=dad).json()
    assert w["my_role"] == "sponsor"
    assert w["total_budget"] is None  # sponsor nie widzi budżetu wesela
    my = client.get(f"{url}/my-contribution", headers=dad)
    assert my.status_code == 200, my.text
    assert my.json()["funder"]["name"] == "Rodzice Pana Młodego"
    assert my.json()["payments"][0]["amount"] == pln("7000.00")

    # Reszta wesela jest niedostępna (403), cudzy wkład też.
    for path in ("funders", "budget/items", "households", "guests/stats", "schedule", "summary"):
        assert client.get(f"{url}/{path}", headers=dad).status_code == 403, path
    assert client.get(f"{url}/funders/{other['funder']['id']}", headers=dad).status_code == 403
    # Para nie ma przypisanego wkładu: „mój wkład” nie istnieje.
    own = client.get(f"{url}/my-contribution", headers=alice)
    assert (own.status_code, own.json()["code"]) == (404, "funder.not_assigned")
    # Sponsor może sam opuścić wesele.
    me = client.get(f"{API}/me", headers=dad).json()
    assert client.delete(f"{url}/members/{me['id']}", headers=dad).status_code == 204


def test_role_change_to_sponsor_needs_funder(client, alice, bob, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    invite_and_accept(client, alice, bob, wedding, "bob@example.com", role="viewer")
    bob_id = client.get(f"{API}/me", headers=bob).json()["id"]
    r = client.patch(f"{url}/members/{bob_id}", headers=alice, json={"role": "sponsor"})
    assert r.status_code == 422
    f = client.post(f"{url}/funders", headers=alice, json={"name": "Chrzestni"}).json()["funder"]
    r = client.patch(
        f"{url}/members/{bob_id}", headers=alice, json={"role": "sponsor", "funder_id": f["id"]}
    )
    assert r.status_code == 200, r.text
    assert r.json()["funder_id"] == f["id"]
    assert client.get(f"{url}/my-contribution", headers=bob).json()["funder"]["name"] == "Chrzestni"
    # Powrót do roli podglądu usuwa powiązanie.
    r = client.patch(f"{url}/members/{bob_id}", headers=alice, json={"role": "viewer"})
    assert r.json()["funder_id"] is None


def test_sponsor_reports_transfer_couple_confirms(client, alice, user_factory, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    f = client.post(
        f"{url}/funders", headers=alice, json={"name": "Rodzice", "pledged_amount": pln("10000")}
    ).json()["funder"]
    dad = user_factory("tata@example.com")
    invite_and_accept(
        client, alice, dad, wedding, "tata@example.com", role="sponsor", funder_id=f["id"]
    )
    r = client.post(
        f"{url}/my-contribution/reports",
        headers=dad,
        json={"amount": pln("4000"), "received_on": "2026-10-20", "note": "Przelew z konta taty"},
    )
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["funder"]["given"] == pln("0.00")  # jeszcze nie potwierdzone
    assert d["funder"]["reported"] == pln("4000.00")
    assert d["contributions"][0]["status"] == "reported"
    attention = client.get(f"{url}/attention", headers=alice).json()
    assert any(a["code"] == "funder.reported" and "4 000 zł" in a["message"] for a in attention)

    # Para nie może zgłaszać jako sponsor; sponsor nie może potwierdzać.
    assert (
        client.post(
            f"{url}/my-contribution/reports", headers=alice, json={"amount": pln("1")}
        ).status_code
        == 404
    )
    cid = d["contributions"][0]["id"]
    confirm = f"{url}/funders/{f['id']}/contributions/{cid}/confirm"
    assert client.post(confirm, headers=dad).status_code == 403
    ok = client.post(confirm, headers=alice)
    assert ok.status_code == 200, ok.text
    assert ok.json()["funder"]["given"] == pln("4000.00")
    assert ok.json()["funder"]["reported"] == pln("0.00")
    mine = client.get(f"{url}/my-contribution", headers=dad).json()
    assert mine["contributions"][0]["status"] == "confirmed"
