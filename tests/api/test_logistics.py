"""Transport i noclegi gości (propozycja 8 z docs/analysis/05)."""

from tests.api.test_offers import vendor
from tests.api.test_schedule import add as add_item
from tests.api.test_schedule import at

API = "/api/v1"


def guests(client, headers, url, *names, **flags):
    h = client.post(f"{url}/households", headers=headers, json={"name": "Rodzina"}).json()
    return [
        client.post(
            f"{url}/households/{h['id']}/guests", headers=headers, json={"first_name": n, **flags}
        ).json()
        for n in names
    ]


def test_runs_capacity_missing_and_schedule(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    a, b, c = guests(client, alice, url, "Ala", "Basia", "Celina", needs_transport=True)
    add_item(client, alice, wedding, title="Tort", starts_at=at("23:30"), for_guests=True)
    add_item(
        client, alice, wedding, title="Pierwszy taniec", starts_at=at("19:00"), for_guests=True
    )
    bus = vendor(client, alice, wedding, "Przewozy Kowalski", "transport")
    r = client.post(
        f"{url}/transport-runs",
        headers=alice,
        json={
            "name": "Powrót wcześniejszy",
            "kind": "back",
            "departs_at": at("23:00"),
            "capacity": 2,
            "vendor_id": bus["id"],
        },
    )
    assert r.status_code == 201, r.text
    run = r.json()["runs"][0]
    o = client.put(
        f"{url}/transport-runs/{run['id']}/guests",
        headers=alice,
        json={"guest_ids": [a["id"], b["id"], c["id"]]},
    ).json()
    run = o["runs"][0]
    assert (run["taken"], run["over"]) == (3, 1)
    # Kurs powrotny o 23:00 omija tort o 23:30 (punkt programu dla gości).
    assert [m["title"] for m in run["missed_items"]] == ["Tort"]
    assert o["transport_missing"] == []
    o = client.put(
        f"{url}/transport-runs/{run['id']}/guests", headers=alice, json={"guest_ids": [a["id"]]}
    ).json()
    assert [p["name"] for p in o["transport_missing"]] == ["Basia", "Celina"]

    # Przewoźnik widzi na swoim linku kurs i liczbę osób, bez nazwisk.
    token = client.post(f"{url}/vendors/{bus['id']}/day-link", headers=alice).json()["token"]
    day = client.get(f"{API}/day/{token}").json()
    assert day["transport"] == [
        {
            "name": "Powrót wcześniejszy",
            "departs_at": "2027-08-21T23:00:00+02:00",
            "from_place": None,
            "to_place": None,
            "passengers": 1,
            "capacity": 2,
        }
    ]
    assert "Ala" not in str(day["transport"])

    stale = client.patch(
        f"{url}/transport-runs/{run['id']}",
        headers={**alice, "If-Match": '"99"'},
        json={"capacity": 50},
    )
    assert stale.status_code == 409
    ok = client.patch(
        f"{url}/transport-runs/{run['id']}",
        headers={**alice, "If-Match": f'"{run["version"]}"'},
        json={"capacity": 50},
    )
    assert ok.json()["runs"][0]["capacity"] == 50
    assert client.delete(f"{url}/transport-runs/{run['id']}", headers=alice).status_code == 204


def test_rooms_move_guest_and_rooming_csv(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    a, b, c = guests(client, alice, url, "Ala", "Basia", "Celina", needs_accommodation=True)
    room = {"place": "Hotel Pod Lipami", "name": "Pokój 12", "beds": 2}
    bad = client.post(
        f"{url}/lodging-rooms",
        headers=alice,
        json={**room, "check_in": "2027-08-21", "check_out": "2027-08-21"},
    )
    assert bad.status_code == 422
    r1 = client.post(
        f"{url}/lodging-rooms",
        headers=alice,
        json={**room, "check_in": "2027-08-21", "check_out": "2027-08-22", "paid_by": "para"},
    ).json()["rooms"][0]
    r2 = client.post(
        f"{url}/lodging-rooms", headers=alice, json={**room, "name": "Pokój 14"}
    ).json()["rooms"]
    r2 = next(r for r in r2 if r["name"] == "Pokój 14")
    too_many = client.put(
        f"{url}/lodging-rooms/{r1['id']}/guests",
        headers=alice,
        json={"guest_ids": [a["id"], b["id"], c["id"]]},
    )
    assert too_many.json()["code"] == "lodging_room.too_many"
    client.put(
        f"{url}/lodging-rooms/{r1['id']}/guests",
        headers=alice,
        json={"guest_ids": [a["id"], b["id"]]},
    )
    # Przeniesienie Basi do pokoju 14: znika z pokoju 12.
    o = client.put(
        f"{url}/lodging-rooms/{r2['id']}/guests", headers=alice, json={"guest_ids": [b["id"]]}
    ).json()
    rooms = {r["name"]: r for r in o["rooms"]}
    assert [p["name"] for p in rooms["Pokój 12"]["occupants"]] == ["Ala"]
    assert rooms["Pokój 12"]["nights"] == 1
    assert [p["name"] for p in o["lodging_missing"]] == ["Celina"]

    csv = client.get(f"{url}/lodging/rooming.csv", headers=alice)
    assert csv.status_code == 200
    assert csv.headers["content-type"].startswith("text/csv")
    text = csv.content.decode("utf-8")
    assert "Hotel Pod Lipami;Pokój 12;2;2027-08-21;2027-08-22;1;Ala;para" in text


def test_foreign_guest_rejected(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    run = client.post(
        f"{url}/transport-runs", headers=alice, json={"name": "Bus", "capacity": 10}
    ).json()["runs"][0]
    r = client.put(
        f"{url}/transport-runs/{run['id']}/guests",
        headers=alice,
        json={"guest_ids": ["0192aaaa-0000-7000-8000-000000000000"]},
    )
    assert r.status_code == 404


def test_guest_picks_run_in_rsvp(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    h = client.post(f"{url}/households", headers=alice, json={"name": "Kowalscy"}).json()
    jan, ewa = (
        client.post(
            f"{url}/households/{h['id']}/guests", headers=alice, json={"first_name": n}
        ).json()
        for n in ("Jan", "Ewa")
    )
    shown = client.post(
        f"{url}/transport-runs",
        headers=alice,
        json={"name": "Autokar z dworca", "capacity": 1, "show_to_guests": True},
    ).json()["runs"][0]
    hidden = client.post(
        f"{url}/transport-runs", headers=alice, json={"name": "Bus dla dziadków", "capacity": 5}
    ).json()["runs"]
    hidden = next(r for r in hidden if r["name"] == "Bus dla dziadków")
    client.put(
        f"{url}/transport-runs/{hidden['id']}/guests",
        headers=alice,
        json={"guest_ids": [ewa["id"]]},
    )
    token = client.post(f"{url}/households/{h['id']}/rsvp-link", headers=alice).json()["token"]

    view = client.get(f"{API}/rsvp/{token}").json()
    assert [(r["name"], r["free"]) for r in view["transport_runs"]] == [("Autokar z dworca", 1)]
    # Kurs ukryty (przydział pary) nie jest widoczny dla gościa.
    assert all(g["transport_run_ids"] == [] for g in view["guests"])

    r = client.put(
        f"{API}/rsvp/{token}",
        json={
            "responses": [],
            "guests": [{"guest_id": jan["id"], "transport_run_ids": [shown["id"]]}],
        },
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert next(g for g in v["guests"] if g["id"] == jan["id"])["transport_run_ids"] == [
        shown["id"]
    ]
    assert next(g for g in v["guests"] if g["id"] == jan["id"])["needs_transport"] is True
    assert v["transport_runs"][0]["free"] == 0
    # Pełny kurs: druga osoba nie wejdzie.
    full = client.put(
        f"{API}/rsvp/{token}",
        json={
            "responses": [],
            "guests": [{"guest_id": ewa["id"], "transport_run_ids": [shown["id"]]}],
        },
    )
    assert (full.status_code, full.json()["code"]) == (409, "rsvp.transport_full")
    # Kurs ukryty i obcy kurs: odrzucone; przydział pary (Ewa w busie) bez zmian.
    bad = client.put(
        f"{API}/rsvp/{token}",
        json={
            "responses": [],
            "guests": [{"guest_id": ewa["id"], "transport_run_ids": [hidden["id"]]}],
        },
    )
    assert bad.status_code == 422
    o = client.get(f"{url}/logistics", headers=alice).json()
    bus = next(r for r in o["runs"] if r["name"] == "Bus dla dziadków")
    assert [p["name"] for p in bus["passengers"]] == ["Ewa"]
    # Rezygnacja z kursu przez gościa zwalnia miejsce.
    client.put(
        f"{API}/rsvp/{token}",
        json={"responses": [], "guests": [{"guest_id": jan["id"], "transport_run_ids": []}]},
    )
    assert client.get(f"{API}/rsvp/{token}").json()["transport_runs"][0]["free"] == 1


def test_coordinator_sees_day_transport_without_names(client, alice, user_factory, wedding):
    from tests.api.test_workspace import invite_and_accept

    url = f"{API}/weddings/{wedding['id']}"
    (a,) = guests(client, alice, url, "Ala")
    run = client.post(
        f"{url}/transport-runs",
        headers=alice,
        json={"name": "Powrót", "kind": "back", "departs_at": at("01:00"), "capacity": 20},
    ).json()["runs"][0]
    client.put(
        f"{url}/transport-runs/{run['id']}/guests", headers=alice, json={"guest_ids": [a["id"]]}
    )
    coordinator = user_factory("swiadek@example.com")
    invite_and_accept(
        client, alice, coordinator, wedding, "swiadek@example.com", role="coordinator"
    )
    r = client.get(f"{url}/day-transport", headers=coordinator)
    assert r.status_code == 200, r.text
    assert [(x["name"], x["passengers"], x["capacity"]) for x in r.json()] == [("Powrót", 1, 20)]
    assert "Ala" not in r.text
    # Pełny widok z nazwiskami tylko dla ról z dostępem do gości.
    assert client.get(f"{url}/logistics", headers=coordinator).status_code == 403


def test_guest_export_has_run_and_room(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    (a,) = guests(client, alice, url, "Ala")
    run = client.post(
        f"{url}/transport-runs", headers=alice, json={"name": "Bus", "capacity": 5}
    ).json()
    client.put(
        f"{url}/transport-runs/{run['runs'][0]['id']}/guests",
        headers=alice,
        json={"guest_ids": [a["id"]]},
    )
    room = client.post(
        f"{url}/lodging-rooms", headers=alice, json={"place": "Hotel", "name": "12", "beds": 2}
    ).json()["rooms"][0]
    client.put(
        f"{url}/lodging-rooms/{room['id']}/guests", headers=alice, json={"guest_ids": [a["id"]]}
    )
    text = client.get(f"{url}/guests/export.csv", headers=alice).content.decode("utf-8-sig")
    ala = next(line for line in text.splitlines() if ";Ala;" in line)
    assert ala.endswith(";Bus;Hotel, 12")
