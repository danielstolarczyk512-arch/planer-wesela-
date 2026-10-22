from app.modules.vendors.checklists import QUESTIONS, standard
from tests.api.test_offers import offer, pln, vendor

API = "/api/v1"


def test_standard_questions_by_category_without_duplicates(client, alice, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    sala = vendor(client, alice, wedding, "Dworek")
    url = f"{w}/vendors/{sala['id']}/checklist"
    r = client.post(f"{url}/standard", headers=alice, json={"kind": "question"})
    assert r.status_code == 200, r.text
    assert [i["code"] for i in r.json()] == [t.code for t in QUESTIONS["venue"]]
    # Ponowne dodanie nie tworzy duplikatów.
    again = client.post(f"{url}/standard", headers=alice, json={"kind": "question"}).json()
    assert len(again) == len(QUESTIONS["venue"])

    contract = client.post(f"{url}/standard", headers=alice, json={"kind": "contract"}).json()
    assert {"c_deposit", "c_min_guests"} <= {i["code"] for i in contract}
    assert all(i["status"] == "open" for i in contract)

    other = vendor(client, alice, wedding, "Pan Kanapka", category="other")
    generic = client.post(
        f"{w}/vendors/{other['id']}/checklist/standard", headers=alice, json={"kind": "question"}
    ).json()
    assert len(generic) == len(standard("question", "other"))


def test_answer_marks_question_done_and_contract_status(client, alice, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    dj = vendor(client, alice, wedding, "DJ Marek", category="dj")
    items = client.post(
        f"{w}/vendors/{dj['id']}/checklist/standard", headers=alice, json={"kind": "question"}
    ).json()
    first = items[0]
    r = client.patch(
        f"{w}/vendor-checklist/{first['id']}",
        headers={**alice, "If-Match": f'"{first["version"]}"'},
        json={"answer": "  8 godzin, 3 przerwy  "},
    )
    assert r.status_code == 200, r.text
    assert r.json()["answer"] == "8 godzin, 3 przerwy"
    assert r.json()["status"] == "ok"
    stale = client.patch(
        f"{w}/vendor-checklist/{first['id']}",
        headers={**alice, "If-Match": f'"{first["version"]}"'},
        json={"answer": "x"},
    )
    assert stale.status_code == 409

    custom = client.post(
        f"{w}/vendors/{dj['id']}/checklist",
        headers=alice,
        json={"kind": "contract", "text": "Kara umowna za spóźnienie"},
    )
    assert custom.status_code == 201
    c = custom.json()
    r = client.patch(
        f"{w}/vendor-checklist/{c['id']}",
        headers={**alice, "If-Match": '"1"'},
        json={"status": "missing"},
    )
    assert r.json()["status"] == "missing"

    listed = client.get(f"{w}/vendor-checklist", headers=alice, params={"kind": "contract"}).json()
    assert [i["id"] for i in listed] == [c["id"]]
    assert client.delete(f"{w}/vendor-checklist/{c['id']}", headers=alice).status_code == 204
    assert (
        client.get(f"{w}/vendor-checklist", headers=alice, params={"kind": "contract"}).json() == []
    )


def test_checklist_is_private_to_wedding(client, alice, bob, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    sala = vendor(client, alice, wedding, "Sala")
    item = client.post(
        f"{w}/vendors/{sala['id']}/checklist", headers=alice, json={"text": "Parking?"}
    ).json()
    other = client.post(f"{API}/weddings", headers=bob, json={"name": "Inne"}).json()
    r = client.patch(
        f"{API}/weddings/{other['id']}/vendor-checklist/{item['id']}",
        headers={**bob, "If-Match": '"1"'},
        json={"answer": "x"},
    )
    assert r.status_code == 404


def test_crew_meals_priced_in_venue_offer(client, alice, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    sala = vendor(client, alice, wedding, "Sala")
    band = vendor(client, alice, wedding, "Zespół", category="band")
    r = client.patch(
        f"{w}/vendors/{band['id']}", headers={**alice, "If-Match": '"1"'}, json={"crew_meals": 5}
    )
    assert r.status_code == 200, r.text
    assert r.json()["crew_meals"] == 5
    rejected = vendor(client, alice, wedding, "Inny fotograf", category="photographer")
    client.patch(
        f"{w}/vendors/{rejected['id']}",
        headers={**alice, "If-Match": '"1"'},
        json={"crew_meals": 2, "status": "rejected"},
    )
    o = offer(
        client,
        alice,
        wedding,
        sala["id"],
        components=[
            {"label": "Menu", "kind": "per_guest", "amount": "300"},
            {"label": "Posiłek dla obsługi", "kind": "per_crew", "amount": "120"},
        ],
    )
    r = client.post(
        f"{w}/offers/compare", headers=alice, json={"offer_ids": [o["id"]], "adults": 100}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["scenario"]["crew"] == 5  # odrzucony fotograf się nie liczy
    assert body["results"][0]["total"] == pln("30600.00")  # 100x300 + 5x120
    override = client.post(
        f"{w}/offers/compare",
        headers=alice,
        json={"offer_ids": [o["id"]], "adults": 100, "crew": 0},
    ).json()
    assert override["results"][0]["total"] == pln("30000.00")
