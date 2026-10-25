from datetime import date, datetime, timedelta

from app.core import clock
from tests.api.test_offers import vendor

API = "/api/v1"


def url(wedding):
    return f"{API}/weddings/{wedding['id']}/schedule"


def at(hhmm: str) -> str:
    return f"2027-08-21T{hhmm}:00+02:00"


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def add(client, headers, wedding, **body):
    r = client.post(url(wedding), headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_items_conflicts_and_vendor_plan(client, alice, wedding):
    band = vendor(client, alice, wedding, "Zespół Weselny", "band")
    a = add(
        client,
        alice,
        wedding,
        title="Oprawa mszy",
        starts_at=at("15:00"),
        duration_minutes=60,
        vendor_id=band["id"],
        buffer_after_minutes=30,
        location="Kościół",
    )
    b = add(
        client,
        alice,
        wedding,
        title="Powitanie na sali",
        starts_at=at("16:15"),
        duration_minutes=30,
        vendor_id=band["id"],
        location="Dworek",
    )
    assert dt(a["ends_at"]) == dt(at("16:00"))

    conflicts = client.get(f"{url(wedding)}/conflicts", headers=alice).json()
    found = {c["code"] for c in conflicts}
    assert found == {"vendor_double_booked", "vendor_not_booked"}
    listed = client.get(url(wedding), headers=alice).json()
    assert "vendor_double_booked" in listed[1]["conflicts"]
    assert listed[1]["vendor_name"] == "Zespół Weselny"

    plan = client.get(url(wedding), headers=alice, params={"vendor_id": band["id"]}).json()
    assert [i["title"] for i in plan] == ["Oprawa mszy", "Powitanie na sali"]

    r = client.patch(
        f"{url(wedding)}/{b['id']}",
        headers={**alice, "If-Match": '"1"'},
        json={"starts_at": at("16:30")},
    )
    assert r.status_code == 200
    assert "vendor_double_booked" not in r.json()["conflicts"]


def test_dependencies_cycle_and_order(client, alice, wedding):
    c = add(client, alice, wedding, title="Ceremonia", starts_at=at("15:00"), duration_minutes=60)
    w = add(client, alice, wedding, title="Życzenia", starts_at=at("15:50"), duration_minutes=30)
    r = client.put(f"{url(wedding)}/{w['id']}/dependencies/{c['id']}", headers=alice)
    assert r.json()["conflicts"] == ["dependency_order"]
    r = client.put(f"{url(wedding)}/{c['id']}/dependencies/{w['id']}", headers=alice)
    assert r.status_code == 422
    assert r.json()["code"] == "schedule.dependency_cycle"
    assert (
        client.delete(f"{url(wedding)}/{w['id']}/dependencies/{c['id']}", headers=alice).status_code
        == 204
    )


def test_shift_after_delay(client, alice, wedding):
    a = add(
        client, alice, wedding, title="Przygotowania", starts_at=at("10:00"), duration_minutes=120
    )
    b = add(client, alice, wedding, title="Ceremonia", starts_at=at("15:00"), duration_minutes=60)
    c = add(client, alice, wedding, title="Obiad", starts_at=at("17:00"), duration_minutes=60)
    body = {"from_item_id": b["id"], "minutes": 20}
    preview = client.post(f"{url(wedding)}/shift", headers=alice, json=body).json()
    assert preview["dry_run"] is True
    assert {ch["item_id"] for ch in preview["changes"]} == {b["id"], c["id"]}
    assert (
        client.get(f"{url(wedding)}/{b['id']}", headers=alice).json()["starts_at"] == b["starts_at"]
    )
    client.post(f"{url(wedding)}/shift", headers=alice, json={**body, "dry_run": False})
    moved = client.get(f"{url(wedding)}/{c['id']}", headers=alice).json()
    assert dt(moved["starts_at"]) == dt(at("17:20"))
    untouched = client.get(f"{url(wedding)}/{a['id']}", headers=alice).json()
    assert untouched["starts_at"] == a["starts_at"]
    bad = client.post(
        f"{url(wedding)}/shift", headers=alice, json={"from_item_id": b["id"], "minutes": 0}
    )
    assert bad.status_code == 422


def test_template_preview_apply_and_guards(client, alice, wedding):
    client.post(
        f"{API}/weddings/{wedding['id']}/events",
        headers=alice,
        json={"kind": "reception", "name": "Przyjęcie"},
    )
    r = client.post(f"{url(wedding)}/from-template", headers=alice, json={"ceremony_time": "15:00"})
    assert r.status_code == 422  # wesele ma tylko planowany miesiąc
    assert r.json()["code"] == "schedule.date_required"

    body = {"day": "2027-08-21", "ceremony_time": "15:00"}
    preview = client.post(f"{url(wedding)}/from-template", headers=alice, json=body).json()
    titles = [i["title"] for i in preview["items"]]
    assert "Błogosławieństwo rodziców" in titles
    assert "Oczepiny" in titles
    assert client.get(url(wedding), headers=alice).json() == []

    applied = client.post(
        f"{url(wedding)}/from-template", headers=alice, json={**body, "dry_run": False}
    )
    assert applied.status_code == 200
    items = client.get(url(wedding), headers=alice).json()
    assert len(items) == len(titles)
    assert client.get(f"{url(wedding)}/conflicts", headers=alice).json() == []
    welcome = next(i for i in items if i["title"] == "Powitanie chlebem i solą")
    assert welcome["event_id"] is not None
    assert welcome["depends_on"]

    again = client.post(f"{url(wedding)}/from-template", headers=alice, json=body)
    assert again.status_code == 409
    assert again.json()["code"] == "schedule.not_empty"


def test_civil_template_shorter_ceremony(client, alice):
    day = (clock.today() + timedelta(days=200)).isoformat()
    w = client.post(
        f"{API}/weddings",
        headers=alice,
        json={"name": "Cywilny", "wedding_date": day, "ceremony_type": "civil"},
    ).json()
    preview = client.post(
        f"{API}/weddings/{w['id']}/schedule/from-template",
        headers=alice,
        json={"ceremony_time": "13:00"},
    ).json()
    ceremony = next(i for i in preview["items"] if i["title"] == "Ceremonia ślubna")
    assert ceremony["duration_minutes"] == 30
    assert any("urzędu" in i["title"] for i in preview["items"])
    assert date.fromisoformat(ceremony["starts_at"][:10]) == date.fromisoformat(day)


def test_shift_with_stale_preview_is_rejected(client, alice, wedding):
    b = add(client, alice, wedding, title="Ceremonia", starts_at=at("15:00"), duration_minutes=60)
    c = add(client, alice, wedding, title="Obiad", starts_at=at("17:00"), duration_minutes=60)
    body = {"from_item_id": b["id"], "minutes": 20}
    preview = client.post(f"{url(wedding)}/shift", headers=alice, json=body).json()
    # Ktoś w międzyczasie zmienia program (inny telefon).
    r = client.patch(
        f"{url(wedding)}/{c['id']}",
        headers={**alice, "If-Match": '"1"'},
        json={"starts_at": at("17:30")},
    )
    assert r.status_code == 200
    stale = client.post(
        f"{url(wedding)}/shift",
        headers=alice,
        json={**body, "dry_run": False, "revision": preview["revision"]},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "conflict.version_mismatch"
    assert dt(client.get(f"{url(wedding)}/{b['id']}", headers=alice).json()["starts_at"]) == dt(
        at("15:00")
    )
    # Nowy podgląd ma nową rewizję i zapis przechodzi; rewizja po zapisie znów jest inna.
    fresh = client.post(f"{url(wedding)}/shift", headers=alice, json=body).json()
    assert fresh["revision"] != preview["revision"]
    done = client.post(
        f"{url(wedding)}/shift",
        headers=alice,
        json={**body, "dry_run": False, "revision": fresh["revision"]},
    )
    assert done.status_code == 200
    assert done.json()["revision"] != fresh["revision"]


def test_times_in_warsaw_and_export(client, alice, wedding):
    a = add(
        client,
        alice,
        wedding,
        title="Ceremonia",
        starts_at="2027-08-21T13:00:00Z",
        duration_minutes=60,
    )
    assert a["starts_at"] == "2027-08-21T15:00:00+02:00"  # zawsze czas polski
    b = add(client, alice, wedding, title="Życzenia", starts_at=at("16:10"))
    client.put(f"{url(wedding)}/{b['id']}/dependencies/{a['id']}", headers=alice)
    shift = client.post(
        f"{url(wedding)}/shift", headers=alice, json={"from_item_id": a["id"], "minutes": 15}
    ).json()
    assert shift["changes"][0]["new_starts_at"] == "2027-08-21T15:15:00+02:00"
    exported = client.get(f"{API}/weddings/{wedding['id']}/export", headers=alice).json()
    rows = {r["title"]: r for r in exported["schedule"]}
    assert rows["Życzenia"]["depends_on"] == [a["id"]]


def test_validation(client, alice, bob, wedding):
    bob_id = client.get(f"{API}/me", headers=bob).json()["id"]
    bad = [
        {"title": "", "starts_at": at("12:00")},
        {"title": "X", "starts_at": "2027-08-21T12:00:00"},
        {"title": "X", "starts_at": at("12:00"), "duration_minutes": 2000},
        {"title": "X", "starts_at": at("12:00"), "buffer_after_minutes": -1},
    ]
    for body in bad:
        assert client.post(url(wedding), headers=alice, json=body).status_code == 422, body
    r = client.post(
        url(wedding),
        headers=alice,
        json={"title": "X", "starts_at": at("12:00"), "responsible_user_id": bob_id},
    )
    assert r.json()["code"] == "schedule.invalid_responsible"
