"""„Wymaga uwagi” na ekranie Dziś: ostrzeżenia z modułów w jednym miejscu."""

from datetime import date

from app.core import clock
from tests.api.test_workspace import invite_and_accept

API = "/api/v1"


def test_attention_collects_and_sorts(client, alice, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2028, 3, 1))
    w = client.post(
        f"{API}/weddings",
        headers=alice,
        json={"name": "W", "ceremony_type": "concordat", "wedding_date": "2028-07-01"},
    ).json()
    url = f"{API}/weddings/{w['id']}"
    assert client.get(f"{url}/attention", headers=alice).json() == []

    # Świadectwo chrztu za wcześnie i przepełniony kurs (błędy), zdjęcia po terminie.
    client.put(f"{url}/ceremony-documents/baptism", headers=alice, json={"issued_on": "2027-11-01"})
    run = client.post(
        f"{url}/transport-runs", headers=alice, json={"name": "Bus", "capacity": 1}
    ).json()["runs"][0]
    h = client.post(f"{url}/households", headers=alice, json={"name": "R"}).json()
    ids = [
        client.post(
            f"{url}/households/{h['id']}/guests", headers=alice, json={"first_name": n}
        ).json()["id"]
        for n in ("A", "B")
    ]
    client.put(f"{url}/transport-runs/{run['id']}/guests", headers=alice, json={"guest_ids": ids})
    client.post(
        f"{url}/deliverables",
        headers=alice,
        json={"title": "Sesja narzeczeńska", "due_on": "2028-02-01"},
    )

    items = client.get(f"{url}/attention", headers=alice).json()
    codes = [i["code"] for i in items]
    assert set(codes) >= {"documents.expires", "transport.over", "deliverable.overdue"}
    # Najpierw błędy, potem ostrzeżenia.
    severities = [i["severity"] for i in items]
    assert severities == sorted(severities, key={"error": 0, "warning": 1, "info": 2}.get)
    links = {i["code"]: i["link"] for i in items}
    assert (links["documents.expires"], links["transport.over"]) == ("formalnosci", "logistyka")


def test_attention_requires_read(client, alice, user_factory, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    coordinator = user_factory("swiadek@example.com")
    invite_and_accept(
        client, alice, coordinator, wedding, "swiadek@example.com", role="coordinator"
    )
    assert client.get(f"{url}/attention", headers=coordinator).status_code == 403
