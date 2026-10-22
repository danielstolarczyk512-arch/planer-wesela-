"""Prognoza frekwencji i lista rezerwowa (propozycja 3 z docs/analysis/05)."""

from datetime import date, timedelta

from sqlalchemy import select, update

from app.core import clock
from app.jobs.worker import run_maintenance
from app.modules.guests.models import ReserveEntry
from app.modules.workspace.models import Wedding
from tests.api.test_offers import SALA_A, offer, vendor
from tests.api.test_workspace import invite_and_accept

API = "/api/v1"


def add_household(client, headers, url, name, guests, **kw):
    h = client.post(f"{url}/households", headers=headers, json={"name": name, **kw}).json()
    out = [
        client.post(
            f"{url}/households/{h['id']}/guests",
            headers=headers,
            json={"first_name": first_name, "age_group": age},
        ).json()
        for first_name, age in guests
    ]
    return h, out


def answer(client, headers, url, guest, event, status):
    r = client.put(
        f"{url}/guests/{guest['id']}/attendance/{event['id']}",
        headers=headers,
        json={"status": status},
    )
    assert r.status_code == 200, r.text


def setup(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    reception = client.post(
        f"{url}/events", headers=alice, json={"kind": "reception", "name": "Przyjęcie"}
    ).json()
    _, yes = add_household(client, alice, url, "Nowakowie", [("Jan", "adult"), ("Ewa", "adult")])
    for g in yes:
        answer(client, alice, url, g, reception, "attending")
    late, _ = add_household(
        client,
        alice,
        url,
        "Kowalscy",
        [("Piotr", "adult"), ("Anna", "adult")],
        rsvp_deadline="2027-04-01",
    )
    _, no = add_household(client, alice, url, "Wiśniewski", [("Adam", "adult")])
    answer(client, alice, url, no[0], reception, "declined")
    _, mixed = add_household(client, alice, url, "Zielińscy", [("Ola", "child"), ("Tom", "adult")])
    answer(client, alice, url, mixed[1], reception, "maybe")
    sala = vendor(client, alice, wedding, "Sala")
    venue = offer(client, alice, wedding, sala["id"], min_guests=80, components=SALA_A)
    assert client.post(f"{url}/offers/{venue['id']}/select", headers=alice, json={}).is_success
    return url, late


def test_forecast_numbers_venue_minimum_and_alerts(client, alice, wedding, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2027, 6, 25))
    url, late = setup(client, alice, wedding)
    r = client.get(f"{url}/attendance-forecast", headers=alice)
    assert r.status_code == 200, r.text
    f = r.json()
    assert f["people"] == {"attending": 2, "declined": 1, "maybe": 1, "pending": 3, "infants": 0}
    assert f["forecast"] == {
        "expected": 5,
        "low": 3,
        "high": 6,
        "expected_adults": 4,
        "expected_children": 1,
    }
    assert f["planned"] == 110
    assert f["free_places_safe"] == 104
    v = f["venues"][0]
    assert (v["min_guests"], v["shortfall_expected"]) == (80, 76)
    assert v["unused_cost_expected"] == {"amount": "25080.00", "currency": "PLN"}
    # 76 os. po 330 zł. Zadanie z szablonu: 21 dni przed 2027-08-01 → 2027-07-11.
    assert f["final_count"]["due_date"] == "2027-07-11"
    assert f["final_count"]["days_left"] == 16
    assert [h["name"] for h in f["overdue_households"]] == ["Kowalscy"]
    assert f["overdue_households"][0]["household_id"] == late["id"]
    codes = [a["code"] for a in f["alerts"]]
    assert codes == ["final_count.soon", "venue.below_minimum", "rsvp.overdue"]
    assert "25 080 zł" in f["alerts"][1]["message"]
    # Założenia pary zmieniają prognozę.
    sure = client.get(f"{url}/attendance-forecast?pending_rate=1&maybe_rate=1", headers=alice)
    assert sure.json()["forecast"]["expected"] == 6
    bad = client.get(f"{url}/attendance-forecast?pending_rate=0.1", headers=alice)
    assert bad.status_code == 422


def test_reserve_list_order_invite_and_suggestions(client, alice, wedding, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2027, 5, 1))
    url, _ = setup(client, alice, wedding)
    a = client.post(
        f"{url}/reserve", headers=alice, json={"name": "Kuzyn Marek z żoną", "persons": 2}
    ).json()
    b = client.post(
        f"{url}/reserve", headers=alice, json={"name": "Kasia z pracy", "side": "bride"}
    ).json()
    names = [e["name"] for e in client.get(f"{url}/reserve", headers=alice).json()]
    assert names == ["Kuzyn Marek z żoną", "Kasia z pracy"]
    moved = client.patch(
        f"{url}/reserve/{b['id']}", headers={**alice, "If-Match": '"1"'}, json={"position": 0}
    )
    assert moved.status_code == 200, moved.text
    ids = [e["id"] for e in client.get(f"{url}/reserve", headers=alice).json()]
    assert ids == [b["id"], a["id"]]
    stale = client.patch(
        f"{url}/reserve/{b['id']}", headers={**alice, "If-Match": '"1"'}, json={"note": "x"}
    )
    assert stale.status_code == 409

    f = client.get(f"{url}/attendance-forecast", headers=alice).json()
    assert f["reserve_waiting"] == 3
    assert f["reserve_invite_by"] == "2027-06-20"  # 6 tygodni przed 2027-08-01
    assert [s["name"] for s in f["suggestions"]] == ["Kasia z pracy", "Kuzyn Marek z żoną"]

    r = client.post(
        f"{url}/reserve/{a['id']}/invite",
        headers=alice,
        json={"guests": [{"first_name": "Marek"}, {"first_name": "Iza"}]},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["entry"]["status"] == "invited"
    household = client.get(f"{url}/households/{body['household_id']}", headers=alice).json()
    assert household["name"] == "Kuzyn Marek z żoną"
    assert [g["first_name"] for g in household["guests"]] == ["Marek", "Iza"]
    again = client.post(
        f"{url}/reserve/{a['id']}/invite", headers=alice, json={"guests": [{"first_name": "X"}]}
    )
    assert again.status_code == 409
    assert again.json()["code"] == "reserve.already_invited"

    f = client.get(f"{url}/attendance-forecast", headers=alice).json()
    assert f["people"]["pending"] == 5  # zaproszeni z rezerwy czekają na odpowiedź
    assert f["reserve_waiting"] == 1
    # Usunięcie wpisu nie usuwa zaproszonego gospodarstwa.
    assert client.delete(f"{url}/reserve/{a['id']}", headers=alice).status_code == 204
    assert client.get(f"{url}/households/{body['household_id']}", headers=alice).is_success


def test_reserve_late_alert_and_no_suggestions(client, alice, wedding, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2027, 6, 25))
    url = f"{API}/weddings/{wedding['id']}"
    client.post(f"{url}/reserve", headers=alice, json={"name": "Sąsiedzi"})
    f = client.get(f"{url}/attendance-forecast", headers=alice).json()
    assert f["suggestions"] == []
    assert "reserve.late" in [a["code"] for a in f["alerts"]]


def test_viewer_reads_but_cannot_change_reserve(client, alice, user_factory, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    entry = client.post(f"{url}/reserve", headers=alice, json={"name": "Sąsiedzi"}).json()
    viewer = user_factory("babcia@example.com")
    invite_and_accept(client, alice, viewer, wedding, "babcia@example.com", role="viewer")
    assert client.get(f"{url}/reserve", headers=viewer).status_code == 200
    assert client.get(f"{url}/attendance-forecast", headers=viewer).status_code == 200
    body = {"guests": [{"first_name": "X"}]}
    r = client.post(f"{url}/reserve/{entry['id']}/invite", headers=viewer, json=body)
    assert r.status_code == 403


def test_reserve_list_removed_with_guest_retention(client, alice, wedding, db):
    url = f"{API}/weddings/{wedding['id']}"
    client.post(f"{url}/reserve", headers=alice, json={"name": "Sąsiedzi"})
    db.execute(update(Wedding).values(wedding_date=clock.today() - timedelta(days=91)))
    db.commit()
    assert run_maintenance()["weddings_guests_anonymized"] == 1
    db.expire_all()
    assert db.scalars(select(ReserveEntry)).all() == []


def test_after_party_forecast_separate(client, alice, wedding):
    url, _ = setup(client, alice, wedding)
    before = client.get(f"{url}/attendance-forecast", headers=alice).json()
    assert before["after_party"] is None
    after = client.post(
        f"{url}/events", headers=alice, json={"kind": "after_party", "name": "Poprawiny"}
    ).json()
    guests = {g["first_name"]: g for g in client.get(f"{url}/guests", headers=alice).json()}
    answer(client, alice, url, guests["Jan"], after, "attending")
    answer(client, alice, url, guests["Ewa"], after, "declined")
    # Odpowiedź o poprawinach nie zmienia prognozy przyjęcia.
    answer(client, alice, url, guests["Adam"], after, "attending")
    o = client.get(f"{url}/attendance-forecast", headers=alice).json()
    assert o["forecast"] == before["forecast"]
    ap = o["after_party"]
    assert ap["event_name"] == "Poprawiny"
    # Adam odmówił przyjęcia, więc i na poprawiny się nie liczy.
    assert ap["people"] == {"attending": 1, "declined": 2, "maybe": 0, "pending": 4, "infants": 0}
    assert ap["forecast"]["expected"] == 4  # 1 + 4 · 0,85
    assert ap["forecast"]["low"] >= 1
