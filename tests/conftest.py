"""Testy działają na osobnej bazie PostgreSQL (wedding_test) z Docker Compose.

Uruchomienie: task db:up && task test
"""

import os
import re
import tempfile
from collections.abc import Iterator
from typing import Any

# Konfiguracja MUSI być ustawiona przed importem aplikacji.
os.environ["WP_ENV"] = "test"
os.environ["WP_DATABASE_URL"] = os.environ.get(
    "WP_TEST_DATABASE_URL", "postgresql+psycopg://wedding:wedding@localhost:5433/wedding_test"
)
os.environ["WP_JWT_SECRET"] = "test-secret-" + "x" * 40
os.environ["WP_DATA_ENCRYPTION_KEY"] = "dGVzdC1rbHVjei0zMi1iYWp0eS10ZXN0LXRlc3QtISE="
os.environ["WP_STORAGE_DIR"] = tempfile.mkdtemp(prefix="wp-test-storage-")
os.environ["WP_AI_PROVIDER"] = "fake"  # testy nie wołają prawdziwego modelu (zob. ai_regression)
os.environ["WP_AUTH_COOKIE_SECURE"] = "false"  # TestClient działa na http://testserver
os.environ["WP_RATE_LIMIT_PER_MINUTE"] = "0"  # globalny limit testowany osobno (test_rate_limit)
os.environ["WP_LOG_JSON"] = "false"
os.environ["WP_LOG_LEVEL"] = "WARNING"

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.db import get_sessionmaker
from app.jobs.queue import Job
from app.main import create_app
from app.models import Base

PASSWORD = "Bardzo-dlugie-haslo-testowe-2026"  # gitleaks:allow - fikcyjne hasło testowe
LINK_TOKEN_RE = re.compile(r"token=([A-Za-z0-9_\-]+)")


def alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = os.environ["WP_DATABASE_URL"]
    cfg.attributes["configure_logger"] = False
    return cfg


@pytest.fixture(scope="session", autouse=True)
def _migrated_database() -> None:
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    yield
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with get_sessionmaker()() as db:
        db.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        db.commit()


@pytest.fixture(scope="session")
def app() -> Any:
    return create_app()


@pytest.fixture
def client(app: Any) -> TestClient:
    return TestClient(app)


@pytest.fixture
def db() -> Iterator[Session]:
    with get_sessionmaker()() as session:
        yield session


def last_email_to(email: str) -> dict[str, Any]:
    with get_sessionmaker()() as db:
        jobs = db.scalars(
            select(Job).where(Job.type == "send_email").order_by(Job.created_at.desc())
        ).all()
    for job in jobs:
        if job.payload.get("to") == email:
            return dict(job.payload)
    raise AssertionError(f"Brak e-maila do {email}")


def token_from_last_email(email: str) -> str:
    match = LINK_TOKEN_RE.search(last_email_to(email)["body"])
    assert match, "E-mail nie zawiera linku z tokenem"
    return match.group(1)


def register(
    client: TestClient,
    email: str,
    *,
    verify: bool = True,
    password: str = PASSWORD,
    name: str | None = None,
) -> None:
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": name,
            "accept_terms": True,
            "accept_privacy": True,
        },
    )
    assert r.status_code == 202, r.text
    if verify:
        token = token_from_last_email(email.lower())
        r = client.post("/api/v1/auth/verify-email", json={"token": token})
        assert r.status_code == 204, r.text


def login(client: TestClient, email: str, password: str = PASSWORD) -> dict[str, Any]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return dict(r.json())


def bearer(tokens: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def user_factory(client: TestClient) -> Any:
    def make(email: str, *, verify: bool = True, name: str | None = None) -> dict[str, str]:
        register(client, email, verify=verify, name=name)
        return bearer(login(client, email))

    return make


@pytest.fixture
def alice(user_factory: Any) -> dict[str, str]:
    return dict(user_factory("alice@example.com", name="Alicja"))


@pytest.fixture
def bob(user_factory: Any) -> dict[str, str]:
    return dict(user_factory("bob@example.com", name="Bartek"))


@pytest.fixture
def wedding(client: TestClient, alice: dict[str, str]) -> dict[str, Any]:
    r = client.post(
        "/api/v1/weddings",
        headers=alice,
        json={
            "name": "Alicja i Bartek",
            "planned_month": "2027-08",
            "ceremony_type": "concordat",
            "city": "KrakĂłw",
            "guest_count_planned": 110,
            "total_budget": {"amount": "65000", "currency": "PLN"},
        },
    )
    assert r.status_code == 201, r.text
    return dict(r.json())
