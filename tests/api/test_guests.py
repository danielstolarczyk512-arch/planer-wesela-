from datetime import date, timedelta

from sqlalchemy import select, update

from app.core import clock
from app.jobs.worker import run_maintenance
from app.modules.guests.models import Guest, Household
from app.modules.workspace.models import Wedding

API = "/api/v1"


def setup_household(client, headers, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    reception = client.post(
        f"{url}/events", headers=headers, json={"kind": "reception", "name": "Przyjęcie"}
    ).json()
    after = client.post(
        f"{url}/events", headers=headers, json={"kind": "after_party", "name": "Poprawiny"}
    ).json()
    h = client.post(
        f"{url}/households",
        headers=headers,
        json={
            "name": "Państwo Nowak",
            "side": "bride",
            "contact_email": "Nowak@Example.com",
            "rsvp_deadline": "2027-07-01",
        },
    ).json()
    adult = client.post(
        f"{url}/households/{h['id']}/guests",
        headers=headers,
        json={"first_name": "Jan", "last_name": "Nowak"},
    ).json()
    child = client.post(
        f"{url}/households/{h['id']}/guests",
        headers=headers,
        json={"first_name": "Zosia", "age_group": "child"},
    ).json()
    return url, reception, after, h, adult, child


def test_household_and_guests(client, alice, wedding, db):
    url, _, _, _h, adult, _ = setup_household(client, alice, wedding)
    households = client.get(f"{url}/households", headers=alice).json()
    assert households[0]["contact_email"] == "nowak@example.com"
    assert len(households[0]["guests"]) == 2

    r = client.patch(
        f"{url}/guests/{adult['id']}",
        headers={**alice, "If-Match": '"1"'},
        json={"dietary_preference": "vegetarian", "dietary_note": "alergia na orzechy"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["dietary_note"] == "alergia na orzechy"
    # W bazie notatka jest zaszyfrowana.
    stored = db.scalars(select(Guest).where(Guest.first_name == "Jan")).one()
    assert b"orzechy" not in stored.dietary_note_encrypted

    stats = client.get(f"{url}/guests/stats", headers=alice).json()
    assert stats["guests"] == 2
    assert stats["children"] == 1
    assert stats["with_dietary_note"] == 1
    assert stats["by_side"] == {"bride": 2}


def test_rsvp_link_flow(client, alice, wedding):
    url, reception, after, h, adult, child = setup_household(client, alice, wedding)
    link = client.post(f"{url}/households/{h['id']}/rsvp-link", headers=alice)
    assert link.status_code == 201
    token = link.json()["token"]
    assert link.json()["url"].endswith(token)

    view = client.get(f"{API}/rsvp/{token}")
    assert view.status_code == 200
    v = view.json()
    assert v["household_name"] == "Państwo Nowak"
    assert {g["first_name"] for g in v["guests"]} == {"Jan", "Zosia"}
    assert "last_name" not in v["guests"][0]

    body = {
        "responses": [
            {"guest_id": adult["id"], "event_id": reception["id"], "status": "attending"},
            {"guest_id": child["id"], "event_id": reception["id"], "status": "attending"},
            {"guest_id": adult["id"], "event_id": after["id"], "status": "declined"},
        ],
        "guests": [
            {"guest_id": adult["id"], "dietary_note": "bez glutenu", "needs_accommodation": True}
        ],
        "health_data_consent": True,
    }
    r = client.put(f"{API}/rsvp/{token}", json=body)
    assert r.status_code == 200, r.text
    jan = next(g for g in r.json()["guests"] if g["first_name"] == "Jan")
    assert jan["has_dietary_note"] is True

    stats = client.get(f"{url}/guests/stats", headers=alice).json()
    rec = next(e for e in stats["events"] if e["kind"] == "reception")
    assert (rec["attending"], rec["attending_adults"], rec["attending_children"]) == (2, 1, 1)
    assert stats["needs_accommodation"] == 1
    summary = client.get(f"{url}/summary", headers=alice).json()
    assert summary["guests"]["confirmed"] == 2

    # Nowy link unieważnia stary.
    client.post(f"{url}/households/{h['id']}/rsvp-link", headers=alice)
    assert client.get(f"{API}/rsvp/{token}").status_code == 404


def test_rsvp_requires_consent_for_notes_and_rejects_foreign_ids(client, alice, wedding):
    url, reception, _, h, adult, _ = setup_household(client, alice, wedding)
    token = client.post(f"{url}/households/{h['id']}/rsvp-link", headers=alice).json()["token"]
    r = client.put(
        f"{API}/rsvp/{token}",
        json={"responses": [], "guests": [{"guest_id": adult["id"], "dietary_note": "orzechy"}]},
    )
    assert r.status_code == 422

    other = client.post(f"{url}/households", headers=alice, json={"name": "Inni"}).json()
    stranger = client.post(
        f"{url}/households/{other['id']}/guests", headers=alice, json={"first_name": "Obcy"}
    ).json()
    r = client.put(
        f"{API}/rsvp/{token}",
        json={
            "responses": [
                {"guest_id": stranger["id"], "event_id": reception["id"], "status": "attending"}
            ]
        },
    )
    assert r.status_code == 422
    assert r.json()["code"] == "rsvp.invalid_target"


def test_rsvp_closed_after_deadline_and_invalid_token(client, alice, wedding, monkeypatch):
    url, reception, _, h, adult, _ = setup_household(client, alice, wedding)
    token = client.post(f"{url}/households/{h['id']}/rsvp-link", headers=alice).json()["token"]
    monkeypatch.setattr(clock, "today", lambda: date(2027, 7, 2))
    assert client.get(f"{API}/rsvp/{token}").json()["is_open"] is False
    r = client.put(
        f"{API}/rsvp/{token}",
        json={
            "responses": [
                {"guest_id": adult["id"], "event_id": reception["id"], "status": "attending"}
            ]
        },
    )
    assert r.status_code == 409
    assert client.get(f"{API}/rsvp/{'x' * 43}").status_code == 404
    revoke = client.delete(f"{url}/households/{h['id']}/rsvp-link", headers=alice)
    assert revoke.status_code == 204


def test_rsvp_companion_added_and_removed_by_guest(client, alice, wedding, monkeypatch):
    url, reception, _, h, adult, _ = setup_household(client, alice, wedding)
    token = client.post(f"{url}/households/{h['id']}/rsvp-link", headers=alice).json()["token"]

    r = client.post(
        f"{API}/rsvp/{token}/companions", json={"first_name": " Ola ", "last_name": "Kos"}
    )
    assert r.status_code == 201, r.text
    ola = next(g for g in r.json()["guests"] if g["first_name"] == "Ola")
    assert ola["is_plus_one"] is True
    assert ola["added_via_rsvp"] is True
    # Bez limitu z planu: kolejna osoba też wchodzi.
    r = client.post(f"{API}/rsvp/{token}/companions", json={"first_name": "Kuba"})
    assert len(r.json()["guests"]) == 4

    # Gość potwierdza obecność dopisanej osoby tym samym formularzem.
    r = client.put(
        f"{API}/rsvp/{token}",
        json={
            "responses": [
                {"guest_id": ola["id"], "event_id": reception["id"], "status": "attending"}
            ]
        },
    )
    assert r.status_code == 200, r.text
    households = client.get(f"{url}/households", headers=alice).json()
    para = next(g for g in households[0]["guests"] if g["first_name"] == "Ola")
    assert para["added_via_rsvp"] is True
    assert para["last_name"] == "Kos"
    assert para["attendance"][reception["id"]] == "attending"

    # Gość nie usunie osoby zaproszonej przez parę.
    r = client.delete(f"{API}/rsvp/{token}/companions/{adult['id']}")
    assert r.status_code == 422
    assert r.json()["code"] == "rsvp.invalid_target"
    r = client.delete(f"{API}/rsvp/{token}/companions/{ola['id']}")
    assert r.status_code == 200
    assert {g["first_name"] for g in r.json()["guests"]} == {"Jan", "Zosia", "Kuba"}

    monkeypatch.setattr(clock, "today", lambda: date(2027, 7, 2))
    r = client.post(f"{API}/rsvp/{token}/companions", json={"first_name": "Spóźniony"})
    assert r.status_code == 409


def test_guest_filters(client, alice, wedding):
    url, reception, _, _, adult, child = setup_household(client, alice, wedding)
    client.put(
        f"{url}/guests/{adult['id']}/attendance/{reception['id']}",
        headers=alice,
        json={"status": "attending"},
    )
    attending = client.get(
        f"{url}/guests",
        headers=alice,
        params={"event_id": reception["id"], "attendance": "attending"},
    )
    assert [g["id"] for g in attending.json()] == [adult["id"]]
    pending = client.get(
        f"{url}/guests",
        headers=alice,
        params={"event_id": reception["id"], "attendance": "pending"},
    )
    assert [g["id"] for g in pending.json()] == [child["id"]]


def test_csv_import_dry_run_and_apply(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    csv = (
        "household;first_name;last_name;side;age_group;dietary;accommodation;transport\n"
        "Kowalscy;Anna;Kowalska;panna młoda;dorosły;wegetariańska;tak;nie\n"
        "Kowalscy;Piotr;Kowalski;panna młoda;;;tak;\n"
        "Wiśniewscy;Ola;;pan młody;dziecko;;;tak\n"
    )
    dry = client.post(f"{url}/guests/import", headers=alice, json={"csv": csv})
    assert dry.status_code == 200, dry.text
    assert dry.json() == {
        "dry_run": True,
        "households_created": 2,
        "households_reused": 0,
        "guests_created": 3,
        "errors": [],
    }
    assert client.get(f"{url}/households", headers=alice).json() == []

    applied = client.post(
        f"{url}/guests/import", headers=alice, json={"csv": csv, "dry_run": False}
    ).json()
    assert applied["guests_created"] == 3
    stats = client.get(f"{url}/guests/stats", headers=alice).json()
    assert stats["diets"]["vegetarian"] == 1
    assert stats["needs_accommodation"] == 2
    assert stats["children"] == 1


def test_csv_import_reports_errors_without_saving(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    csv = "household,first_name,dietary\nA,Jan,keto\n,Ola,\n"
    r = client.post(
        f"{url}/guests/import", headers=alice, json={"csv": csv, "dry_run": False}
    ).json()
    assert [e["row"] for e in r["errors"]] == [2, 3]
    assert r["guests_created"] == 0
    assert client.get(f"{url}/households", headers=alice).json() == []
    bad = client.post(f"{url}/guests/import", headers=alice, json={"csv": "a;b\n1;2"})
    assert bad.status_code == 422


def test_guest_data_anonymized_90_days_after_wedding(client, alice, db):
    soon = (clock.today() + timedelta(days=30)).isoformat()
    w = client.post(
        f"{API}/weddings", headers=alice, json={"name": "Retencja", "wedding_date": soon}
    ).json()
    url = f"{API}/weddings/{w['id']}"
    h = client.post(
        f"{url}/households",
        headers=alice,
        json={"name": "Nowakowie", "contact_phone": "+48 600 000 000"},
    ).json()
    client.post(
        f"{url}/households/{h['id']}/guests",
        headers=alice,
        json={"first_name": "Jan", "last_name": "Nowak", "dietary_note": "orzechy"},
    )
    client.post(f"{url}/households/{h['id']}/rsvp-link", headers=alice)

    assert run_maintenance()["weddings_guests_anonymized"] == 0
    db.execute(update(Wedding).values(wedding_date=clock.today() - timedelta(days=91)))
    db.commit()
    assert run_maintenance()["weddings_guests_anonymized"] == 1

    db.expire_all()
    g = db.scalars(select(Guest)).one()
    assert (g.first_name, g.last_name, g.dietary_note_encrypted) == ("Gość 1", None, None)
    hh = db.scalars(select(Household)).one()
    assert (hh.name, hh.contact_phone) == ("Gospodarstwo", None)
    assert run_maintenance()["weddings_guests_anonymized"] == 0  # tylko raz


def test_csv_import_language_column(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    csv = (
        "household;first_name;language\n"
        "Smith family;John;angielski\nNowakowie;Ewa;\nX;Y;klingoński\n"
    )
    r = client.post(f"{url}/guests/import", headers=alice, json={"csv": csv, "dry_run": False})
    body = r.json()
    assert [e["row"] for e in body["errors"]] == [4]
    assert "Nieznany język" in body["errors"][0]["message"]
    assert body["guests_created"] == 0  # błąd w pliku: nic nie zapisujemy
    csv = "household;first_name;language\nSmith family;John;angielski\nNowakowie;Ewa;\n"
    client.post(f"{url}/guests/import", headers=alice, json={"csv": csv, "dry_run": False})
    langs = {
        h["name"]: h["language"] for h in client.get(f"{url}/households", headers=alice).json()
    }
    assert langs == {"Smith family": "en", "Nowakowie": None}
