"""Informacje dla usługodawców i potwierdzanie wersji programu (propozycja 9 z analizy 05)."""

from sqlalchemy import select

from app.modules.audit.models import AuditLog
from tests.api.test_offers import vendor
from tests.api.test_schedule import add, at
from tests.api.test_workspace import invite_and_accept

API = "/api/v1"
BRIEF = {
    "must": ["Pierwszy taniec: „Perfect”", "Zdjęcie z dziadkami"],
    "avoid": ["Disco polo"],
    "people": [{"name": "Babcia Halina", "role": "mama Pana Młodego, na wózku"}],
    "notes": "Proszę o ciche wejście w kościele.",
    "contact": "Świadek Tomek",
}


def test_brief_versions_and_acknowledge(client, alice, wedding, db):
    w = f"{API}/weddings/{wedding['id']}"
    band = vendor(client, alice, wedding, "Zespół", "band")
    item = add(
        client, alice, wedding, title="Oczepiny", starts_at=at("23:00"), vendor_id=band["id"]
    )
    token = client.post(f"{w}/vendors/{band['id']}/day-link", headers=alice).json()["token"]

    day = client.get(f"{API}/day/{token}").json()
    assert (day["version"], day["acknowledged_version"], day["up_to_date"]) == (1, None, False)
    assert day["brief"]["must"] == []
    # Ponowny odczyt bez zmian nie podbija wersji.
    assert client.get(f"{API}/day/{token}").json()["version"] == 1

    ack = client.post(f"{API}/day/{token}/ack", json={"version": 1})
    assert ack.status_code == 200, ack.text
    assert ack.json()["version"] == 1
    statuses = client.get(f"{w}/vendor-briefs", headers=alice).json()
    assert [(s["vendor_name"], s["version"], s["up_to_date"]) for s in statuses] == [
        ("Zespół", 1, True)
    ]

    # Informacje dla usługodawcy: zapis z If-Match zmienia wersję linku.
    brief_url = f"{w}/vendors/{band['id']}/brief"
    b = client.get(brief_url, headers=alice)
    assert b.headers["etag"] == '"1"'
    saved = client.put(brief_url, headers={**alice, "If-Match": '"1"'}, json=BRIEF)
    assert saved.status_code == 200, saved.text
    assert saved.json()["people"][0]["name"] == "Babcia Halina"
    stale = client.put(brief_url, headers={**alice, "If-Match": '"1"'}, json=BRIEF)
    assert stale.status_code == 409
    day = client.get(f"{API}/day/{token}").json()
    assert day["brief"]["avoid"] == ["Disco polo"]
    assert (day["version"], day["acknowledged_version"], day["up_to_date"]) == (2, 1, False)
    assert client.get(f"{w}/vendor-briefs", headers=alice).json()[0]["up_to_date"] is False

    # Przesunięcie programu po otwarciu strony: potwierdzenie starej wersji jest odrzucane.
    moved = client.patch(
        f"{w}/schedule/{item['id']}",
        headers={**alice, "If-Match": f'"{item["version"]}"'},
        json={"starts_at": at("23:30")},
    )
    assert moved.status_code == 200, moved.text
    old = client.post(f"{API}/day/{token}/ack", json={"version": 2})
    assert old.status_code == 409
    assert old.json()["code"] == "day_link.version_changed"
    day = client.get(f"{API}/day/{token}").json()
    assert day["version"] == 3
    assert client.post(f"{API}/day/{token}/ack", json={"version": 3}).status_code == 200
    assert client.get(f"{API}/day/{token}").json()["up_to_date"] is True

    # Audyt: potwierdzenie bez treści, zapis informacji tylko z nazwami pól.
    logs = db.scalars(select(AuditLog).where(AuditLog.entity_type == "vendor_brief")).all()
    assert {a.action for a in logs} == {"update", "acknowledge"}
    assert all("Halina" not in str(a.changes) for a in logs)


def test_other_vendor_brief_not_visible(client, alice, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    band = vendor(client, alice, wedding, "Zespół", "band")
    photo = vendor(client, alice, wedding, "Fotograf", "photographer")
    client.put(f"{w}/vendors/{photo['id']}/brief", headers={**alice, "If-Match": '"1"'}, json=BRIEF)
    client.get(f"{w}/vendors/{photo['id']}/brief", headers=alice)
    token = client.post(f"{w}/vendors/{band['id']}/day-link", headers=alice).json()["token"]
    assert client.get(f"{API}/day/{token}").json()["brief"]["must"] == []


def test_viewer_reads_brief_but_cannot_save(client, alice, user_factory, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    band = vendor(client, alice, wedding, "Zespół", "band")
    viewer = user_factory("babcia@example.com")
    invite_and_accept(client, alice, viewer, wedding, "babcia@example.com", role="viewer")
    assert client.get(f"{w}/vendors/{band['id']}/brief", headers=viewer).status_code == 200
    r = client.put(
        f"{w}/vendors/{band['id']}/brief", headers={**viewer, "If-Match": '"1"'}, json=BRIEF
    )
    assert r.status_code == 403


def test_ack_with_unknown_token(client):
    assert client.post(f"{API}/day/nieznany-token/ack", json={"version": 1}).status_code == 404


def test_brief_in_export_and_cleared_after_wedding(client, alice, wedding, db):
    from datetime import timedelta

    from sqlalchemy import update

    from app.core import clock
    from app.jobs.worker import run_maintenance
    from app.modules.schedule.models import VendorBrief
    from app.modules.workspace.models import Wedding

    w = f"{API}/weddings/{wedding['id']}"
    band = vendor(client, alice, wedding, "Zespół", "band")
    client.get(f"{w}/vendors/{band['id']}/brief", headers=alice)
    client.put(f"{w}/vendors/{band['id']}/brief", headers={**alice, "If-Match": '"1"'}, json=BRIEF)
    export = client.get(f"{w}/export", headers=alice).json()
    assert export["vendor_briefs"][0]["people"][0]["name"] == "Babcia Halina"
    db.execute(update(Wedding).values(wedding_date=clock.today() - timedelta(days=91)))
    db.commit()
    assert run_maintenance()["weddings_guests_anonymized"] == 1
    db.expire_all()
    b = db.scalars(select(VendorBrief)).one()
    assert (b.people, b.contact, b.must) == ([], None, BRIEF["must"])
