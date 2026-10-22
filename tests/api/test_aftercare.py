"""Po weselu (propozycja 10 z docs/analysis/05)."""

from datetime import UTC, date, datetime

from sqlalchemy import select

from app.core import clock
from app.jobs.queue import Job
from app.modules.notifications import service as notifications
from tests.api.test_offers import pln, vendor

API = "/api/v1"


def test_after_wedding_overview(client, alice, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2028, 7, 20))
    w = client.post(
        f"{API}/weddings",
        headers=alice,
        json={"name": "W", "ceremony_type": "civil", "wedding_date": "2028-07-01"},
    ).json()
    url = f"{API}/weddings/{w['id']}"
    photo = vendor(client, alice, w, "Fotograf", "photographer")
    cat = client.get(f"{url}/budget/categories", headers=alice).json()[0]["id"]
    item = client.post(
        f"{url}/budget/items",
        headers=alice,
        json={"category_id": cat, "name": "Sala", "planned": pln("30000")},
    ).json()
    client.post(
        f"{url}/budget/items/{item['id']}/payments",
        headers=alice,
        json={"kind": "final", "amount": pln("5000"), "due_date": "2028-07-10"},
    )
    h = client.post(f"{url}/households", headers=alice, json={"name": "Nowakowie"}).json()
    client.patch(
        f"{url}/households/{h['id']}",
        headers={**alice, "If-Match": '"1"'},
        json={"gift_note": "koperta", "thanked": True},
    )

    r = client.post(
        f"{url}/deliverables",
        headers=alice,
        json={"title": "Zdjęcia — galeria", "vendor_id": photo["id"], "due_on": "2028-07-15"},
    )
    assert r.status_code == 201, r.text
    o = r.json()
    assert o["after_wedding"] is True
    d = o["deliverables"][0]
    assert (d["status"], d["days_late"], d["vendor_name"]) == ("overdue", 5, "Fotograf")
    assert o["open_payments"][0]["amount"] == pln("5000.00")
    assert o["open_payments"][0]["overdue"] is True
    assert o["thanks"] == {"with_gift": 1, "thanked_with_gift": 1, "thanked": 1}
    id_card = next(i for i in o["name_change"] if i["code"] == "id_card")
    assert id_card["approx_deadline"] == "2028-10-29"  # 120 dni po ślubie
    assert id_card["source"].startswith("https://www.gov.pl/")

    # Odebrane (If-Match), potem odhaczenie pozycji zmiany nazwiska.
    done = client.patch(
        f"{url}/deliverables/{d['id']}",
        headers={**alice, "If-Match": f'"{d["version"]}"'},
        json={"received_on": "2028-07-20"},
    ).json()
    assert done["deliverables"][0]["status"] == "received"
    o = client.put(f"{url}/after-checks/bank", headers=alice, json={"done": True}).json()
    assert next(i for i in o["name_change"] if i["code"] == "bank")["done_on"] == "2028-07-20"
    o = client.put(f"{url}/after-checks/bank", headers=alice, json={"done": False}).json()
    assert next(i for i in o["name_change"] if i["code"] == "bank")["done_on"] is None
    assert (
        client.put(f"{url}/after-checks/xyz", headers=alice, json={"done": True}).status_code == 404
    )


def test_overdue_deliverable_in_digest(client, alice, db, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2028, 8, 1))
    w = client.post(
        f"{API}/weddings",
        headers=alice,
        json={"name": "D", "ceremony_type": "civil", "wedding_date": "2028-07-01"},
    ).json()
    client.post(
        f"{API}/weddings/{w['id']}/deliverables",
        headers=alice,
        json={"title": "Film", "due_on": "2028-07-25"},
    )
    assert notifications.send_digests(db, now=datetime(2028, 8, 1, 9, tzinfo=UTC)) == 1
    body = (
        db.scalars(select(Job).where(Job.payload["subject"].astext.like("Wesele:%")))
        .one()
        .payload["body"]
    )
    assert "Od usługodawców po weselu" in body
    assert "Film: termin minął 25.07.2028" in body
