"""Health, nagłówki, format błędów, kolejka zadań, zgodność modeli z migracjami."""

from datetime import timedelta

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import select

from app.core.db import get_engine, get_sessionmaker, utcnow
from app.jobs import worker
from app.jobs.queue import Job, enqueue
from app.models import Base
from tests.conftest import register

API = "/api/v1"


def test_health(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ok"}


def test_security_headers_and_request_id(client):
    r = client.get("/health/live", headers={"X-Request-ID": "test-request-1234"})
    assert r.headers["X-Request-ID"] == "test-request-1234"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Cache-Control"] == "no-store"
    generated = client.get("/health/live", headers={"X-Request-ID": "<script>"})
    assert generated.headers["X-Request-ID"] != "<script>"


def test_unknown_route_problem_json(client):
    r = client.get(f"{API}/nie-ma-takiej-trasy")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == "not_found"


def test_openapi_available_in_dev(client):
    spec = client.get(f"{API}/openapi.json").json()
    assert "/api/v1/weddings" in spec["paths"]


def test_models_match_migrations():
    with get_engine().connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"Modele różnią się od migracji: {diff}"


def test_worker_sends_email_and_scrubs_payload(client, monkeypatch):
    sent = []
    monkeypatch.setattr(
        worker, "send_email", lambda to, s, b, html=None: sent.append((to, s, b, html))
    )
    register(client, "ania@example.com", verify=False)
    while worker.run_once():
        pass
    assert sent
    assert sent[0][0] == "ania@example.com"
    assert sent[0][3].startswith("<!doctype html>")  # wersja HTML trafia do wysyłki
    with get_sessionmaker()() as db:
        job = db.scalars(select(Job)).one()
        assert job.status == "succeeded"
        assert job.payload == {"scrubbed": True}


def test_worker_retries_then_dead(monkeypatch):
    def boom(_db, _payload):
        raise RuntimeError("smtp down: ania@example.com")

    with get_sessionmaker()() as db:
        job = enqueue(db, "flaky", {"x": 1}, max_attempts=2)
        db.commit()
        job_id = job.id
    handlers = {"flaky": boom}
    assert worker.run_once(handlers)
    with get_sessionmaker()() as db:
        job = db.get_one(Job, job_id)
        assert job.status == "queued"
        assert job.last_error == "RuntimeError"  # bez treści (mogła zawierać e-mail)
        job.run_after = utcnow() - timedelta(seconds=1)
        db.commit()
    assert worker.run_once(handlers)
    with get_sessionmaker()() as db:
        assert db.get_one(Job, job_id).status == "dead"


def test_unknown_job_type_fails_safely():
    with get_sessionmaker()() as db:
        enqueue(db, "nieznany", {}, max_attempts=1)
        db.commit()
    assert worker.run_once()
    with get_sessionmaker()() as db:
        assert db.scalars(select(Job)).one().status == "dead"


def test_maintenance_requeues_stale_jobs():
    with get_sessionmaker()() as db:
        job = enqueue(db, "x", {})
        job.status = "running"
        job.locked_until = utcnow() - timedelta(minutes=1)
        db.commit()
    stats = worker.run_maintenance()
    assert stats["stale_jobs_requeued"] == 1


def test_long_job_keeps_its_lock(monkeypatch):
    """Audyt 2026-10-23 (4.2): heartbeat odnawia blokadę, gdy zadanie trwa dłużej niż takt."""
    import time

    monkeypatch.setattr(worker, "HEARTBEAT_INTERVAL", 0.05)
    seen: list = []

    def slow(_db, _payload):
        with get_sessionmaker()() as other:
            first = other.scalars(select(Job.locked_until)).one()
        time.sleep(0.3)
        with get_sessionmaker()() as other:
            seen.extend([first, other.scalars(select(Job.locked_until)).one()])

    with get_sessionmaker()() as db:
        enqueue(db, "wolne", {})
        db.commit()
    assert worker.run_once({"wolne": slow})
    assert seen[1] > seen[0]
    with get_sessionmaker()() as db:
        assert db.scalars(select(Job)).one().status == "succeeded"
