from app.modules.vendors.models import CATEGORIES
from app.modules.vendors.schemas import VendorCategory

API = "/api/v1"


def test_vendor_categories_in_sync(client):
    assert set(VendorCategory.__args__) == set(CATEGORIES)
    cats = client.get(f"{API}/vendor-categories").json()
    venue = next(c for c in cats if c["slug"] == "venue")
    assert venue["budget_category"] == "Sala i catering"


def test_vendor_crud_normalization_and_duplicates(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}/vendors"
    a = client.post(
        url,
        headers=alice,
        json={
            "name": "  Dworek   Pod Lipami ",
            "category": "venue",
            "website_url": "https://www.dworek-lipy.example.pl/oferta",
            "phone": "+48 600-100-200",
            "nip": "5260250995",
        },
    )
    assert a.status_code == 201, a.text
    assert a.json()["name"] == "Dworek Pod Lipami"
    assert a.json()["possible_duplicates"] == []

    b = client.post(
        url,
        headers=alice,
        json={"name": "Dworek pod Lipami Sp. z o.o.", "category": "venue", "phone": "600100200"},
    ).json()
    reasons = b["possible_duplicates"][0]["reasons"]
    assert "ten sam telefon" in reasons

    c = client.post(
        url,
        headers=alice,
        json={
            "name": "Zupełnie Inna Firma",
            "category": "dj",
            "website_url": "http://dworek-lipy.example.pl",
        },
    ).json()
    assert c["possible_duplicates"][0]["reasons"] == ["ta sama strona www"]

    assert len(client.get(url, headers=alice, params={"category": "venue"}).json()) == 2
    found = client.get(url, headers=alice, params={"q": "lipami"}).json()
    assert {v["id"] for v in found} == {a.json()["id"], b["id"]}

    r = client.patch(
        f"{url}/{c['id']}",
        headers={**alice, "If-Match": '"1"'},
        json={"status": "rejected", "website_url": None},
    )
    assert r.status_code == 200
    assert r.json()["possible_duplicates"] == []
    assert client.delete(f"{url}/{c['id']}", headers=alice).status_code == 204


def test_vendor_validation(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}/vendors"
    assert (
        client.post(url, headers=alice, json={"name": "X", "nip": "1234567890"}).json()["code"]
        == "vendor.invalid_nip"
    )
    for body in (
        {"name": ""},
        {"name": "X", "category": "magik"},
        {"name": "X", "website_url": "javascript:alert(1)"},
        {"name": "X", "email": "nie-email"},
    ):
        assert client.post(url, headers=alice, json=body).status_code == 422, body
