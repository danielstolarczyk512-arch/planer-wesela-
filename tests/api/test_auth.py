from datetime import timedelta

from sqlalchemy import func, select, update

from app.core.db import utcnow
from app.modules.audit.models import SecurityEvent
from app.modules.identity.models import AuthSession, Consent, User
from tests.conftest import PASSWORD, bearer, last_email_to, login, register, token_from_last_email

API = "/api/v1"
WRONG_PASSWORD = "zle-haslo-123456"  # gitleaks:allow - fikcyjne hasło testowe


def test_register_verify_login_me(client, db):
    register(client, "Ania@Example.com", name="Ania")
    tokens = login(client, "ania@example.com")
    assert tokens["token_type"] == "bearer"
    me = client.get(f"{API}/me", headers=bearer(tokens)).json()
    assert me["email"] == "ania@example.com"  # e-mail znormalizowany
    assert me["email_verified"] is True
    user = db.scalars(select(User)).one()
    assert user.password_hash.startswith("$argon2id$")
    consents = {c.type for c in db.scalars(select(Consent))}
    assert consents == {"terms", "privacy"}


def test_register_requires_terms(client):
    r = client.post(
        f"{API}/auth/register",
        json={
            "email": "a@example.com",
            "password": PASSWORD,
            "accept_terms": False,
            "accept_privacy": True,
        },
    )
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")


def test_register_weak_password_does_not_echo_password(client):
    r = client.post(
        f"{API}/auth/register",
        json={
            "email": "a@example.com",
            "password": "qwertyuiop",
            "accept_terms": True,
            "accept_privacy": True,
        },
    )
    assert r.status_code == 422
    assert r.json()["code"] == "auth.weak_password"
    assert "qwertyuiop" not in r.text


def test_register_existing_email_is_indistinguishable(client, db):
    register(client, "ania@example.com")
    r = client.post(
        f"{API}/auth/register",
        json={
            "email": "ania@example.com",
            "password": PASSWORD,
            "accept_terms": True,
            "accept_privacy": True,
        },
    )
    assert r.status_code == 202
    assert "już istnieje" in last_email_to("ania@example.com")["body"]
    assert db.scalar(select(func.count()).select_from(User)) == 1


def test_verify_email_token_single_use(client):
    register(client, "ania@example.com", verify=False)
    token = token_from_last_email("ania@example.com")
    assert client.post(f"{API}/auth/verify-email", json={"token": token}).status_code == 204
    r = client.post(f"{API}/auth/verify-email", json={"token": token})
    assert r.status_code == 422
    assert r.json()["code"] == "auth.invalid_token"


def test_login_wrong_password_and_unknown_user_same_error(client, db):
    register(client, "ania@example.com")
    wrong = client.post(
        f"{API}/auth/login", json={"email": "ania@example.com", "password": WRONG_PASSWORD}
    )
    unknown = client.post(
        f"{API}/auth/login", json={"email": "nikt@example.com", "password": WRONG_PASSWORD}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["code"] == unknown.json()["code"] == "auth.invalid_credentials"
    assert (
        db.scalar(
            select(func.count())
            .select_from(SecurityEvent)
            .where(SecurityEvent.type == "login_failed")
        )
        == 2
    )


def test_login_brute_force_limited(client):
    register(client, "ania@example.com")
    for _ in range(5):
        r = client.post(
            f"{API}/auth/login", json={"email": "ania@example.com", "password": WRONG_PASSWORD}
        )
        assert r.status_code == 401
    r = client.post(f"{API}/auth/login", json={"email": "ania@example.com", "password": PASSWORD})
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0


def test_protected_endpoint_requires_token(client):
    r = client.get(f"{API}/me")
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"
    r = client.get(f"{API}/me", headers={"Authorization": "Bearer nie.jest.jwt"})
    assert r.status_code == 401


def test_refresh_rotation_and_reuse_detection(client, db):
    register(client, "ania@example.com")
    first = login(client, "ania@example.com")
    r = client.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert r.status_code == 200
    second = r.json()
    assert second["refresh_token"] != first["refresh_token"]
    # Następca użyty → stary token nie mieści się już w oknie tolerancji.
    third = client.post(f"{API}/auth/refresh", json={"refresh_token": second["refresh_token"]})
    second = third.json()

    # Ponowne użycie starego tokena → odrzucenie i unieważnienie całej rodziny sesji.
    r = client.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert r.status_code == 401
    r = client.post(f"{API}/auth/refresh", json={"refresh_token": second["refresh_token"]})
    assert r.status_code == 401
    assert client.get(f"{API}/me", headers=bearer(second)).status_code == 401
    assert (
        db.scalar(
            select(func.count())
            .select_from(SecurityEvent)
            .where(SecurityEvent.type == "refresh_token_reuse")
        )
        == 1
    )


WEB = {"X-Client": "web"}


def test_web_client_keeps_refresh_token_in_httponly_cookie(client):
    register(client, "ania@example.com")
    r = client.post(
        f"{API}/auth/login",
        headers=WEB,
        json={"email": "ania@example.com", "password": PASSWORD},
    )
    assert r.status_code == 200
    assert r.json()["refresh_token"] is None  # JavaScript nie widzi refresh tokena
    cookie = r.headers["set-cookie"]
    assert "wp_refresh=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/api/v1/auth" in cookie

    # Odświeżenie z ciasteczka działa tylko z nagłówkiem klienta webowego.
    assert client.post(f"{API}/auth/refresh", json={}).status_code == 401
    r2 = client.post(f"{API}/auth/refresh", headers=WEB)
    assert r2.status_code == 200
    assert r2.json()["refresh_token"] is None
    access = {"Authorization": f"Bearer {r2.json()['access_token']}"}
    assert client.get(f"{API}/me", headers=access).status_code == 200

    out = client.post(f"{API}/auth/logout", headers={**access, **WEB})
    assert out.status_code == 204
    assert 'wp_refresh=""' in out.headers["set-cookie"] or "Max-Age=0" in out.headers["set-cookie"]
    assert client.post(f"{API}/auth/refresh", headers=WEB).status_code == 401


def test_web_refresh_with_revoked_cookie_clears_it(client):
    register(client, "ania@example.com")
    client.post(
        f"{API}/auth/login", headers=WEB, json={"email": "ania@example.com", "password": PASSWORD}
    )
    client.cookies.set("wp_refresh", "nieprawidlowy-token-" + "x" * 30, path="/api/v1/auth")
    r = client.post(f"{API}/auth/refresh", headers=WEB)
    assert r.status_code == 401
    assert "Max-Age=0" in r.headers["set-cookie"] or 'wp_refresh=""' in r.headers["set-cookie"]


def test_mobile_client_still_gets_refresh_token_in_body(client):
    register(client, "ania@example.com")
    tokens = login(client, "ania@example.com")
    assert tokens["refresh_token"]
    r = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200


def test_parallel_refresh_retry_is_tolerated(client, db):
    register(client, "ania@example.com")
    first = login(client, "ania@example.com")
    a = client.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    # Ponowienie tego samego żądania (np. utracona odpowiedź na słabym zasięgu).
    b = client.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert a.status_code == b.status_code == 200
    assert a.json()["refresh_token"] != b.json()["refresh_token"]
    assert client.get(f"{API}/me", headers=bearer(a.json())).status_code == 200
    assert client.get(f"{API}/me", headers=bearer(b.json())).status_code == 200
    events = db.scalars(select(SecurityEvent.type)).all()
    assert "refresh_token_retry" in events
    assert "refresh_token_reuse" not in events

    # Po oknie tolerancji ponowne użycie = możliwa kradzież.
    db.execute(
        update(AuthSession)
        .where(AuthSession.revoked_reason == "rotated")
        .values(revoked_at=utcnow() - timedelta(minutes=5))
    )
    db.commit()
    r = client.post(f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert r.status_code == 401
    assert client.get(f"{API}/me", headers=bearer(a.json())).status_code == 401


def test_access_token_from_before_rotation_still_valid_until_logout(client):
    register(client, "ania@example.com")
    first = login(client, "ania@example.com")
    second = client.post(
        f"{API}/auth/refresh", json={"refresh_token": first["refresh_token"]}
    ).json()
    assert client.get(f"{API}/me", headers=bearer(first)).status_code == 200
    assert client.post(f"{API}/auth/logout", headers=bearer(second)).status_code == 204
    assert client.get(f"{API}/me", headers=bearer(first)).status_code == 401
    assert client.get(f"{API}/me", headers=bearer(second)).status_code == 401


def test_logout_only_current_device(client):
    register(client, "ania@example.com")
    phone = login(client, "ania@example.com")
    laptop = login(client, "ania@example.com")
    assert client.post(f"{API}/auth/logout", headers=bearer(phone)).status_code == 204
    assert client.get(f"{API}/me", headers=bearer(phone)).status_code == 401
    assert client.get(f"{API}/me", headers=bearer(laptop)).status_code == 200


def test_forgot_and_reset_password_revokes_sessions(client):
    register(client, "ania@example.com")
    old = login(client, "ania@example.com")
    r = client.post(f"{API}/auth/password/forgot", json={"email": "ania@example.com"})
    assert r.status_code == 202
    token = token_from_last_email("ania@example.com")
    r = client.post(
        f"{API}/auth/password/reset",
        json={"token": token, "new_password": "Nowe-Haslo-Do-Testow-99"},
    )
    assert r.status_code == 204
    assert client.get(f"{API}/me", headers=bearer(old)).status_code == 401
    login(client, "ania@example.com", "Nowe-Haslo-Do-Testow-99")
    r = client.post(f"{API}/auth/login", json={"email": "ania@example.com", "password": PASSWORD})
    assert r.status_code == 401


def test_forgot_password_unknown_email_same_response(client):
    r = client.post(f"{API}/auth/password/forgot", json={"email": "nikt@example.com"})
    assert r.status_code == 202


def test_change_password_keeps_current_device_only(client):
    register(client, "ania@example.com")
    current = login(client, "ania@example.com")
    other = login(client, "ania@example.com")
    r = client.post(
        f"{API}/me/password",
        headers=bearer(current),
        json={"current_password": PASSWORD, "new_password": "Zupelnie-Nowe-Haslo-42"},
    )
    assert r.status_code == 204
    assert client.get(f"{API}/me", headers=bearer(current)).status_code == 200
    assert client.get(f"{API}/me", headers=bearer(other)).status_code == 401


def test_sessions_list_and_revoke(client, db):
    register(client, "ania@example.com")
    a = login(client, "ania@example.com")
    b = login(client, "ania@example.com")
    sessions = client.get(f"{API}/me/sessions", headers=bearer(a)).json()
    assert len(sessions) == 2
    assert sum(s["current"] for s in sessions) == 1
    other = next(s for s in sessions if not s["current"])
    assert client.delete(f"{API}/me/sessions/{other['id']}", headers=bearer(a)).status_code == 204
    assert client.get(f"{API}/me", headers=bearer(b)).status_code == 401
    assert (
        db.scalar(
            select(func.count()).select_from(AuthSession).where(AuthSession.revoked_at.is_(None))
        )
        == 1
    )


def test_profile_update(client):
    register(client, "ania@example.com")
    h = bearer(login(client, "ania@example.com"))
    r = client.patch(f"{API}/me", headers=h, json={"display_name": "Ania K.", "locale": "en-GB"})
    assert r.status_code == 200
    assert r.json()["display_name"] == "Ania K."
    assert r.json()["locale"] == "en-GB"


def test_resend_verification(client):
    register(client, "ania@example.com", verify=False)
    h = bearer(login(client, "ania@example.com"))
    assert client.post(f"{API}/me/verify-email/resend", headers=h).status_code == 204
    token = token_from_last_email("ania@example.com")
    assert client.post(f"{API}/auth/verify-email", json={"token": token}).status_code == 204
