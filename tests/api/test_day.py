"""Dzień ślubu: koordynator dnia, plan B, link z programem dla usługodawcy."""

from tests.api.test_offers import vendor
from tests.api.test_schedule import add, at, url
from tests.api.test_workspace import invite_and_accept

API = "/api/v1"


def test_coordinator_sees_only_the_day(client, alice, bob, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    dj = vendor(client, alice, wedding, "DJ Marek", "dj")
    item = add(client, alice, wedding, title="Pierwszy taniec", starts_at=at("21:00"))
    invite_and_accept(client, alice, bob, wedding, "bob@example.com", role="coordinator")

    me = client.get(w, headers=bob)
    assert me.status_code == 200
    assert me.json()["my_role"] == "coordinator"
    assert me.json()["total_budget"] is None  # budżet ukryty
    assert client.get(url(wedding), headers=bob).status_code == 200
    assert client.get(f"{w}/events", headers=bob).status_code == 200
    assert client.get(f"{w}/vendors/{dj['id']}", headers=bob).status_code == 200
    # Opóźnienie w dniu ślubu: koordynator przesuwa program.
    r = client.post(
        f"{url(wedding)}/shift",
        headers=bob,
        json={"from_item_id": item["id"], "minutes": 15, "dry_run": False},
    )
    assert r.status_code == 200, r.text

    # Bez dostępu: budżet, goście (diety), zadania, oferty, edycja programu, podsumowanie.
    for path in ("budget/overview", "households", "tasks", "offers", "summary", "members"):
        assert client.get(f"{w}/{path}", headers=bob).status_code == 403, path
    r = client.patch(
        f"{url(wedding)}/{item['id']}", headers={**bob, "If-Match": '"2"'}, json={"title": "X"}
    )
    assert r.status_code == 403


def test_plan_b_on_schedule_item(client, alice, wedding):
    item = add(
        client,
        alice,
        wedding,
        title="Sesja w ogrodzie",
        starts_at=at("18:00"),
        plan_b="Deszcz: zdjęcia na werandzie, parasole w bagażniku auta",
    )
    assert item["plan_b"].startswith("Deszcz")
    r = client.patch(
        f"{url(wedding)}/{item['id']}", headers={**alice, "If-Match": '"1"'}, json={"plan_b": None}
    )
    assert r.json()["plan_b"] is None


def test_vendor_day_link(client, alice, bob, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    band = vendor(client, alice, wedding, "Zespół", "band")
    photo = vendor(client, alice, wedding, "Fotograf", "photographer")
    add(
        client,
        alice,
        wedding,
        title="Oczepiny",
        starts_at=at("23:00"),
        vendor_id=band["id"],
        preparations="Welon i krawat",
        plan_b="Jeśli opóźnienie: skrócić do 20 min",
    )
    add(
        client,
        alice,
        wedding,
        title="Sesja",
        starts_at=at("18:00"),
        vendor_id=photo["id"],
        preparations="Prywatna uwaga dla fotografa",
    )
    link = f"{w}/vendors/{band['id']}/day-link"
    assert client.get(link, headers=alice).json()["active"] is False
    token = client.post(link, headers=alice).json()["token"]

    r = client.get(f"{API}/day/{token}")
    assert r.status_code == 200, r.text
    day = r.json()
    assert day["vendor_name"] == "Zespół"
    mine = next(i for i in day["items"] if i["title"] == "Oczepiny")
    other = next(i for i in day["items"] if i["title"] == "Sesja")
    assert mine["mine"] is True
    assert mine["plan_b"].startswith("Jeśli")
    assert other["mine"] is False
    assert other["preparations"] is None  # cudze szczegóły ukryte
    assert r.headers["cache-control"] == "no-store"
    assert client.get(link, headers=alice).json()["last_used_at"] is not None

    # Nowy link unieważnia stary; wyłączenie; obcy nie wygeneruje linku.
    token2 = client.post(link, headers=alice).json()["token"]
    assert client.get(f"{API}/day/{token}").status_code == 404
    assert client.delete(link, headers=alice).status_code == 204
    assert client.get(f"{API}/day/{token2}").status_code == 404
    assert client.post(link, headers=bob).status_code == 404


def test_day_link_gone_with_vendor(client, alice, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    band = vendor(client, alice, wedding, "Zespół", "band")
    token = client.post(f"{w}/vendors/{band['id']}/day-link", headers=alice).json()["token"]
    assert client.delete(f"{w}/vendors/{band['id']}", headers=alice).status_code == 204
    assert client.get(f"{API}/day/{token}").status_code == 404


def test_venue_link_catering_numbers_and_consent(client, alice, wedding):
    from tests.api.test_seating import household, table
    from tests.api.test_seating import url as seating

    w = f"{API}/weddings/{wedding['id']}"
    sala = vendor(client, alice, wedding, "Dworek", "venue")
    band = client.post(
        f"{w}/vendors", headers=alice, json={"name": "Zespół", "category": "band", "crew_meals": 4}
    ).json()
    reception = client.post(
        f"{w}/events", headers=alice, json={"kind": "reception", "name": "Przyjęcie"}
    ).json()
    ania, kuba, ola, zenek = household(
        client,
        alice,
        wedding,
        "Nowakowie",
        [("Ania", "adult"), ("Kuba", "child"), ("Ola", "adult"), ("Zenek", "adult")],
    )
    client.patch(
        f"{w}/guests/{ania['id']}",
        headers={**alice, "If-Match": '"1"'},
        json={"dietary_preference": "vegan", "dietary_note": "alergia na orzechy"},
    )

    def answer(guest, status):
        client.put(
            f"{w}/guests/{guest['id']}/attendance/{reception['id']}",
            headers=alice,
            json={"status": status},
        )

    answer(ania, "attending")
    answer(kuba, "attending")
    answer(zenek, "declined")
    t1 = table(client, alice, wedding, "Stół 1", 8)
    for g in (ania, kuba, zenek):
        r = client.put(
            f"{seating(wedding)}/guests/{g['id']}", headers=alice, json={"table_id": t1["id"]}
        )
        assert r.status_code == 204, r.text

    link = f"{w}/vendors/{sala['id']}/day-link"
    token = client.post(link, headers=alice).json()["token"]
    r = client.get(f"{API}/day/{token}")
    assert r.status_code == 200, r.text
    c = r.json()["catering"]
    assert c["attending"] == {"adults": 1, "teens": 0, "children": 1, "infants": 0}
    assert c["pending"] == 1  # Ola
    assert c["diets"] == [{"diet": "vegan", "count": 1}]
    assert c["crew_meals"] == 4
    assert c["details_shared"] is False
    # Bez zgody: przy stole same liczby (odmowa Zenka nie liczy się), bez imion i uwag.
    assert c["tables"] == [
        {
            "name": "Stół 1",
            "count": {"adults": 1, "teens": 0, "children": 1, "infants": 0},
            "diets": [{"diet": "vegan", "count": 1}],
            "guests": None,
        }
    ]
    assert "Ania" not in r.text
    assert "orzechy" not in r.text
    assert client.get(link, headers=alice).json()["share_catering"] is False

    # Zmiana na liście gości widoczna od razu.
    answer(ola, "attending")
    c = client.get(f"{API}/day/{token}").json()["catering"]
    assert c["attending"]["adults"] == 2
    assert c["pending"] == 0

    # Za zgodą: imiona, diety i uwagi przy stołach; stary link przestaje działać.
    token2 = client.post(link, headers=alice, json={"share_catering": True}).json()["token"]
    assert client.get(f"{API}/day/{token}").status_code == 404
    c = client.get(f"{API}/day/{token2}").json()["catering"]
    assert c["details_shared"] is True
    assert c["tables"][0]["guests"] == [
        {"name": "Ania", "age_group": "adult", "diet": "vegan", "diet_note": "alergia na orzechy"},
        {"name": "Kuba", "age_group": "child", "diet": "standard", "diet_note": None},
    ]
    assert client.get(link, headers=alice).json()["share_catering"] is True

    # Inni usługodawcy: bez sekcji dla kuchni i bez możliwości zgody.
    band_link = f"{w}/vendors/{band['id']}/day-link"
    band_token = client.post(band_link, headers=alice).json()["token"]
    assert client.get(f"{API}/day/{band_token}").json()["catering"] is None
    r = client.post(band_link, headers=alice, json={"share_catering": True})
    assert r.status_code == 422
    assert r.json()["code"] == "day_link.catering_not_allowed"
