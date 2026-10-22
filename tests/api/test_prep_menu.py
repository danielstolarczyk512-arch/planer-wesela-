"""Plan przygotowań (fryzjer, makijaż) i menu z alergenami (propozycje 5 i 6 z analizy 07)."""

from app.modules.schedule.prep import Slot, compute, hhmm
from tests.api.test_offers import vendor
from tests.api.test_workspace import invite_and_accept

API = "/api/v1"
H = 60


def test_compute_backwards_bride_last():
    # Gotowi na 13:00, po jednej fryzjerce i makijażystce; Panna Młoda (ostatnia) kończy o 13:00.
    mama, bride = compute(13 * H, 1, 1, [(60, 45), (90, 60)])
    assert bride == (Slot(10 * H + 30, 12 * H, 1), Slot(12 * H, 13 * H, 1))
    # Mama: makijaż przed Panną Młodą, fryzura przed fryzurą Panny Młodej.
    assert mama == (Slot(9 * H + 30, 10 * H + 30, 1), Slot(11 * H + 15, 12 * H, 1))
    # Druga fryzjerka: mama może mieć fryzurę równolegle — start później.
    mama2, _ = compute(13 * H, 2, 1, [(60, 45), (90, 60)])
    assert mama2[0] == Slot(10 * H + 15, 11 * H + 15, 2)
    assert hhmm(-30) == "23:30"


def test_prep_plan_people_and_vendor_links(client, alice, user_factory, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    o = client.get(f"{w}/prep", headers=alice).json()
    assert (o["ready_by"], o["version"], o["people"]) == ("13:00", 0, [])
    assert client.put(f"{w}/prep", headers=alice, json={"ready_by": "14:00"}).status_code == 428
    r = client.put(f"{w}/prep", headers={**alice, "If-Match": '"0"'}, json={"ready_by": "14:00:00"})
    assert r.status_code == 200, r.text
    assert (r.json()["ready_by"], r.json()["version"]) == ("14:00", 1)
    stale = client.put(f"{w}/prep", headers={**alice, "If-Match": '"0"'}, json={"hair_artists": 2})
    assert stale.status_code == 409

    for name, hair, makeup in (("Panna Młoda", 90, 60), ("Mama", 60, 45), ("Świadkowa", 45, 0)):
        r = client.post(
            f"{w}/prep/people",
            headers=alice,
            json={"name": name, "hair_minutes": hair, "makeup_minutes": makeup},
        )
        assert r.status_code == 201, r.text
    o = r.json()
    # Panna Młoda na koniec kolejki.
    bride = o["people"][0]
    o = client.post(
        f"{w}/prep/people/{bride['id']}/move", headers=alice, json={"direction": "down"}
    ).json()
    o = client.post(
        f"{w}/prep/people/{bride['id']}/move", headers=alice, json={"direction": "down"}
    ).json()
    assert [p["name"] for p in o["people"]] == ["Mama", "Świadkowa", "Panna Młoda"]
    last = o["people"][2]
    assert (last["hair"]["end"], last["makeup"]) == (
        "13:00",
        {"start": "13:00", "end": "14:00", "artist": 1},
    )
    assert o["start"] == o["hair_start"]
    assert o["warnings"] == []

    hair = vendor(client, alice, wedding, "Fryzjerka Ola", "hairdresser")
    makeup = vendor(client, alice, wedding, "Makijaż Ewa", "makeup")
    dj = vendor(client, alice, wedding, "DJ", "dj")
    tokens = {
        v["category"]: client.post(f"{w}/vendors/{v['id']}/day-link", headers=alice).json()["token"]
        for v in (hair, makeup, dj)
    }
    hair_day = client.get(f"{API}/day/{tokens['hairdresser']}").json()
    assert [s["name"] for s in hair_day["prep"]] == ["Mama", "Świadkowa", "Panna Młoda"]
    makeup_day = client.get(f"{API}/day/{tokens['makeup']}").json()
    assert [s["name"] for s in makeup_day["prep"]] == ["Mama", "Panna Młoda"]  # bez świadkowej
    assert client.get(f"{API}/day/{tokens['dj']}").json()["prep"] == []

    coordinator = user_factory("swiadek@example.com")
    invite_and_accept(
        client, alice, coordinator, wedding, "swiadek@example.com", role="coordinator"
    )
    assert client.get(f"{w}/prep", headers=coordinator).status_code == 200
    r = client.post(f"{w}/prep/people", headers=coordinator, json={"name": "X"})
    assert r.status_code == 403

    # Za mało osób obsługujących: ostrzeżenie o starcie przed 6:00.
    many = [{"name": f"Druhna {i}", "hair_minutes": 120, "makeup_minutes": 0} for i in range(4)]
    for body in many:
        client.post(f"{w}/prep/people", headers=alice, json=body)
    o = client.get(f"{w}/prep", headers=alice).json()
    assert any("Start przed 6:00" in x for x in o["warnings"])
    assert len(client.get(f"{w}/export", headers=alice).json()["prep_people"]) == 7


def test_menu_allergens_diet_warnings_and_guest_page(client, alice, user_factory, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    h = client.post(f"{w}/households", headers=alice, json={"name": "Nowakowie"}).json()
    for first_name, diet in (("Jan", "vegetarian"), ("Ewa", "gluten_free"), ("Ola", "standard")):
        client.post(
            f"{w}/households/{h['id']}/guests",
            headers=alice,
            json={"first_name": first_name, "dietary_preference": diet},
        )
    r = client.post(
        f"{w}/menu",
        headers=alice,
        json={
            "course": "main",
            "name": "Schab ze śliwką",
            "allergens": ["gluten", "milk", "gluten"],
        },
    )
    assert r.status_code == 201, r.text
    o = r.json()
    assert o["dishes"][0]["allergens"] == ["gluten", "milk"]
    assert o["diets"] == {"vegetarian": 1, "vegan": 0, "gluten_free": 1}
    assert len(o["warnings"]) == 2
    assert any("wegetariańskiej" in x for x in o["warnings"])

    # Wegańskie danie jest też wegetariańskie i bez glutenu: ostrzeżenia znikają.
    o = client.post(
        f"{w}/menu",
        headers=alice,
        json={"course": "main", "name": "Pierogi z soczewicą", "vegan": True},
    ).json()
    vegan = o["dishes"][1]
    assert (vegan["vegetarian"], vegan["gluten_free"]) == (True, True)
    assert o["warnings"] == []
    # Desery nie są sprawdzane (każdy może je pominąć).
    o = client.post(
        f"{w}/menu",
        headers=alice,
        json={"course": "dessert", "name": "Sernik", "allergens": ["gluten"]},
    ).json()
    assert o["warnings"] == []

    bad = client.post(
        f"{w}/menu", headers=alice, json={"course": "main", "name": "X", "allergens": ["kurz"]}
    )
    assert bad.status_code == 422
    r = client.patch(
        f"{w}/menu/{vegan['id']}",
        headers={**alice, "If-Match": f'"{vegan["version"]}"'},
        json={"vegetarian": False},
    )
    assert r.status_code == 200, r.text
    changed = next(d for d in r.json()["dishes"] if d["id"] == vegan["id"])
    assert (changed["vegetarian"], changed["vegan"]) == (False, False)

    token = client.post(f"{w}/households/{h['id']}/rsvp-link", headers=alice).json()["token"]
    assert client.get(f"{API}/rsvp/{token}").json()["menu"] is None
    assert client.put(f"{w}/menu/show", headers=alice, json={"enabled": True}).json() == {
        "enabled": True
    }
    menu = client.get(f"{API}/rsvp/{token}").json()["menu"]
    assert [d["name"] for d in menu] == ["Schab ze śliwką", "Pierogi z soczewicą", "Sernik"]
    assert "id" not in menu[0]

    viewer = user_factory("ogladam@example.com")
    invite_and_accept(client, alice, viewer, wedding, "ogladam@example.com", role="viewer")
    assert client.get(f"{w}/menu", headers=viewer).status_code == 200
    r = client.post(f"{w}/menu", headers=viewer, json={"course": "main", "name": "Y"})
    assert r.status_code == 403
    assert len(client.get(f"{w}/export", headers=alice).json()["menu"]) == 3
