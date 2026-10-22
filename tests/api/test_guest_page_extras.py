"""Strona gościa: „Gdzie siedzimy”, komunikat i księga życzeń (propozycje 7, 8 i 9 z analizy 07)."""

from sqlalchemy import select

from app.jobs.queue import Job
from tests.api.test_seating import table, url
from tests.api.test_workspace import invite_and_accept

API = "/api/v1"


def _household(client, headers, w, name, *first_names, **kw):
    h = client.post(f"{w}/households", headers=headers, json={"name": name, **kw}).json()
    guests = [
        client.post(
            f"{w}/households/{h['id']}/guests", headers=headers, json={"first_name": f}
        ).json()
        for f in first_names
    ]
    token = client.post(f"{w}/households/{h['id']}/rsvp-link", headers=headers).json()["token"]
    return h, guests, token


def test_guest_sees_only_own_table_when_published(client, alice, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    _, (jan, ewa), token = _household(client, alice, w, "Nowakowie", "Jan", "Ewa")
    _, (obcy,), _ = _household(client, alice, w, "Kowalscy", "Adam")
    t5 = table(client, alice, wedding, "Stół 5", 8)
    for g, seat in ((jan, 1), (ewa, 2), (obcy, 3)):
        r = client.put(
            f"{url(wedding)}/guests/{g['id']}",
            headers=alice,
            json={"table_id": t5["id"], "seat_number": seat},
        )
        assert r.status_code == 204, r.text
    assert client.get(f"{API}/rsvp/{token}").json()["tables"] is None

    r = client.put(f"{w}/guest-page", headers=alice, json={"show_tables": True})
    assert r.json()["show_tables"] is True
    tables = client.get(f"{API}/rsvp/{token}").json()["tables"]
    # Tylko swoje zaproszenie — bez Adama z innej rodziny.
    assert tables == [
        {"first_name": "Ewa", "table": "Stół 5", "seat_number": 2},
        {"first_name": "Jan", "table": "Stół 5", "seat_number": 1},
    ]


def test_announcement_banner_and_single_email(client, alice, wedding, db):
    w = f"{API}/weddings/{wedding['id']}"
    _, _, token = _household(
        client, alice, w, "Nowakowie", "Jan", contact_email="nowak@example.com"
    )
    _household(client, alice, w, "Smith", "John", contact_email="smith@example.com", language="en")
    _household(client, alice, w, "Bez maila", "Ola")
    r = client.post(f"{w}/guest-page/announcement/email", headers=alice, json={"dry_run": True})
    assert (r.status_code, r.json()["code"]) == (409, "announcement.empty")

    s = client.put(
        f"{w}/guest-page/announcement",
        headers=alice,
        json={"text": "  Ceremonia przesunięta na 16:30.  "},
    ).json()
    assert s["announcement"] == "Ceremonia przesunięta na 16:30."
    assert (s["households"], s["households_with_email"]) == (3, 2)
    banner = client.get(f"{API}/rsvp/{token}").json()["announcement"]
    assert banner["text"] == "Ceremonia przesunięta na 16:30."

    preview = client.post(
        f"{w}/guest-page/announcement/email", headers=alice, json={"dry_run": True}
    ).json()
    assert preview == {"dry_run": True, "recipients": 2}
    sent = client.post(f"{w}/guest-page/announcement/email", headers=alice, json={"dry_run": False})
    assert sent.json() == {"dry_run": False, "recipients": 2}
    jobs = db.scalars(
        select(Job).where(Job.payload["to"].astext.in_(["nowak@example.com", "smith@example.com"]))
    ).all()
    subjects = sorted(j.payload["subject"] for j in jobs)
    assert subjects[0].endswith("a message from the couple")
    assert subjects[1].endswith("wiadomość od pary młodej")
    assert all("/rsvp/" not in j.payload["body"] for j in jobs)  # bez nowego linku
    again = client.post(
        f"{w}/guest-page/announcement/email", headers=alice, json={"dry_run": False}
    )
    assert (again.status_code, again.json()["code"]) == (409, "announcement.already_sent")

    # Nowa treść = można wysłać ponownie; pusty tekst usuwa baner.
    s = client.put(f"{w}/guest-page/announcement", headers=alice, json={"text": "Inna"}).json()
    assert s["announcement_emailed_at"] is None
    client.put(f"{w}/guest-page/announcement", headers=alice, json={"text": ""})
    assert client.get(f"{API}/rsvp/{token}").json()["announcement"] is None


def test_wishes_guest_writes_couple_hides(client, alice, user_factory, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    h, _, token = _household(client, alice, w, "Nowakowie", "Jan")
    wish = {"author": "Ciocia Basia", "text": "Sto lat, kochani!"}
    r = client.post(f"{API}/rsvp/{token}/wishes", json=wish)
    assert (r.status_code, r.json()["code"]) == (404, "rsvp.wishes_disabled")

    client.put(f"{w}/guest-page", headers=alice, json={"wishes_enabled": True})
    r = client.post(f"{API}/rsvp/{token}/wishes", json=wish)
    assert r.status_code == 201, r.text
    assert r.json()["wishes"] == {"limit": 5, "mine": [wish]}
    for i in range(4):
        assert client.post(f"{API}/rsvp/{token}/wishes", json={**wish, "text": str(i)}).is_success
    over = client.post(f"{API}/rsvp/{token}/wishes", json=wish)
    assert (over.status_code, over.json()["code"]) == (409, "rsvp.wishes_limit")

    rows = client.get(f"{w}/wishes", headers=alice).json()
    assert len(rows) == 5
    assert rows[0]["household_name"] == "Nowakowie"
    rows = client.put(
        f"{w}/wishes/{rows[1]['id']}/hidden", headers=alice, json={"hidden": True}
    ).json()
    assert rows[1]["hidden"] is True
    assert client.delete(f"{w}/wishes/{rows[2]['id']}", headers=alice).status_code == 204

    viewer = user_factory("ogladam@example.com")
    invite_and_accept(client, alice, viewer, wedding, "ogladam@example.com", role="viewer")
    assert len(client.get(f"{w}/wishes", headers=viewer).json()) == 4
    r = client.put(f"{w}/wishes/{rows[0]['id']}/hidden", headers=viewer, json={"hidden": True})
    assert r.status_code == 403

    # Usunięcie zaproszenia zostawia życzenia (pamiątka), bez powiązania z rodziną.
    assert client.delete(f"{w}/households/{h['id']}", headers=alice).status_code == 204
    rows = client.get(f"{w}/wishes", headers=alice).json()
    assert len(rows) == 4
    assert rows[0]["household_name"] is None
    assert len(client.get(f"{w}/export", headers=alice).json()["guest_wishes"]) == 4
