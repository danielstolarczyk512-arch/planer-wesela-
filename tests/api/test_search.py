"""Wyszukiwarka w weselu (N1 z analizy 08)."""

from tests.api.test_offers import vendor
from tests.api.test_workspace import invite_and_accept

API = "/api/v1"


def test_search_tasks_guests_vendors_expenses(client, alice, user_factory, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    client.post(f"{url}/tasks", headers=alice, json={"title": "Zarezerwować kwiaty 100%"})
    h = client.post(f"{url}/households", headers=alice, json={"name": "Kwiatkowscy"}).json()
    client.post(f"{url}/households/{h['id']}/guests", headers=alice, json={"first_name": "Ola"})
    vendor(client, alice, wedding, "Kwiaciarnia Róża", "florist")
    cat = client.get(f"{url}/budget/categories", headers=alice).json()[0]["id"]
    client.post(
        f"{url}/budget/items",
        headers=alice,
        json={
            "category_id": cat,
            "name": "Kwiaty na stoły",
            "planned": {"amount": "900", "currency": "PLN"},
        },
    )
    r = client.get(f"{url}/search", headers=alice, params={"q": "  kWIa "})
    assert r.status_code == 200, r.text
    hits = r.json()["results"]
    assert {(x["kind"], x["title"]) for x in hits} == {
        ("task", "Zarezerwować kwiaty 100%"),
        ("guest", "Ola"),
        ("vendor", "Kwiaciarnia Róża"),
        ("expense", "Kwiaty na stoły"),
    }
    guest = next(x for x in hits if x["kind"] == "guest")
    assert (guest["id"], guest["subtitle"]) == (h["id"], "Kwiatkowscy")
    # Znaki % i _ dosłownie, za krótkie zapytanie — pusto.
    assert [
        x["title"]
        for x in client.get(f"{url}/search", headers=alice, params={"q": "0%"}).json()["results"]
    ] == ["Zarezerwować kwiaty 100%"]
    assert client.get(f"{url}/search", headers=alice, params={"q": "k"}).json()["results"] == []

    coordinator = user_factory("swiadek@example.com")
    invite_and_accept(
        client, alice, coordinator, wedding, "swiadek@example.com", role="coordinator"
    )
    assert client.get(f"{url}/search", headers=coordinator, params={"q": "kwia"}).status_code in (
        403,
        404,
    )
