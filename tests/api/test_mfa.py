"""Weryfikacja dwuetapowa (TOTP): konfiguracja, logowanie w dwóch krokach, kody zapasowe, limity."""

import secrets
import time

import pyotp
from sqlalchemy import select

from app.modules.audit.models import SecurityEvent
from app.modules.identity.models import MfaRecoveryCode, UserMfa
from tests.conftest import PASSWORD, bearer, login, register

API = "/api/v1"
EMAIL = "mfa@example.com"
# Złe hasło generowane przy każdym uruchomieniu (bez stałych haseł w repozytorium).
WRONG_PASSWORD = f"zle-{secrets.token_urlsafe(12)}"


def _enable(client, tokens) -> tuple[pyotp.TOTP, list[str]]:
    setup = client.post(f"{API}/me/mfa/setup", json={"password": PASSWORD}, headers=bearer(tokens))
    assert setup.status_code == 200, setup.text
    body = setup.json()
    assert body["otpauth_uri"].startswith("otpauth://totp/")
    assert body["qr_svg"].lstrip().startswith("<svg")
    totp = pyotp.TOTP(body["secret"])
    r = client.post(f"{API}/me/mfa/enable", json={"code": totp.now()}, headers=bearer(tokens))
    assert r.status_code == 200, r.text
    codes = r.json()["recovery_codes"]
    assert len(codes) == 10
    assert len(set(codes)) == 10
    return totp, codes


def _next_code(totp: pyotp.TOTP) -> str:
    """Kod z następnego okna 30 s (ten sam kod nie działa dwa razy)."""
    return totp.at(int(time.time()) + 30)


def test_setup_requires_password_and_secret_is_encrypted(client, db):
    register(client, EMAIL)
    tokens = login(client, EMAIL)
    r = client.post(
        f"{API}/me/mfa/setup", json={"password": WRONG_PASSWORD}, headers=bearer(tokens)
    )
    assert r.status_code == 401
    r = client.post(f"{API}/me/mfa/setup", json={"password": PASSWORD}, headers=bearer(tokens))
    secret = r.json()["secret"]
    record = db.scalars(select(UserMfa)).one()
    assert secret.encode() not in record.secret_encrypted
    assert record.enabled_at is None
    # Bez potwierdzenia kodem logowanie nadal jednoetapowe.
    assert "access_token" in login(client, EMAIL)


def test_enable_with_wrong_code_is_rejected(client):
    register(client, EMAIL)
    tokens = login(client, EMAIL)
    client.post(f"{API}/me/mfa/setup", json={"password": PASSWORD}, headers=bearer(tokens))
    r = client.post(f"{API}/me/mfa/enable", json={"code": "000000"}, headers=bearer(tokens))
    assert r.status_code == 422
    assert r.json()["code"] == "mfa.invalid_code"


def test_two_step_login_and_me_flags(client, db):
    register(client, EMAIL)
    tokens = login(client, EMAIL)
    totp, codes = _enable(client, tokens)
    me = client.get(f"{API}/me", headers=bearer(tokens)).json()
    assert me["mfa_enabled"] is True
    assert me["mfa_recovery_codes_left"] == 10
    # Kody zapasowe tylko jako skróty.
    stored = {c.code_hash for c in db.scalars(select(MfaRecoveryCode))}
    assert not any(code.replace("-", "") in h for code in codes for h in stored)

    first = client.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert first.status_code == 200
    challenge = first.json()
    assert challenge["mfa_required"] is True
    assert "access_token" not in challenge
    r = client.post(
        f"{API}/auth/login/mfa",
        json={"mfa_token": challenge["mfa_token"], "code": _next_code(totp)},
    )
    assert r.status_code == 200, r.text
    assert client.get(f"{API}/me", headers=bearer(r.json())).status_code == 200
    # Token wyzwania jest jednorazowy.
    again = client.post(
        f"{API}/auth/login/mfa",
        json={"mfa_token": challenge["mfa_token"], "code": _next_code(totp)},
    )
    assert again.status_code == 401
    assert again.json()["code"] == "mfa.challenge_expired"


def test_code_cannot_be_reused(client):
    register(client, EMAIL)
    tokens = login(client, EMAIL)
    totp, _ = _enable(client, tokens)  # włączenie zużyło bieżący kod
    challenge = client.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()
    r = client.post(
        f"{API}/auth/login/mfa", json={"mfa_token": challenge["mfa_token"], "code": totp.now()}
    )
    assert r.status_code == 401
    assert r.json()["code"] == "mfa.invalid_code"


def test_recovery_code_works_once(client):
    register(client, EMAIL)
    tokens = login(client, EMAIL)
    _, codes = _enable(client, tokens)
    for expected in (200, 401):
        challenge = client.post(
            f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}
        ).json()
        r = client.post(
            f"{API}/auth/login/mfa",
            json={"mfa_token": challenge["mfa_token"], "code": codes[0].upper()},
        )
        assert r.status_code == expected, r.text
    me = client.get(f"{API}/me", headers=bearer(tokens)).json()
    assert me["mfa_recovery_codes_left"] == 9


def test_brute_force_is_limited(client, db):
    register(client, EMAIL)
    tokens = login(client, EMAIL)
    _enable(client, tokens)
    statuses = []
    for _ in range(6):
        challenge = client.post(
            f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}
        ).json()
        r = client.post(
            f"{API}/auth/login/mfa", json={"mfa_token": challenge["mfa_token"], "code": "123456"}
        )
        statuses.append(r.status_code)
    assert statuses[:5] == [401] * 5
    assert statuses[5] == 429
    events = [e.type for e in db.scalars(select(SecurityEvent))]
    assert events.count("mfa_failed") == 5


def test_tokens_are_not_interchangeable(client):
    register(client, EMAIL)
    tokens = login(client, EMAIL)
    _enable(client, tokens)
    challenge = client.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()
    # Token wyzwania nie jest tokenem dostępu…
    assert (
        client.get(
            f"{API}/me", headers={"Authorization": f"Bearer {challenge['mfa_token']}"}
        ).status_code
        == 401
    )
    # …a token dostępu nie jest tokenem wyzwania.
    r = client.post(
        f"{API}/auth/login/mfa", json={"mfa_token": tokens["access_token"], "code": "123456"}
    )
    assert r.status_code == 401
    assert r.json()["code"] == "mfa.challenge_expired"


def test_web_client_gets_cookie_after_second_step(client):
    register(client, EMAIL)
    tokens = login(client, EMAIL)
    totp, _ = _enable(client, tokens)
    challenge = client.post(
        f"{API}/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        headers={"X-Client": "web"},
    ).json()
    assert "set-cookie" not in {k.lower() for k in challenge}
    r = client.post(
        f"{API}/auth/login/mfa",
        json={"mfa_token": challenge["mfa_token"], "code": _next_code(totp)},
        headers={"X-Client": "web"},
    )
    assert r.status_code == 200
    assert r.json()["refresh_token"] is None
    assert "wp_refresh=" in r.headers["set-cookie"]


def test_disable_requires_password_and_code(client, db):
    register(client, EMAIL)
    tokens = login(client, EMAIL)
    totp, codes = _enable(client, tokens)
    r = client.post(
        f"{API}/me/mfa/disable",
        json={"password": WRONG_PASSWORD, "code": _next_code(totp)},
        headers=bearer(tokens),
    )
    assert r.status_code == 401
    r = client.post(
        f"{API}/me/mfa/disable",
        json={"password": PASSWORD, "code": codes[1]},
        headers=bearer(tokens),
    )
    assert r.status_code == 204
    assert db.scalars(select(UserMfa)).first() is None
    assert db.scalars(select(MfaRecoveryCode)).first() is None
    assert "access_token" in login(client, EMAIL)


def test_regenerate_recovery_codes(client):
    register(client, EMAIL)
    tokens = login(client, EMAIL)
    totp, old = _enable(client, tokens)
    r = client.post(
        f"{API}/me/mfa/recovery-codes",
        json={"password": PASSWORD, "code": _next_code(totp)},
        headers=bearer(tokens),
    )
    assert r.status_code == 200
    new = r.json()["recovery_codes"]
    assert set(new).isdisjoint(old)
    challenge = client.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()
    r = client.post(
        f"{API}/auth/login/mfa", json={"mfa_token": challenge["mfa_token"], "code": old[0]}
    )
    assert r.status_code == 401
