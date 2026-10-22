"""Kalendarz i ICS: przypomnienia z nowych modułów (dokumenty, ceny, oddanie zdjęć, objazdy)."""

from datetime import date

from app.core import clock
from tests.api.test_offers import pln

API = "/api/v1"


def test_reminders_in_calendar_and_ics(client, alice, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2027, 10, 1))
    w = client.post(
        f"{API}/weddings",
        headers=alice,
        json={"name": "W", "ceremony_type": "civil", "wedding_date": "2028-07-01"},
    ).json()
    url = f"{API}/weddings/{w['id']}"
    cat = client.get(f"{url}/budget/categories", headers=alice).json()[0]["id"]
    client.post(
        f"{url}/budget/items",
        headers=alice,
        json={
            "category_id": cat,
            "name": "Sala",
            "planned": pln("40000"),
            "indexation": "cpi",
            "price_review_on": "2028-01-15",
        },
    )
    client.post(
        f"{url}/deliverables", headers=alice, json={"title": "Film", "due_on": "2028-09-30"}
    )
    for name in ("Babcia", "Wujek"):
        client.post(
            f"{url}/households",
            headers=alice,
            json={
                "name": name,
                "delivery_method": "in_person",
                "delivery_planned_on": "2028-02-12",
            },
        )

    r = client.get(f"{url}/calendar?start=2027-10-01&end=2028-12-31", headers=alice)
    assert r.status_code == 200, r.text
    reminders = {e["title"]: e for e in r.json() if e["kind"] == "reminder"}
    assert (
        reminders["Od dziś: Zapewnienie w USC o braku przeszkód do małżeństwa"]["date"]
        == "2028-01-01"
    )
    assert (
        reminders["Najpóźniej: Zapewnienie w USC o braku przeszkód do małżeństwa"]["date"]
        == "2028-05-31"
    )
    assert reminders["Aneks lub potwierdzenie ceny: Sala"]["link"] == "budzet"
    assert reminders["Termin oddania: Film"]["date"] == "2028-09-30"
    # Objazd: liczba zaproszeń, bez nazwisk.
    assert reminders["Objazd z zaproszeniami (2)"]["link"] == "zaproszenia"
    assert not any("Babcia" in t for t in reminders)

    token = client.post(f"{url}/calendar-feed", headers=alice).json()["token"]
    ics = client.get(f"{API}/calendar/{token}.ics").text
    assert "CATEGORIES:Przypomnienie" in ics
    assert "Objazd z zaproszeniami (2)" in ics
    assert "Babcia" not in ics
