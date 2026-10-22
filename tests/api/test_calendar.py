from datetime import date

from app.modules.calendar.service import _fold, to_ics

API = "/api/v1"


def test_calendar_entries_tasks_payments_events(client, alice, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    client.post(f"{w}/tasks", headers=alice, json={"title": "Kupić buty", "due_date": "2027-05-03"})
    cat = client.get(f"{w}/budget/categories", headers=alice).json()[0]
    item = client.post(
        f"{w}/budget/items",
        headers=alice,
        json={
            "category_id": cat["id"],
            "name": "DJ",
            "planned": {"amount": "4000", "currency": "PLN"},
        },
    ).json()
    client.post(
        f"{w}/budget/items/{item['id']}/payments",
        headers=alice,
        json={
            "kind": "advance_zaliczka",
            "amount": {"amount": "500", "currency": "PLN"},
            "due_date": "2027-05-04",
        },
    )
    r = client.get(
        f"{w}/calendar", headers=alice, params={"start": "2027-05-01", "end": "2027-05-31"}
    )
    assert r.status_code == 200, r.text
    entries = r.json()
    assert {"kind": "task", "title": "Kupić buty"}.items() <= next(
        e for e in entries if e["kind"] == "task" and e["title"] == "Kupić buty"
    ).items()
    pay = next(e for e in entries if e["kind"] == "payment")
    assert pay["title"] == "Zaliczka: DJ"
    assert pay["date"] == "2027-05-04"
    # Zakres dat: nic spoza maja.
    assert all("2027-05-01" <= e["date"] <= "2027-05-31" for e in entries)


def test_ics_feed_lifecycle(client, alice, bob, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    assert client.get(f"{w}/calendar-feed", headers=alice).json()["active"] is False
    r = client.post(f"{w}/calendar-feed", headers=alice)
    assert r.status_code == 201
    token = r.json()["token"]
    ics = client.get(f"{API}/calendar/{token}.ics")
    assert ics.status_code == 200
    assert ics.headers["content-type"].startswith("text/calendar")
    assert ics.text.startswith("BEGIN:VCALENDAR")
    assert "SUMMARY:" in ics.text
    assert " zł" not in ics.text  # bez kwot
    assert client.get(f"{w}/calendar-feed", headers=alice).json()["last_used_at"] is not None

    # Nowy adres unieważnia poprzedni.
    token2 = client.post(f"{w}/calendar-feed", headers=alice).json()["token"]
    assert client.get(f"{API}/calendar/{token}.ics").status_code == 404
    assert client.get(f"{API}/calendar/{token2}.ics").status_code == 200
    assert client.delete(f"{w}/calendar-feed", headers=alice).status_code == 204
    assert client.get(f"{API}/calendar/{token2}.ics").status_code == 404
    # Cudze wesele: brak dostępu.
    assert client.post(f"{w}/calendar-feed", headers=bob).status_code == 404


def test_ics_feed_stops_when_member_removed(client, alice, bob, wedding):
    from tests.api.test_workspace import invite_and_accept

    w = f"{API}/weddings/{wedding['id']}"
    invite_and_accept(client, alice, bob, wedding, "bob@example.com", role="viewer")
    token = client.post(f"{w}/calendar-feed", headers=bob).json()["token"]
    assert client.get(f"{API}/calendar/{token}.ics").status_code == 200
    bob_id = client.get(f"{API}/me", headers=bob).json()["id"]
    assert client.delete(f"{w}/members/{bob_id}", headers=alice).status_code == 204
    assert client.get(f"{API}/calendar/{token}.ics").status_code == 404


def test_ics_format_escaping_and_folding():
    entry = {
        "kind": "event",
        "date": date(2027, 8, 7),
        "time": "15:00",
        "title": "Ceremonia; kościół, Kraków",
        "ref_id": "x",
        "done": False,
    }
    text = to_ics("Ala; i Bartek", [entry])
    assert "SUMMARY:15:00 Ceremonia\\; kościół\\, Kraków" in text
    assert "X-WR-CALNAME:Ala\\; i Bartek" in text
    assert "DTSTART;VALUE=DATE:20270807" in text
    assert text.endswith(chr(13) + chr(10))
    long = _fold("SUMMARY:" + "ż" * 80)
    assert all(len(part.encode()) <= 75 for part in long.split(chr(13) + chr(10)))
