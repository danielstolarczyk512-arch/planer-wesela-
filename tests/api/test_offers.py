from datetime import date, timedelta

from tests.api.test_documents import drain_jobs, pdf_sample, upload

API = "/api/v1"


def pln(a):
    return {"amount": a, "currency": "PLN"}


def vendor(client, headers, wedding, name, category="venue"):
    r = client.post(
        f"{API}/weddings/{wedding['id']}/vendors",
        headers=headers,
        json={"name": name, "category": category},
    )
    assert r.status_code == 201, r.text
    return r.json()


def offer(client, headers, wedding, vendor_id, **kw):
    body = {"vendor_id": vendor_id, "title": "Pakiet", **kw}
    r = client.post(f"{API}/weddings/{wedding['id']}/offers", headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()


SALA_A = [
    {"label": "Menu", "kind": "per_guest", "amount": "330"},
    {"label": "Dzieci", "kind": "per_child", "amount": "165"},
    {"label": "Poprawiny", "kind": "per_guest", "amount": "150", "event_kind": "after_party"},
    {"label": "Napoje", "kind": "per_guest", "amount": "0", "included": True},
]
SALA_B = [
    {"label": "Menu", "kind": "per_guest", "amount": "289"},
    {"label": "Napoje i alkohol", "kind": "per_guest", "amount": "45"},
    {"label": "Obsługa", "kind": "percent", "amount": "10"},
    {"label": "Wiejski stół", "kind": "fixed", "amount": None},
]
TERMS_A = [
    {
        "term_type": "deposit",
        "amount": pln("5000"),
        "deposit_kind": "deposit_zadatek",
        "due_date": "2026-12-01",
    },
    {
        "term_type": "payment_schedule",
        "installments": [
            {"kind": "installment", "amount": pln("10000"), "days_before_wedding": 30},
            {"kind": "final", "amount": pln("20000"), "days_before_wedding": 1},
        ],
    },
    {"term_type": "cancellation", "text": "Zadatek przepada przy odwołaniu."},
    {"term_type": "drinks", "text": "Napoje bezalkoholowe w cenie."},
]


def test_compare_by_hand(client, alice, wedding):
    a = offer(
        client,
        alice,
        wedding,
        vendor(client, alice, wedding, "Sala A")["id"],
        min_guests=80,
        components=SALA_A,
        terms=TERMS_A,
    )
    b = offer(
        client, alice, wedding, vendor(client, alice, wedding, "Sala B")["id"], components=SALA_B
    )
    r = client.post(
        f"{API}/weddings/{wedding['id']}/offers/compare",
        headers=alice,
        json={
            "offer_ids": [a["id"], b["id"]],
            "adults": 100,
            "children": 8,
            "after_party_adults": 60,
            "after_party_children": 0,
        },
    )
    assert r.status_code == 200, r.text
    res = {x["offer_id"]: x for x in r.json()["results"]}
    # A: 100x330 + 8x165 + 60x150 = 33 000 + 1 320 + 9 000 = 43 320
    assert res[a["id"]]["total"] == pln("43320.00")
    assert res[a["id"]]["missing_terms"] == []
    # B: brak ceny dzieci → 108 os.: menu 108x289 = 31 212, napoje 108x45 = 4 860;
    # suma 36 072 + 10% obsługi 3 607,20 → 39 679,20; wiejski stół nieznany
    assert res[b["id"]]["total"] == pln("39679.20")
    assert res[b["id"]]["unknown"] == ["Wiejski stół"]
    assert any(w.startswith("offer.no_child_price") for w in res[b["id"]]["warnings"])
    assert len(res[b["id"]]["missing_terms"]) == 3
    assert r.json()["cheapest_offer_id"] == b["id"]
    assert res[a["id"]]["difference_to_cheapest"] == pln("3640.80")


def test_scenarios_difference_and_final_payment(client, alice, wedding):
    a = offer(
        client,
        alice,
        wedding,
        vendor(client, alice, wedding, "Sala A")["id"],
        components=SALA_A,
        terms=TERMS_A,
    )
    b = offer(
        client, alice, wedding, vendor(client, alice, wedding, "Sala B")["id"], components=SALA_B
    )
    base = {"children": 0, "after_party_adults": 0, "after_party_children": 0}
    r = client.post(
        f"{API}/weddings/{wedding['id']}/offers/scenarios",
        headers=alice,
        json={
            "offer_ids": [a["id"], b["id"]],
            "scenarios": [
                {"label": "Plan", "adults": 100, **base},
                {"label": "Co jeśli +20", "adults": 120, **base},
            ],
        },
    )
    assert r.status_code == 200, r.text
    res = {x["offer_id"]: x for x in r.json()["results"]}
    plan, more = res[a["id"]]["scenarios"]
    assert (plan["label"], more["label"]) == ("Plan", "Co jeśli +20")
    assert plan["total"] == pln("33000.00")
    assert more["total"] == pln("39600.00")
    # Różnica = 20 dorosłych x 330 zł; pierwszy scenariusz to punkt odniesienia.
    assert more["difference_to_first"] == pln("6600.00")
    assert plan["difference_to_first"] == pln("0.00")
    # Dopłata = suma - zadatek 5 000 - rata 10 000; rośnie o całą różnicę.
    assert plan["final_payment"] == pln("18000.00")
    assert more["final_payment"] == pln("24600.00")
    assert more["final_difference_to_first"] == pln("6600.00")
    anchor = date(2027, 8, 1)
    assert [
        (p["kind"], p["amount"]["amount"], p["due_date"], p["computed"]) for p in more["payments"]
    ] == [
        ("deposit_zadatek", "5000.00", "2026-12-01", False),
        ("installment", "10000.00", (anchor - timedelta(days=30)).isoformat(), False),
        ("final", "24600.00", (anchor - timedelta(days=1)).isoformat(), True),
    ]
    # Oferta bez warunków płatności: cała kwota jako dopłata bez terminu.
    b_more = res[b["id"]]["scenarios"][1]
    assert b_more["payments"] == [
        {"kind": "final", "amount": b_more["total"], "due_date": None, "computed": True}
    ]

    one = client.post(
        f"{API}/weddings/{wedding['id']}/offers/scenarios",
        headers=alice,
        json={"offer_ids": [a["id"]], "scenarios": [{"label": "Plan"}]},
    )
    assert one.status_code == 422


def test_compare_uses_guest_list(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    a = offer(
        client, alice, wedding, vendor(client, alice, wedding, "Sala")["id"], components=SALA_A[:2]
    )
    h = client.post(f"{url}/households", headers=alice, json={"name": "R"}).json()
    for name, age in [("A", "adult"), ("B", "teen"), ("C", "child"), ("D", "infant")]:
        client.post(
            f"{url}/households/{h['id']}/guests",
            headers=alice,
            json={"first_name": name, "age_group": age},
        )
    r = client.post(
        f"{url}/offers/compare",
        headers=alice,
        json={"offer_ids": [a["id"]], "guest_basis": "invited"},
    ).json()
    # dorośli: adult + teen = 2 x 330; dzieci: 1 x 165; niemowlę bezpłatne → 825
    assert r["scenario"]["adults"] == 2
    assert r["scenario"]["children"] == 1
    assert r["results"][0]["total"] == pln("825.00")


def test_draft_needs_approval_and_edit_requires_reapproval(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}/offers"
    v = vendor(client, alice, wedding, "Fotograf", "photographer")
    o = offer(
        client,
        alice,
        wedding,
        v["id"],
        status="draft",
        components=[
            {"label": "Pakiet", "kind": "fixed", "amount": "6800", "confidence": "unverified"}
        ],
    )
    r = client.post(f"{url}/compare", headers=alice, json={"offer_ids": [o["id"]]})
    assert r.status_code == 409
    assert r.json()["code"] == "offer.not_approved"

    r = client.post(f"{url}/{o['id']}/approve", headers=alice, json={})
    assert r.json()["code"] == "offer.unverified_fields"
    r = client.post(f"{url}/{o['id']}/approve", headers=alice, json={"confirm_unverified": True})
    assert r.json()["status"] == "approved"

    r = client.patch(
        f"{url}/{o['id']}",
        headers={**alice, "If-Match": f'"{r.json()["version"]}"'},
        json={"components": [{"label": "Pakiet", "kind": "fixed", "amount": "7200"}]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "needs_review"
    assert r.json()["components"][0]["amount"] == "7200.00"


def test_citations_must_exist_in_document(client, alice, wedding):
    sample = pdf_sample()
    doc = upload(client, alice, wedding, sample).json()
    drain_jobs()
    version_id = doc["versions"][0]["id"]
    v = vendor(client, alice, wedding, "Sala z PDF")
    ok = client.post(
        f"{API}/weddings/{wedding['id']}/offers",
        headers=alice,
        json={
            "vendor_id": v["id"],
            "title": "Z dokumentu",
            "source_document_version_id": version_id,
            "components": [
                {
                    "label": "Menu",
                    "kind": "per_guest",
                    "amount": "330",
                    "citation": {"page": 1, "quote": "330  zł za osobę dorosłą"},
                }
            ],
        },
    )
    assert ok.status_code == 201, ok.text
    bad = client.post(
        f"{API}/weddings/{wedding['id']}/offers",
        headers=alice,
        json={
            "vendor_id": v["id"],
            "title": "Zmyślone",
            "source_document_version_id": version_id,
            "components": [
                {
                    "label": "Menu",
                    "kind": "per_guest",
                    "amount": "99",
                    "citation": {"quote": "99 zł za osobę"},
                }
            ],
        },
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "offer.citation_not_found"
    no_doc = client.post(
        f"{API}/weddings/{wedding['id']}/offers",
        headers=alice,
        json={
            "vendor_id": v["id"],
            "title": "X",
            "components": [
                {"label": "M", "kind": "fixed", "amount": "1", "citation": {"quote": "cokolwiek"}}
            ],
        },
    )
    assert no_doc.json()["code"] == "offer.citation_without_document"


def test_select_creates_budget_item_and_payments(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    va = vendor(client, alice, wedding, "Sala A")
    a = offer(client, alice, wedding, va["id"], min_guests=80, components=SALA_A, terms=TERMS_A)
    b = offer(
        client, alice, wedding, vendor(client, alice, wedding, "Sala B")["id"], components=SALA_B
    )
    r = client.post(f"{url}/offers/{a['id']}/select", headers=alice, json={})
    assert r.status_code == 200, r.text
    s = r.json()
    # guest_basis=planned: 110 dorosłych x 330 + poprawiny 110 x 150 = 36 300 + 16 500 = 52 800
    assert s["planned_amount"] == pln("52800.00")
    assert s["payments_created"] == 3
    assert s["rejected_offers"] == 1

    item = client.get(f"{url}/budget/items/{s['budget_item_id']}", headers=alice).json()
    assert item["estimated"] == pln("52800.00")
    payments = client.get(
        f"{url}/budget/items/{s['budget_item_id']}/payments", headers=alice
    ).json()
    # planned_month 2027-08 → kotwica 2027-08-01
    assert [(p["kind"], p["due_date"]) for p in payments] == [
        ("deposit_zadatek", "2026-12-01"),
        ("installment", (date(2027, 8, 1) - timedelta(days=30)).isoformat()),
        ("final", (date(2027, 8, 1) - timedelta(days=1)).isoformat()),
    ]
    assert client.get(f"{url}/vendors/{va['id']}", headers=alice).json()["status"] == "booked"
    assert client.get(f"{url}/offers/{b['id']}", headers=alice).json()["status"] == "rejected"
    cat = client.get(f"{url}/budget/categories", headers=alice).json()
    sala = next(c for c in cat if c["id"] == item["category_id"])
    assert sala["name"] == "Sala i catering"

    again = client.post(f"{url}/offers/{a['id']}/select", headers=alice, json={})
    assert again.status_code == 409
    assert client.post(f"{url}/offers/{a['id']}/reject", headers=alice).status_code == 409


def test_term_validation(client, alice, wedding):
    v = vendor(client, alice, wedding, "X")
    url = f"{API}/weddings/{wedding['id']}/offers"
    bad_terms = [
        [{"term_type": "deposit", "amount": pln("100")}],
        [{"term_type": "payment_schedule"}],
        [
            {
                "term_type": "payment_schedule",
                "installments": [
                    {
                        "kind": "final",
                        "amount": pln("1"),
                        "due_date": "2027-01-01",
                        "days_before_wedding": 3,
                    }
                ],
            }
        ],
    ]
    for terms in bad_terms:
        r = client.post(
            url, headers=alice, json={"vendor_id": v["id"], "title": "T", "terms": terms}
        )
        assert r.status_code == 422, terms
    r = client.post(
        url,
        headers=alice,
        json={
            "vendor_id": v["id"],
            "title": "T",
            "components": [{"label": "Serwis", "kind": "percent", "amount": "150"}],
        },
    )
    assert r.status_code == 422


def test_delete_full_wedding_with_budget_offers_documents(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    a = offer(
        client,
        alice,
        wedding,
        vendor(client, alice, wedding, "Sala")["id"],
        components=SALA_A,
        terms=TERMS_A,
    )
    client.post(f"{url}/offers/{a['id']}/select", headers=alice, json={})
    upload(client, alice, wedding, pdf_sample())
    assert client.delete(url, headers=alice).status_code == 204
    assert client.get(url, headers=alice).status_code == 404
