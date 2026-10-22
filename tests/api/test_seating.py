from tests.api.test_workspace import invite_and_accept

API = "/api/v1"


def base(wedding):
    return f"{API}/weddings/{wedding['id']}"


def url(wedding):
    return f"{base(wedding)}/seating"


def household(client, headers, wedding, name, people, group=None, side="both"):
    h = client.post(
        f"{base(wedding)}/households",
        headers=headers,
        json={"name": name, "group_label": group, "side": side},
    ).json()
    return [
        client.post(
            f"{base(wedding)}/households/{h['id']}/guests",
            headers=headers,
            json={"first_name": first, "age_group": age},
        ).json()
        for first, age in people
    ]


def table(client, headers, wedding, name, capacity, kind="regular"):
    r = client.post(
        f"{url(wedding)}/tables",
        headers=headers,
        json={"name": name, "capacity": capacity, "kind": kind},
    )
    assert r.status_code == 201, r.text
    return r.json()


def seats(plan):
    return {g["guest_id"]: t["id"] for t in plan["tables"] for g in t["guests"]}


def test_auto_preview_apply_and_plan(client, alice, wedding):
    kowalscy = household(
        client, alice, wedding, "Kowalscy", [("Jan", "adult"), ("Ewa", "adult"), ("Ola", "child")]
    )
    nowakowie = household(
        client, alice, wedding, "Nowakowie", [("Adam", "adult"), ("Iza", "adult")]
    )
    solo = household(client, alice, wedding, "Piotr", [("Piotr", "adult")], group="praca")
    baby = household(client, alice, wedding, "Maluch", [("Staś", "infant")])
    t1 = table(client, alice, wedding, "Stół 1", 4)
    t2 = table(client, alice, wedding, "Stół 2", 4)
    kids = table(client, alice, wedding, "Dzieci", 4, kind="kids")
    table(client, alice, wedding, "Para Młoda", 2, kind="head")

    preview = client.post(f"{url(wedding)}/auto", headers=alice, json={})
    assert preview.status_code == 200, preview.text
    p = preview.json()
    assert p["dry_run"] is True
    assert p["status"] in {"optimal", "feasible"}
    placed = {a["guest_id"]: a["table_id"] for a in p["assignments"]}
    assert placed[kowalscy[2]["id"]] == kids["id"]  # dziecko przy stole dziecięcym
    assert placed[kowalscy[0]["id"]] == placed[kowalscy[1]["id"]]
    assert placed[nowakowie[0]["id"]] == placed[nowakowie[1]["id"]]
    assert baby[0]["id"] not in placed  # niemowlę bez osobnego miejsca
    assert p["issues"] == []
    assert (
        seats(client.get(url(wedding), headers=alice).json()) == {}
    )  # podgląd niczego nie zapisał

    r = client.put(
        f"{url(wedding)}/assignments", headers=alice, json={"assignments": p["assignments"]}
    )
    assert r.status_code == 204
    plan = client.get(url(wedding), headers=alice).json()
    assert seats(plan) == placed
    assert plan["stats"] == {"tables": 4, "seats": 14, "seated": 6, "to_seat": 0}
    assert {t["id"] for t in plan["tables"]} >= {t1["id"], t2["id"]}
    assert solo[0]["id"] in placed


def test_locked_guest_rules_and_issues(client, alice, wedding):
    a = household(client, alice, wedding, "Ciocia A", [("Halina", "adult")])
    b = household(client, alice, wedding, "Ciocia B", [("Grażyna", "adult")])
    c = household(client, alice, wedding, "Wujek", [("Zenek", "adult")])
    t1 = table(client, alice, wedding, "Stół 1", 2)
    t2 = table(client, alice, wedding, "Stół 2", 2)
    rule = client.post(
        f"{url(wedding)}/rules",
        headers=alice,
        json={
            "kind": "apart",
            "guest_a_id": a[0]["id"],
            "guest_b_id": b[0]["id"],
            "note": "kłótnia",
        },
    )
    assert rule.status_code == 201
    again = client.post(
        f"{url(wedding)}/rules",
        headers=alice,
        json={"kind": "together", "guest_a_id": b[0]["id"], "guest_b_id": a[0]["id"]},
    )
    assert again.status_code == 409
    assert again.json()["code"] == "seating.rule_exists"

    # Ręcznie: obie ciocie przy jednym stole → plan pokazuje błąd reguły.
    for g in (a[0], b[0]):
        r = client.put(
            f"{url(wedding)}/guests/{g['id']}", headers=alice, json={"table_id": t1["id"]}
        )
        assert r.status_code == 204
    issues = client.get(url(wedding), headers=alice).json()["issues"]
    assert [i["code"] for i in issues] == ["apart_broken"]

    # Automat nie rusza przypiętych: przy sprzeczności zgłasza konflikt z kodem.
    client.delete(f"{url(wedding)}/guests/{b[0]['id']}", headers=alice)
    r = client.post(f"{url(wedding)}/auto", headers=alice, json={"dry_run": False})
    assert r.status_code == 200, r.text
    plan = seats(client.get(url(wedding), headers=alice).json())
    assert plan[a[0]["id"]] == t1["id"]
    assert plan[b[0]["id"]] == t2["id"]
    assert c[0]["id"] in plan

    taken = client.put(
        f"{url(wedding)}/guests/{c[0]['id']}",
        headers=alice,
        json={"table_id": t1["id"], "seat_number": 3},
    )
    assert taken.json()["code"] == "seating.invalid_seat"
    client.put(
        f"{url(wedding)}/guests/{a[0]['id']}",
        headers=alice,
        json={"table_id": t1["id"], "seat_number": 1},
    )
    clash = client.put(
        f"{url(wedding)}/guests/{c[0]['id']}",
        headers=alice,
        json={"table_id": t1["id"], "seat_number": 1},
    )
    assert clash.status_code == 409
    assert clash.json()["code"] == "seating.seat_taken"

    cleared = client.post(f"{url(wedding)}/clear", headers=alice, json={}).json()
    assert cleared["removed"] >= 1
    left = seats(client.get(url(wedding), headers=alice).json())
    assert left == {a[0]["id"]: t1["id"]}  # przypięta zostaje


def test_auto_errors_and_declined_guests(client, alice, wedding):
    r = client.post(f"{url(wedding)}/auto", headers=alice, json={})
    assert r.json()["code"] == "seating.no_tables"
    reception = client.post(
        f"{base(wedding)}/events", headers=alice, json={"kind": "reception", "name": "Przyjęcie"}
    ).json()
    people = household(client, alice, wedding, "Duża rodzina", [("A", "adult"), ("B", "adult")])
    no = household(client, alice, wedding, "Odmowa", [("Nie", "adult")])
    client.put(
        f"{base(wedding)}/guests/{no[0]['id']}/attendance/{reception['id']}",
        headers=alice,
        json={"status": "declined"},
    )
    table(client, alice, wedding, "Mały", 1)
    r = client.post(f"{url(wedding)}/auto", headers=alice, json={})
    assert r.status_code == 422
    assert r.json()["code"] == "seating.capacity_insufficient"
    r = client.post(f"{url(wedding)}/auto", headers=alice, json={"basis": "attending"})
    assert r.status_code == 200  # nikt jeszcze nie potwierdził: nic do usadzenia
    assert r.json()["assignments"] == []
    plan = client.get(url(wedding), headers=alice).json()
    assert {g["guest_id"] for g in plan["unassigned"]} == {p["id"] for p in people}


def test_tables_crud_and_version(client, alice, wedding):
    t = table(client, alice, wedding, "Stół 1", 8)
    r = client.patch(
        f"{url(wedding)}/tables/{t['id']}",
        headers={**alice, "If-Match": '"1"'},
        json={"capacity": 10, "shape": "rectangular"},
    )
    assert r.status_code == 200
    assert r.json()["capacity"] == 10
    assert r.headers["ETag"] == '"2"'
    stale = client.patch(
        f"{url(wedding)}/tables/{t['id']}", headers={**alice, "If-Match": '"1"'}, json={"name": "X"}
    )
    assert stale.status_code == 409
    bad = client.post(f"{url(wedding)}/tables", headers=alice, json={"name": "X", "capacity": 0})
    assert bad.status_code == 422
    nulls = client.patch(
        f"{url(wedding)}/tables/{t['id']}",
        headers={**alice, "If-Match": '"2"'},
        json={"name": None},
    )
    assert nulls.status_code == 422
    assert client.delete(f"{url(wedding)}/tables/{t['id']}", headers=alice).status_code == 204
    assert client.get(f"{url(wedding)}/tables", headers=alice).json() == []


def test_viewer_reads_only_and_foreign_ids(client, alice, bob, user_factory, wedding):
    viewer = user_factory("babcia@example.com")
    invite_and_accept(client, alice, viewer, wedding, "babcia@example.com", role="viewer")
    t = table(client, alice, wedding, "Stół 1", 8)
    g = household(client, alice, wedding, "Kowalscy", [("Jan", "adult")])
    assert client.get(url(wedding), headers=viewer).status_code == 200
    r = client.put(
        f"{url(wedding)}/guests/{g[0]['id']}", headers=viewer, json={"table_id": t["id"]}
    )
    assert r.status_code == 403
    assert client.post(f"{url(wedding)}/auto", headers=viewer, json={}).status_code == 403

    # Stół z innego wesela nie istnieje dla tego wesela.
    other = client.post(f"{API}/weddings", headers=bob, json={"name": "Inne"}).json()
    foreign = table(client, bob, other, "Obcy", 8)
    r = client.put(
        f"{url(wedding)}/guests/{g[0]['id']}", headers=alice, json={"table_id": foreign["id"]}
    )
    assert r.status_code == 404
    r = client.put(
        f"{url(wedding)}/assignments",
        headers=alice,
        json={"assignments": [{"guest_id": g[0]["id"], "table_id": foreign["id"]}]},
    )
    assert r.status_code == 404


def test_seating_in_export(client, alice, wedding):
    t = table(client, alice, wedding, "Stół 1", 8)
    g = household(client, alice, wedding, "Kowalscy", [("Jan", "adult")])
    client.put(f"{url(wedding)}/guests/{g[0]['id']}", headers=alice, json={"table_id": t["id"]})
    data = client.get(f"{base(wedding)}/export", headers=alice).json()
    assert data["seating"]["tables"][0]["name"] == "Stół 1"
    assert data["seating"]["assignments"][0]["guest_id"] == g[0]["id"]


def test_room_layout_and_table_positions(client, alice, wedding):
    room = client.get(f"{url(wedding)}/room", headers=alice).json()
    assert room == {"width_m": 20.0, "length_m": 12.0, "items": [], "version": 0}
    body = {
        "width_m": 24,
        "length_m": 14,
        "items": [{"kind": "dance_floor", "label": "Parkiet", "x": 12, "y": 7, "w": 6, "h": 5}],
    }
    r = client.put(f"{url(wedding)}/room", headers={**alice, "If-Match": '"0"'}, json=body)
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 1
    stale = client.put(f"{url(wedding)}/room", headers={**alice, "If-Match": '"0"'}, json=body)
    assert stale.status_code == 409
    bad = client.put(
        f"{url(wedding)}/room",
        headers={**alice, "If-Match": '"1"'},
        json={**body, "items": [{"kind": "pool", "x": 1, "y": 1, "w": 1, "h": 1}]},
    )
    assert bad.status_code == 422

    t = table(client, alice, wedding, "Stół 1", 8)
    assert (t["pos_x"], t["pos_y"], t["rotation"]) == (None, None, 0)
    r = client.patch(
        f"{url(wedding)}/tables/{t['id']}",
        headers={**alice, "If-Match": '"1"'},
        json={"pos_x": 3.5, "pos_y": 4, "rotation": 90},
    )
    assert r.status_code == 200, r.text
    plan = client.get(url(wedding), headers=alice).json()
    assert plan["room"]["items"][0]["kind"] == "dance_floor"
    assert (plan["tables"][0]["pos_x"], plan["tables"][0]["rotation"]) == (3.5, 90)


def test_seat_numbers_family_together(client, alice, wedding):
    t = table(client, alice, wedding, "Stół 1", 8)
    family = household(
        client,
        alice,
        wedding,
        "Kowalscy",
        [("Zosia", "child"), ("Anna", "adult"), ("Jan", "adult")],
    )
    single = household(client, alice, wedding, "Nowak", [("Ewa", "adult")])
    for g in family + single:
        client.put(f"{url(wedding)}/guests/{g['id']}", headers=alice, json={"table_id": t["id"]})
    # Ewa ma już wpisane miejsce 1 — zostaje.
    client.put(
        f"{url(wedding)}/guests/{single[0]['id']}",
        headers=alice,
        json={"table_id": t["id"], "seat_number": 1},
    )
    preview = client.post(f"{url(wedding)}/seat-numbers", headers=alice, json={"dry_run": True})
    assert preview.status_code == 200, preview.text
    seats = {s["guest_id"]: s["seat_number"] for s in preview.json()["seats"]}
    assert seats[single[0]["id"]] == 1
    family_seats = sorted(seats[g["id"]] for g in family)
    assert family_seats == list(range(family_seats[0], family_seats[0] + 3))  # obok siebie
    # Podgląd nie zapisuje.
    plan = client.get(url(wedding), headers=alice).json()
    assert {g["seat_number"] for g in plan["tables"][0]["guests"]} == {1, None}

    r = client.post(f"{url(wedding)}/seat-numbers", headers=alice, json={})
    assert r.status_code == 200
    plan = client.get(url(wedding), headers=alice).json()
    by_name = {g["name"]: g["seat_number"] for g in plan["tables"][0]["guests"]}
    assert by_name["Ewa"] == 1
    assert abs(by_name["Anna"] - by_name["Jan"]) == 1  # para obok siebie
    # Ponowne numerowanie od zera (keep_existing=false) też daje komplet bez dziur.
    r = client.post(f"{url(wedding)}/seat-numbers", headers=alice, json={"keep_existing": False})
    assert sorted(s["seat_number"] for s in r.json()["seats"]) == [1, 2, 3, 4]


def test_auto_places_near_group_closest_to_head_table(client, alice, wedding):
    head = table(client, alice, wedding, "Para Młoda", 2, kind="head")
    far = table(client, alice, wedding, "Stół daleko", 2)
    near = table(client, alice, wedding, "Stół blisko", 2)
    for t, (x, y) in ((head, (2, 2)), (near, (4, 3)), (far, (18, 10))):
        r = client.patch(
            f"{url(wedding)}/tables/{t['id']}",
            headers={**alice, "If-Match": '"1"'},
            json={"pos_x": x, "pos_y": y},
        )
        assert r.status_code == 200, r.text
    family = household(
        client,
        alice,
        wedding,
        "Rodzice",
        [("Mama", "adult"), ("Tata", "adult")],
        group="Rodzina Ani",
    )
    household(
        client, alice, wedding, "Koledzy", [("Kuba", "adult"), ("Olek", "adult")], group="Praca"
    )
    r = client.post(
        f"{url(wedding)}/auto",
        headers=alice,
        json={"near_groups": ["rodzina  ani"], "near_target": "head"},
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["near_applied"] is True
    where = {a["guest_id"]: a["table_id"] for a in out["assignments"]}
    assert {where[g["id"]] for g in family} == {near["id"]}

    # Cel bez pozycji (parkiet nie narysowany): reguła pominięta, z informacją.
    r = client.post(
        f"{url(wedding)}/auto",
        headers=alice,
        json={"near_groups": ["Rodzina Ani"], "near_target": "dance_floor"},
    )
    assert r.json()["near_applied"] is False


def test_auto_run_in_worker_preview_then_save(client, alice, bob, wedding, db):
    from sqlalchemy import select

    from app.jobs.queue import Job
    from tests.api.test_documents import drain_jobs

    r = client.post(f"{url(wedding)}/auto-runs", headers=alice, json={})
    assert r.status_code == 202, r.text
    drain_jobs()
    failed = client.get(f"{url(wedding)}/auto-runs/{r.json()['id']}", headers=alice).json()
    assert (failed["status"], failed["error_code"]) == ("failed", "seating.no_tables")

    t = table(client, alice, wedding, "Stół 1", 6)
    family = household(client, alice, wedding, "Kowalscy", [("Anna", "adult"), ("Jan", "adult")])
    r = client.post(f"{url(wedding)}/auto-runs", headers=alice, json={})
    run = r.json()
    assert run["status"] == "queued"
    assert run["result"] is None
    job = db.scalars(select(Job).where(Job.type == "seating_auto")).all()[-1]
    assert job.max_attempts == 1  # bez ponawiania (CPU)
    drain_jobs()
    done = client.get(f"{url(wedding)}/auto-runs/{run['id']}", headers=alice).json()
    assert done["status"] == "done", done
    assert {a["guest_id"]: a["table_id"] for a in done["result"]["assignments"]} == {
        g["id"]: t["id"] for g in family
    }
    # Podgląd niczego nie zapisał; zapis — tak jak dotąd, przez PUT assignments.
    assert client.get(url(wedding), headers=alice).json()["stats"]["seated"] == 0
    r = client.put(
        f"{url(wedding)}/assignments",
        headers=alice,
        json={"assignments": done["result"]["assignments"], "replace_unlocked": True},
    )
    assert r.status_code == 204, r.text
    assert client.get(url(wedding), headers=alice).json()["stats"]["seated"] == 2
    assert client.get(f"{url(wedding)}/auto-runs/{run['id']}", headers=bob).status_code == 404


def test_old_auto_runs_purged(client, alice, wedding, db):
    from datetime import timedelta

    from app.core.db import utcnow
    from app.modules.seating import service
    from app.modules.seating.models import SeatingAutoRun

    table(client, alice, wedding, "Stół 1", 6)
    run_id = client.post(f"{url(wedding)}/auto-runs", headers=alice, json={}).json()["id"]
    assert service.purge_auto_runs(db) == 0
    run = db.get(SeatingAutoRun, run_id)
    run.created_at = utcnow() - timedelta(days=8)
    db.commit()
    assert service.purge_auto_runs(db) == 1


def test_auto_run_unexpected_error_marks_failed(client, alice, wedding, monkeypatch):
    from app.modules.seating import service
    from tests.api.test_documents import drain_jobs

    def boom(*_args, **_kwargs):
        raise RuntimeError("awaria solvera")

    monkeypatch.setattr(service, "_compute_auto", boom)
    table(client, alice, wedding, "Stół 1", 6)
    run_id = client.post(f"{url(wedding)}/auto-runs", headers=alice, json={}).json()["id"]
    drain_jobs()
    out = client.get(f"{url(wedding)}/auto-runs/{run_id}", headers=alice).json()
    assert (out["status"], out["error_code"]) == ("failed", "seating.auto_error")
