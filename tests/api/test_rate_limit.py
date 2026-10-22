"""Etap 6: globalny limit żądań (na użytkownika albo prefiks IP)."""

import pytest
from fastapi.testclient import TestClient

from app.core import throttle
from app.core.config import get_settings
from app.main import create_app

API = "/api/v1"


@pytest.fixture
def limited(monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 5)
    monkeypatch.setattr(throttle.time, "time", lambda: 1_800_000_030.0)  # bez zmiany okna
    return TestClient(create_app())


def test_limit_per_user_and_ip(limited, alice):
    for _ in range(5):
        assert limited.get(f"{API}/me", headers=alice).status_code == 200
    r = limited.get(f"{API}/me", headers=alice)
    assert r.status_code == 429
    assert r.json()["code"] == "rate_limited"
    assert r.headers["retry-after"] == "31"
    # Inny klucz (anonimowy adres) ma własny licznik; zdrowie nie jest limitowane.
    assert limited.get(f"{API}/me").status_code == 401
    for _ in range(10):
        assert limited.get("/health/live").status_code == 200


def test_invalid_token_counts_by_ip(limited):
    bad = {"Authorization": "Bearer nieprawidlowy"}
    codes = [limited.get(f"{API}/me", headers=bad).status_code for _ in range(7)]
    assert codes[:5] == [401] * 5
    assert codes[5:] == [429, 429]


def test_rsvp_limit_configurable(monkeypatch, client):
    # Publiczne RSVP: limit na adres IP w oknie 10 minut, ustawiany w konfiguracji.
    monkeypatch.setattr(get_settings(), "rsvp_rate_limit", 3)
    codes = [client.get(f"{API}/rsvp/nieistniejacy-token").status_code for _ in range(4)]
    assert codes == [404, 404, 404, 429]
