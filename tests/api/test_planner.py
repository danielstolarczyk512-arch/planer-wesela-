from datetime import date, timedelta

import pytest

from app.core import clock
from app.modules.planner.service import catch_up_dates
from app.modules.planner.templates import BY_CODE, TEMPLATES, templates_for

API = "/api/v1"


def tasks_of(client, headers, wedding, **params):
    r = client.get(
        f"{API}/weddings/{wedding['id']}/tasks", headers=headers, params={"limit": 200, **params}
    )
    assert r.status_code == 200, r.text
    return r.json()["items"]


def test_templates_are_consistent():
    codes = {t.code for t in TEMPLATES}
    assert len(codes) == len(TEMPLATES)
    seen: set[str] = set()
    for t in TEMPLATES:
        assert set(t.depends_on) <= codes, t.code
        assert 1 <= t.priority <= 4
        if t.parent:
            # Rodzic przed dzieckiem, dziecko tylko dla ceremonii rodzica, bez zagnieżdżeń.
            assert t.parent in seen, t.code
            parent = BY_CODE[t.parent]
            assert parent.parent is None
            assert set(t.ceremony_types) <= set(parent.ceremony_types), t.code
        seen.add(t.code)


@pytest.mark.parametrize("ceremony", ["civil", "concordat", "humanist", "undecided"])
def test_template_filter_by_ceremony(ceremony):
    codes = {t.code for t in templates_for(ceremony)}
    assert ("church_book" in codes) == (ceremony == "concordat")
    assert ("usc_book" in codes) == (ceremony == "civil")


def new_wedding(client, headers, **body):
    r = client.post(
        f"{API}/weddings",
        headers=headers,
        json={"name": "Test", "ceremony_type": "concordat", **body},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_wedding_creation_generates_tasks_with_dates(client, alice, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2025, 6, 1))
    w = new_wedding(client, alice, planned_month="2027-08")
    tasks = tasks_of(client, alice, w)
    assert len(tasks) == len(templates_for("concordat"))
    venue = next(t for t in tasks if t["template_code"] == "venue_book")
    # planned_month 2027-08 → kotwica 2027-08-01, offset -480 dni
    assert venue["due_date"] == (date(2027, 8, 1) - timedelta(days=480)).isoformat()
    assert venue["due_mode"] == "relative"
    assert len(venue["depends_on"]) == 2
    assert venue["tip"]
    assert "zadatek" in venue["tip"]
    assert venue["vendor_category"] == "venue"


def test_document_checklist_is_subtasks(client, alice, wedding):
    tasks = tasks_of(client, alice, wedding)
    parent = next(t for t in tasks if t["template_code"] == "docs_concordat")
    children = [t for t in tasks if t["parent_task_id"] == parent["id"]]
    assert {c["template_code"] for c in children} == {
        t.code for t in TEMPLATES if t.parent == "docs_concordat"
    }
    assert all(c["due_date"] == parent["due_date"] for c in children)
    assert not any(t["template_code"] == "docs_civil" for t in tasks)


def test_catch_up_dates_spread_before_wedding():
    today = date(2026, 10, 20)
    dates = catch_up_dates(today + timedelta(days=100), today, 10)
    assert dates == sorted(dates)
    assert dates[0] > today
    assert dates[-1] == today + timedelta(days=25)  # ćwierć ze 100 dni
    assert catch_up_dates(today + timedelta(days=1000), today, 3)[-1] == today + timedelta(days=60)
    assert catch_up_dates(today + timedelta(days=10), today, 2)[-1] == today + timedelta(days=9)
    assert catch_up_dates(today, today, 2) == [today, today]
    assert catch_up_dates(today + timedelta(days=50), today, 0) == []


def test_late_start_has_no_overdue_tasks(client, alice):
    """Wesele założone 4 miesiące przed ślubem: zaległości rozłożone na najbliższe tygodnie."""
    today = clock.today()
    w = new_wedding(client, alice, wedding_date=(today + timedelta(days=120)).isoformat())
    tasks = tasks_of(client, alice, w)
    assert [t["template_code"] for t in tasks if t["is_overdue"]] == []
    venue = next(t for t in tasks if t["template_code"] == "venue_book")
    music = next(t for t in tasks if t["template_code"] == "music_book")
    assert today < date.fromisoformat(venue["due_date"]) <= today + timedelta(days=30)
    assert venue["due_date"] <= music["due_date"]  # kolejność zależności zachowana
    assert venue["due_mode"] == "relative"
    summary = client.get(f"{API}/weddings/{w['id']}/summary", headers=alice).json()
    assert summary["tasks"]["overdue"] == 0


def test_catch_up_endpoint_preview_and_apply(client, alice, wedding, monkeypatch):
    url = f"{API}/weddings/{wedding['id']}/tasks/catch-up"
    monkeypatch.setattr(clock, "today", lambda: date(2027, 3, 1))
    overdue = [t for t in tasks_of(client, alice, wedding, overdue=True) if not t["parent_task_id"]]
    assert overdue
    preview = client.post(url, headers=alice, json={"dry_run": True})
    assert preview.status_code == 200, preview.text
    assert len(preview.json()["changes"]) == len(overdue)
    assert tasks_of(client, alice, wedding, overdue=True)  # podgląd niczego nie zmienił
    r = client.post(url, headers=alice, json={"dry_run": False})
    assert r.status_code == 200
    assert not tasks_of(client, alice, wedding, overdue=True)
    assert client.post(url, headers=alice, json={"dry_run": True}).json()["changes"] == []


def test_sync_template_after_ceremony_change(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    r = client.patch(url, headers={**alice, "If-Match": '"1"'}, json={"ceremony_type": "civil"})
    assert r.status_code == 200, r.text
    preview = client.post(f"{url}/tasks/sync-template", headers=alice, json={"dry_run": True})
    assert preview.status_code == 200, preview.text
    p = preview.json()
    added = {t["code"] for t in p["to_add"]}
    assert {"usc_book", "docs_civil", "docs_civil_ids"} <= added
    skipped = {t["title"] for t in p["to_skip"]}
    assert "Ustalcie termin ślubu w parafii" in skipped

    r = client.post(f"{url}/tasks/sync-template", headers=alice, json={"dry_run": False})
    assert r.status_code == 200
    tasks = tasks_of(client, alice, wedding)
    by_code = {t["template_code"]: t for t in tasks}
    assert by_code["church_book"]["status"] == "skipped"
    assert by_code["docs_civil_ids"]["parent_task_id"] == by_code["docs_civil"]["id"]
    again = client.post(f"{url}/tasks/sync-template", headers=alice, json={"dry_run": True})
    assert again.json()["to_add"] == []
    assert again.json()["to_skip"] == []


def test_sync_template_readds_deleted_task(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}/tasks"
    cake = next(t for t in tasks_of(client, alice, wedding) if t["template_code"] == "cake")
    assert client.delete(f"{url}/{cake['id']}", headers=alice).status_code == 204
    p = client.post(f"{url}/sync-template", headers=alice, json={"dry_run": True}).json()
    assert [t["code"] for t in p["to_add"]] == ["cake"]


def test_task_vendor_link(client, alice, bob, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    vendor = client.post(
        f"{url}/vendors", headers=alice, json={"name": "Foto Kadr", "category": "photographer"}
    ).json()
    task = client.post(
        f"{url}/tasks", headers=alice, json={"title": "Plener", "vendor_id": vendor["id"]}
    ).json()
    assert task["vendor_id"] == vendor["id"]
    r = client.patch(
        f"{url}/tasks/{task['id']}", headers={**alice, "If-Match": '"1"'}, json={"vendor_id": None}
    )
    assert r.json()["vendor_id"] is None

    other = client.post(f"{API}/weddings", headers=bob, json={"name": "Inne"}).json()
    foreign = client.post(
        f"{API}/weddings/{other['id']}/vendors", headers=bob, json={"name": "Obcy"}
    ).json()
    r = client.post(f"{url}/tasks", headers=alice, json={"title": "X", "vendor_id": foreign["id"]})
    assert r.status_code == 422
    assert r.json()["code"] == "task.invalid_vendor"


def test_wedding_without_date_has_undated_tasks_filled_later(client, alice):
    w = client.post(f"{API}/weddings", headers=alice, json={"name": "Bez daty"}).json()
    assert all(t["due_date"] is None for t in tasks_of(client, alice, w))
    future = (clock.today() + timedelta(days=500)).isoformat()
    r = client.patch(
        f"{API}/weddings/{w['id']}",
        headers={**alice, "If-Match": '"1"'},
        json={"wedding_date": future},
    )
    assert r.status_code == 200, r.text
    assert all(t["due_date"] is not None for t in tasks_of(client, alice, w))


def test_patch_date_change_requires_reschedule(client, alice, wedding):
    r = client.patch(
        f"{API}/weddings/{wedding['id']}",
        headers={**alice, "If-Match": '"1"'},
        json={"planned_month": "2027-09"},
    )
    assert r.status_code == 409
    assert r.json()["code"] == "wedding.reschedule_required"
    assert (
        client.get(f"{API}/weddings/{wedding['id']}", headers=alice).json()["planned_month"]
        == "2027-08"
    )


def test_reschedule_dry_run_then_apply_keeps_manual_and_done(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    tasks = tasks_of(client, alice, wedding)
    manual, done = tasks[0], tasks[1]
    r = client.patch(
        f"{url}/tasks/{manual['id']}",
        headers={**alice, "If-Match": '"1"'},
        json={"due_date": "2027-01-15"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["due_manually_set"] is True
    client.post(f"{url}/tasks/{done['id']}/complete", headers=alice)

    body = {"planned_month": "2027-10", "dry_run": True}
    preview = client.post(f"{url}/reschedule", headers={**alice, "If-Match": '"1"'}, json=body)
    assert preview.status_code == 200, preview.text
    p = preview.json()
    assert p["dry_run"] is True
    assert p["kept_manual"] == 1
    assert p["kept_finished"] == 1
    assert len(p["changes"]) == len(tasks) - 2
    # Podgląd niczego nie zmienił.
    assert client.get(url, headers=alice).json()["planned_month"] == "2027-08"

    applied = client.post(
        f"{url}/reschedule", headers={**alice, "If-Match": '"1"'}, json={**body, "dry_run": False}
    )
    assert applied.status_code == 200
    assert client.get(url, headers=alice).json()["planned_month"] == "2027-10"
    after = {t["id"]: t for t in tasks_of(client, alice, wedding)}
    assert after[manual["id"]]["due_date"] == "2027-01-15"
    assert after[done["id"]]["due_date"] == done["due_date"]


def test_reschedule_requires_current_version(client, alice, wedding):
    r = client.post(
        f"{API}/weddings/{wedding['id']}/reschedule",
        headers={**alice, "If-Match": '"7"'},
        json={"planned_month": "2027-10", "dry_run": True},
    )
    assert r.status_code == 409


def test_task_crud_filters_and_overdue(client, alice, wedding, monkeypatch):
    url = f"{API}/weddings/{wedding['id']}/tasks"
    r = client.post(
        url,
        headers=alice,
        json={"title": "Kupić buty", "category": "stroj", "due_date": "2027-05-01", "priority": 3},
    )
    assert r.status_code == 201, r.text
    task = r.json()
    assert task["due_mode"] == "absolute"
    assert task["source"] == "user"
    assert [
        t["id"] for t in tasks_of(client, alice, wedding, category="stroj") if t["source"] == "user"
    ] == [task["id"]]

    monkeypatch.setattr(clock, "today", lambda: date(2027, 5, 2))
    overdue = tasks_of(client, alice, wedding, overdue=True)
    assert task["id"] in {t["id"] for t in overdue}
    assert next(t for t in overdue if t["id"] == task["id"])["is_overdue"] is True

    assert client.post(f"{url}/{task['id']}/complete", headers=alice).json()["status"] == "done"
    assert client.post(f"{url}/{task['id']}/reopen", headers=alice).json()["completed_at"] is None
    assert client.delete(f"{url}/{task['id']}", headers=alice).status_code == 204


def test_relative_task_and_clear_due(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}/tasks"
    t = client.post(
        url, headers=alice, json={"title": "Wieczór panieński", "offset_days": -30}
    ).json()
    assert t["due_date"] == (date(2027, 8, 1) - timedelta(days=30)).isoformat()
    r = client.patch(
        f"{url}/{t['id']}", headers={**alice, "If-Match": '"1"'}, json={"clear_due": True}
    )
    assert r.json()["due_date"] is None
    assert r.json()["due_mode"] == "none"


def test_task_validation(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}/tasks"
    bad = [
        {"title": ""},
        {"title": "X", "priority": 5},
        {"title": "X", "due_date": "2027-01-01", "offset_days": -3},
    ]
    for body in bad:
        assert client.post(url, headers=alice, json=body).status_code == 422


def test_assignee_must_be_member(client, alice, bob, wedding):
    bob_id = client.get(f"{API}/me", headers=bob).json()["id"]
    r = client.post(
        f"{API}/weddings/{wedding['id']}/tasks",
        headers=alice,
        json={"title": "X", "assignee_user_id": bob_id},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "task.invalid_assignee"


def test_dependency_cycle_rejected(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}/tasks"
    a = client.post(url, headers=alice, json={"title": "A"}).json()
    b = client.post(url, headers=alice, json={"title": "B"}).json()
    c = client.post(url, headers=alice, json={"title": "C"}).json()
    assert client.put(f"{url}/{b['id']}/dependencies/{a['id']}", headers=alice).status_code == 200
    assert client.put(f"{url}/{c['id']}/dependencies/{b['id']}", headers=alice).status_code == 200
    r = client.put(f"{url}/{a['id']}/dependencies/{c['id']}", headers=alice)
    assert r.status_code == 422
    assert r.json()["code"] == "task.dependency_cycle"
    assert client.put(f"{url}/{a['id']}/dependencies/{a['id']}", headers=alice).status_code == 422
    assert (
        client.delete(f"{url}/{c['id']}/dependencies/{b['id']}", headers=alice).status_code == 204
    )
    assert (
        client.delete(f"{url}/{c['id']}/dependencies/{b['id']}", headers=alice).status_code == 404
    )
