"""Etap 3: idempotencja, podsumowanie, eksport wesela, przypomnienia, uprawnienia viewer."""

from datetime import UTC, date, datetime

from sqlalchemy import func, select

from app.core import clock
from app.jobs.queue import Job
from app.modules.notifications import service as notifications
from tests.api.test_workspace import invite_and_accept

API = "/api/v1"


def test_idempotency_key_replays_without_duplicate(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}/tasks"
    headers = {**alice, "Idempotency-Key": "task-create-0001"}
    first = client.post(url, headers=headers, json={"title": "Zamówić tort"})
    second = client.post(url, headers=headers, json={"title": "Zamówić tort"})
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert second.headers.get("idempotency-replayed") == "true"
    titles = [
        t["title"] for t in client.get(url, headers=alice, params={"limit": 200}).json()["items"]
    ]
    assert titles.count("Zamówić tort") == 1

    other_body = client.post(url, headers=headers, json={"title": "Coś innego"})
    assert other_body.status_code == 422
    assert other_body.json()["code"] == "idempotency.key_reused"
    bad_key = client.post(url, headers={**alice, "Idempotency-Key": "x"}, json={"title": "A"})
    assert bad_key.status_code == 422


def test_idempotency_is_per_user(client, alice, bob, wedding):
    invite_and_accept(client, alice, bob, wedding, "bob@example.com")
    url = f"{API}/weddings/{wedding['id']}/tasks"
    a = client.post(url, headers={**alice, "Idempotency-Key": "same-key-123"}, json={"title": "T"})
    b = client.post(url, headers={**bob, "Idempotency-Key": "same-key-123"}, json={"title": "T"})
    assert a.json()["id"] != b.json()["id"]


def test_idempotency_replay_requires_active_session(client, alice, wedding):
    """Audyt 2026-10-23 S1: wylogowana sesja nie odtwarza zapisanej odpowiedzi."""
    url = f"{API}/weddings/{wedding['id']}/tasks"
    headers = {**alice, "Idempotency-Key": "task-logout-0001"}
    assert client.post(url, headers=headers, json={"title": "Tort"}).status_code == 201
    assert client.post(f"{API}/auth/logout", headers=alice).status_code == 204
    replay = client.post(url, headers=headers, json={"title": "Tort"})
    assert replay.status_code == 401
    assert replay.headers.get("idempotency-replayed") is None


def test_idempotency_replay_rechecks_membership_and_role(client, alice, bob, wedding):
    invite_and_accept(client, alice, bob, wedding, "bob@example.com")
    bob_id = client.get(f"{API}/me", headers=bob).json()["id"]
    url = f"{API}/weddings/{wedding['id']}/tasks"
    headers = {**bob, "Idempotency-Key": "task-role-0001"}
    assert client.post(url, headers=headers, json={"title": "Kwiaty"}).status_code == 201

    members = f"{API}/weddings/{wedding['id']}/members/{bob_id}"
    assert client.patch(members, headers=alice, json={"role": "viewer"}).status_code == 200
    changed = client.post(url, headers=headers, json={"title": "Kwiaty"})
    assert changed.status_code == 403
    assert changed.json()["code"] == "idempotency.context_changed"

    assert client.delete(members, headers=alice).status_code == 204
    removed = client.post(url, headers=headers, json={"title": "Kwiaty"})
    assert removed.status_code == 404
    assert removed.headers.get("idempotency-replayed") is None


def test_summary(client, alice, wedding, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2027, 6, 1))
    s = client.get(f"{API}/weddings/{wedding['id']}/summary", headers=alice)
    assert s.status_code == 200, s.text
    body = s.json()
    assert body["wedding"]["days_to_wedding"] == 61
    assert body["tasks"]["overdue"] > 0
    assert body["budget"]["total_budget"] == {"amount": "65000.00", "currency": "PLN"}
    assert body["guests"]["planned"] == 110


def test_export_contains_everything_and_is_audited(client, alice, wedding):
    url = f"{API}/weddings/{wedding['id']}"
    h = client.post(f"{url}/households", headers=alice, json={"name": "Nowakowie"}).json()
    client.post(
        f"{url}/households/{h['id']}/guests",
        headers=alice,
        json={"first_name": "Jan", "dietary_note": "orzechy"},
    )
    data = client.get(f"{url}/export", headers=alice).json()
    assert data["wedding"]["name"] == wedding["name"]
    assert len(data["tasks"]) > 20
    assert len(data["budget"]["categories"]) == 12
    assert data["guests"][0]["dietary_note"] == "orzechy"
    assert "dietary_note_encrypted" not in data["guests"][0]
    history = client.get(f"{url}/budget/history", headers=alice).json()
    assert isinstance(history, list)


def test_viewer_cannot_export_or_write(client, alice, user_factory, wedding):
    viewer = user_factory("babcia@example.com")
    invite_and_accept(client, alice, viewer, wedding, "babcia@example.com", role="viewer")
    url = f"{API}/weddings/{wedding['id']}"
    assert client.get(f"{url}/summary", headers=viewer).status_code == 200
    assert client.get(f"{url}/export", headers=viewer).status_code == 403
    assert client.post(f"{url}/tasks", headers=viewer, json={"title": "X"}).status_code == 403
    assert client.post(f"{url}/households", headers=viewer, json={"name": "X"}).status_code == 403


def test_notification_settings(client, alice):
    assert client.get(f"{API}/me/notifications", headers=alice).json() == {"digest": "daily"}
    r = client.put(f"{API}/me/notifications", headers=alice, json={"digest": "weekly"})
    assert r.json() == {"digest": "weekly"}
    assert (
        client.put(f"{API}/me/notifications", headers=alice, json={"digest": "hourly"}).status_code
        == 422
    )


def _digest_jobs(db):
    return db.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.type == "send_email", Job.payload["subject"].astext.like("Wesele:%"))
    )


def test_daily_digest_once_per_day(client, alice, db, monkeypatch):
    # Wesele założone z wyprzedzeniem (bez nadrabiania zaległości), potem „mija czas”.
    monkeypatch.setattr(clock, "today", lambda: date(2025, 6, 1))
    r = client.post(
        f"{API}/weddings", headers=alice, json={"name": "A", "planned_month": "2027-08"}
    )
    assert r.status_code == 201
    monkeypatch.setattr(clock, "today", lambda: date(2026, 3, 20))
    morning = datetime(2026, 3, 20, 7, 0, tzinfo=UTC)  # 8:00 czasu polskiego
    night = datetime(2026, 3, 20, 3, 0, tzinfo=UTC)
    assert notifications.send_digests(db, now=night) == 0
    assert notifications.send_digests(db, now=morning) == 1
    assert notifications.send_digests(db, now=morning) == 0
    assert _digest_jobs(db) == 1
    payload = (
        db.scalars(select(Job).where(Job.payload["subject"].astext.like("Wesele:%"))).one().payload
    )
    assert "PO TERMINIE" in payload["body"]


def test_digest_respects_off(client, alice, wedding, db, monkeypatch):
    client.put(f"{API}/me/notifications", headers=alice, json={"digest": "off"})
    monkeypatch.setattr(clock, "today", lambda: date(2026, 3, 20))
    assert notifications.send_digests(db, now=datetime(2026, 3, 20, 9, tzinfo=UTC)) == 0


def test_digest_polish_amounts_dates_and_kinds():
    from decimal import Decimal

    assert notifications.money_pl(Decimal("12500.5")) == "12 500,50 zł"
    assert notifications.money_pl(Decimal("80.00")) == "80,00 zł"
    assert notifications.date_pl(date(2027, 1, 5)) == "05.01.2027"


def test_digest_skips_sponsor_and_lists_documents(client, alice, user_factory, db, monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: date(2028, 6, 20))
    w = client.post(
        f"{API}/weddings",
        headers=alice,
        json={"name": "D", "ceremony_type": "concordat", "wedding_date": "2028-07-01"},
    ).json()
    url = f"{API}/weddings/{w['id']}"
    funder = client.post(f"{url}/funders", headers=alice, json={"name": "Rodzice"}).json()
    dad = user_factory("tata@example.com")
    invite_and_accept(
        client, alice, dad, w, "tata@example.com", role="sponsor", funder_id=funder["funder"]["id"]
    )
    client.put(f"{url}/ceremony-documents/baptism", headers=alice, json={"issued_on": "2027-11-01"})
    # Para dostaje pełne podsumowanie; sponsor bez swoich płatności — nic
    # (nie widzi zadań ani płatności wesela).
    assert notifications.send_digests(db, now=datetime(2028, 6, 20, 9, tzinfo=UTC)) == 1
    jobs = db.scalars(select(Job).where(Job.payload["subject"].astext.like("Wesele:%"))).all()
    assert [j.payload["to"] for j in jobs] == ["alice@example.com"]
    body = jobs[0].payload["body"]
    assert "Dokumenty do ślubu" in body
    assert "Świadectwo chrztu do ślubu: straci ważność 01.05.2028, przed ślubem" in body


def test_digest_lists_attendance_alerts(client, alice, db, monkeypatch):
    # Termin podania sali ostatecznej liczby (21 dni przed ślubem) za 10 dni, goście bez odpowiedzi.
    monkeypatch.setattr(clock, "today", lambda: date(2028, 6, 1))
    w = client.post(
        f"{API}/weddings",
        headers=alice,
        json={"name": "F", "ceremony_type": "civil", "wedding_date": "2028-07-01"},
    ).json()
    url = f"{API}/weddings/{w['id']}"
    h = client.post(f"{url}/households", headers=alice, json={"name": "Nowakowie"}).json()
    client.post(f"{url}/households/{h['id']}/guests", headers=alice, json={"first_name": "Jan"})
    assert notifications.send_digests(db, now=datetime(2028, 6, 1, 9, tzinfo=UTC)) == 1
    body = db.scalars(select(Job).where(Job.payload["subject"].astext.like("Wesele:%"))).one()
    assert "Frekwencja i sala" in body.payload["body"]
    assert "sala czeka na ostateczną liczbę gości" in body.payload["body"]


def test_sponsor_digest_only_own_payments(client, alice, user_factory, db, monkeypatch):
    from tests.api.test_offers import pln

    monkeypatch.setattr(clock, "today", lambda: date(2028, 6, 20))
    w = client.post(
        f"{API}/weddings",
        headers=alice,
        json={"name": "S", "ceremony_type": "civil", "wedding_date": "2028-07-01"},
    ).json()
    url = f"{API}/weddings/{w['id']}"
    funder = client.post(f"{url}/funders", headers=alice, json={"name": "Rodzice"}).json()
    cat = client.get(f"{url}/budget/categories", headers=alice).json()[0]["id"]
    item = client.post(
        f"{url}/budget/items",
        headers=alice,
        json={"category_id": cat, "name": "Sala", "planned": pln("30000")},
    ).json()
    pay = f"{url}/budget/items/{item['id']}/payments"
    client.post(
        pay,
        headers=alice,
        json={
            "kind": "final",
            "amount": pln("9000"),
            "due_date": "2028-06-24",
            "funder_id": funder["funder"]["id"],
        },
    )
    client.post(
        pay,
        headers=alice,
        json={"kind": "installment", "amount": pln("500"), "due_date": "2028-06-22"},
    )
    dad = user_factory("tata@example.com")
    invite_and_accept(
        client, alice, dad, w, "tata@example.com", role="sponsor", funder_id=funder["funder"]["id"]
    )
    assert notifications.send_digests(db, now=datetime(2028, 6, 20, 9, tzinfo=UTC)) == 2
    mail = (
        db.scalars(
            select(Job).where(
                Job.payload["to"].astext == "tata@example.com",
                Job.payload["subject"].astext.like("Wesele:%"),
            )
        )
        .one()
        .payload
    )
    assert mail["subject"].startswith("Wesele: Wasze płatności")
    assert "Sala (dopłata)" in mail["body"]
    assert "500" not in mail["body"]  # płatność pary — sponsor jej nie widzi
    assert "/wklad" in mail["body"]
