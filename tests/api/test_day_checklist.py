"""„Co zabrać” na dzień ślubu."""

from tests.api.test_offers import pln
from tests.api.test_workspace import invite_and_accept

API = "/api/v1"


def test_typical_list_envelopes_and_coordinator(client, alice, user_factory):
    w = client.post(
        f"{API}/weddings",
        headers=alice,
        json={"name": "W", "ceremony_type": "civil", "wedding_date": "2028-07-01"},
    ).json()
    url = f"{API}/weddings/{w['id']}"
    cat = client.get(f"{url}/budget/categories", headers=alice).json()[0]["id"]
    item = client.post(
        f"{url}/budget/items",
        headers=alice,
        json={"category_id": cat, "name": "Zespół", "planned": pln("8000")},
    ).json()
    client.post(
        f"{url}/budget/items/{item['id']}/payments",
        headers=alice,
        json={"kind": "final", "amount": pln("6000"), "due_date": "2028-07-01"},
    )
    r = client.post(f"{url}/day-checklist/typical", headers=alice)
    assert r.status_code == 200, r.text
    titles = [i["title"] for i in r.json()]
    assert titles[0] == "Obrączki"
    assert "Koperta: Zespół (dopłata)" in titles
    assert "6000" not in str(r.json())  # bez kwot (koordynator nie widzi budżetu)
    # Ponowne wczytanie nie dubluje pozycji.
    again = client.post(f"{url}/day-checklist/typical", headers=alice).json()
    assert len(again) == len(titles)

    own = client.post(
        f"{url}/day-checklist", headers=alice, json={"title": "Głośnik", "who": "Tomek"}
    )
    assert own.status_code == 201
    stale = client.patch(
        f"{url}/day-checklist/{own.json()['id']}",
        headers={**alice, "If-Match": '"9"'},
        json={"who": None},
    )
    assert stale.status_code == 409

    coordinator = user_factory("swiadek@example.com")
    invite_and_accept(client, alice, coordinator, w, "swiadek@example.com", role="coordinator")
    rings = r.json()[0]
    assert client.get(f"{url}/day-checklist", headers=coordinator).status_code == 200
    done = client.put(
        f"{url}/day-checklist/{rings['id']}/done", headers=coordinator, json={"done": True}
    )
    assert done.status_code == 200, done.text
    assert done.json()["done"] is True
    # Koordynator odhacza, ale nie edytuje listy.
    assert (
        client.post(f"{url}/day-checklist", headers=coordinator, json={"title": "X"}).status_code
        == 403
    )
    assert (
        client.delete(f"{url}/day-checklist/{rings['id']}", headers=coordinator).status_code == 403
    )
