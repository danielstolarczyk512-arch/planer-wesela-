"""Zadania dla bliskich bez konta (propozycja 10 z analizy 07)."""

from sqlalchemy import select

from app.modules.planner.models import Helper
from tests.api.test_workspace import invite_and_accept

API = "/api/v1"


def _task(client, headers, w, title, **kw):
    r = client.post(f"{w}/tasks", headers=headers, json={"title": title, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_helper_link_shows_only_own_tasks_and_marks_done(client, alice, wedding, db):
    w = f"{API}/weddings/{wedding['id']}"
    created = client.post(f"{w}/helpers", headers=alice, json={"name": "Tata — kierowcy"})
    assert created.status_code == 201, created.text
    link = created.json()
    assert link["url"].endswith(f"/pomocnik/{link['token']}")
    # W bazie tylko hash tokenu.
    stored = db.scalars(select(Helper)).one()
    assert stored.token_hash != link["token"]

    drivers = _task(client, alice, w, "Ustal kierowców", description="3 auta z Tarnowa")
    flowers = _task(client, alice, w, "Kwiaty dla mam")
    _task(client, alice, w, "Zadanie pary")
    for t in (drivers, flowers):
        r = client.put(
            f"{w}/tasks/{t['id']}/helper", headers=alice, json={"helper_id": link["helper_id"]}
        )
        assert r.status_code == 200, r.text
        assert r.json()["helper_id"] == link["helper_id"]

    view = client.get(f"{API}/helper/{link['token']}").json()
    assert view["helper_name"] == "Tata — kierowcy"
    assert [t["title"] for t in view["tasks"]] == ["Kwiaty dla mam", "Ustal kierowców"]
    assert view["tasks"][1]["description"] == "3 auta z Tarnowa"

    r = client.put(f"{API}/helper/{link['token']}/tasks/{drivers['id']}/done", json={"done": True})
    assert r.status_code == 200, r.text
    assert [t["done"] for t in r.json()["tasks"]] == [False, True]  # zrobione na końcu
    task = client.get(f"{w}/tasks/{drivers['id']}", headers=alice).json()
    assert task["status"] == "done"

    # Cudzego zadania nie odhaczy.
    other = _task(client, alice, w, "Inne")
    r = client.put(f"{API}/helper/{link['token']}/tasks/{other['id']}/done", json={"done": True})
    assert r.status_code == 404

    helpers = client.get(f"{w}/helpers", headers=alice).json()
    assert (helpers[0]["open_tasks"], helpers[0]["done_tasks"]) == (1, 1)
    assert helpers[0]["last_used_at"] is not None

    # Nowy link unieważnia stary.
    fresh = client.post(f"{w}/helpers/{link['helper_id']}/link", headers=alice).json()
    assert client.get(f"{API}/helper/{link['token']}").status_code == 404
    assert client.get(f"{API}/helper/{fresh['token']}").status_code == 200
    assert "token_hash" not in client.get(f"{w}/export", headers=alice).json()["helpers"][0]

    # Usunięcie pomocnika zostawia zadania (bez przypisania).
    assert client.delete(f"{w}/helpers/{link['helper_id']}", headers=alice).status_code == 204
    assert client.get(f"{w}/tasks/{flowers['id']}", headers=alice).json()["helper_id"] is None
    assert client.get(f"{API}/helper/{fresh['token']}").status_code == 404


def test_helper_from_other_wedding_and_viewer(client, alice, user_factory, wedding):
    w = f"{API}/weddings/{wedding['id']}"
    other = client.post(
        f"{API}/weddings", headers=alice, json={"name": "Inne", "ceremony_type": "civil"}
    ).json()
    foreign = client.post(
        f"{API}/weddings/{other['id']}/helpers", headers=alice, json={"name": "Obcy"}
    ).json()
    t = _task(client, alice, w, "Zadanie")
    r = client.put(
        f"{w}/tasks/{t['id']}/helper", headers=alice, json={"helper_id": foreign["helper_id"]}
    )
    assert (r.status_code, r.json()["code"]) == (422, "helper.unknown")

    viewer = user_factory("ogladam@example.com")
    invite_and_accept(client, alice, viewer, wedding, "ogladam@example.com", role="viewer")
    assert client.get(f"{w}/helpers", headers=viewer).status_code == 200
    assert client.post(f"{w}/helpers", headers=viewer, json={"name": "X"}).status_code == 403


def test_links_without_login_expire_after_wedding(client, alice, wedding, db, monkeypatch):
    """Audyt 2026-10-23 S5: link pomocnika (30 dni) i usługodawcy (7 dni) wygasają po weselu."""
    from datetime import date, datetime

    from sqlalchemy import update

    from app.core import clock
    from app.modules.workspace import service as workspace
    from app.modules.workspace.models import Wedding
    from tests.api.test_offers import vendor

    w = f"{API}/weddings/{wedding['id']}"
    db.execute(
        update(Wedding).where(Wedding.id == wedding["id"]).values(wedding_date=date(2027, 8, 14))
    )
    db.commit()
    helper = client.post(f"{w}/helpers", headers=alice, json={"name": "Ciocia"}).json()["token"]
    band = vendor(client, alice, wedding, "Zespół", category="band")
    day = client.post(f"{w}/vendors/{band['id']}/day-link", headers=alice).json()["token"]

    def status_at(moment: datetime) -> tuple[int, int]:
        monkeypatch.setattr(workspace, "utcnow", lambda: moment)
        return (
            client.get(f"{API}/helper/{helper}").status_code,
            client.get(f"{API}/day/{day}").status_code,
        )

    assert status_at(datetime(2027, 8, 21, 12, tzinfo=clock.WARSAW)) == (200, 200)
    assert status_at(datetime(2027, 8, 22, 12, tzinfo=clock.WARSAW)) == (200, 404)
    assert status_at(datetime(2027, 9, 14, 12, tzinfo=clock.WARSAW)) == (404, 404)
