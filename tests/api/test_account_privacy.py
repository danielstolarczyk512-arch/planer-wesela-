from datetime import timedelta

from sqlalchemy import select, text, update

from app.core.db import utcnow
from app.jobs.worker import run_maintenance
from app.modules.identity.models import User
from app.modules.workspace.models import Wedding
from tests.conftest import PASSWORD, bearer, login, register

API = "/api/v1"


def test_consents_grant_withdraw_and_history(client, alice):
    r = client.post(f"{API}/me/consents", headers=alice, json={"type": "marketing"})
    assert r.status_code == 201
    assert client.delete(f"{API}/me/consents/marketing", headers=alice).status_code == 204
    assert client.delete(f"{API}/me/consents/marketing", headers=alice).status_code == 404
    history = client.get(f"{API}/me/consents", headers=alice).json()
    marketing = [c for c in history if c["type"] == "marketing"]
    assert len(marketing) == 1
    assert marketing[0]["withdrawn_at"] is not None


def test_terms_consent_cannot_be_withdrawn_separately(client, alice):
    r = client.delete(f"{API}/me/consents/terms", headers=alice)
    assert r.status_code == 422
    assert r.json()["code"] == "consent.not_withdrawable"


def test_export_contains_my_data_without_secrets(client, alice, wedding):
    r = client.get(f"{API}/me/export", headers=alice)
    assert r.status_code == 200
    data = r.json()
    assert data["account"]["email"] == "alice@example.com"
    assert data["weddings"][0]["id"] == wedding["id"]
    assert "password" not in r.text
    assert "refresh_token" not in r.text


def test_delete_account_grace_period_cancel(client):
    register(client, "ania@example.com")
    h = bearer(login(client, "ania@example.com"))
    r = client.request("DELETE", f"{API}/me", headers=h, json={"password": PASSWORD})
    assert r.status_code == 202
    assert client.get(f"{API}/me", headers=h).json()["deletion_scheduled_at"] is not None
    assert client.post(f"{API}/me/cancel-deletion", headers=h).status_code == 204
    assert client.get(f"{API}/me", headers=h).json()["deletion_scheduled_at"] is None


def test_delete_account_wrong_password(client, alice):
    r = client.request("DELETE", f"{API}/me", headers=alice, json={"password": "zle-haslo-123"})
    assert r.status_code == 401


def test_sole_owner_with_members_cannot_delete_account(client, alice, bob, wedding):
    _add_bob(client, alice, bob, wedding)
    r = client.request("DELETE", f"{API}/me", headers=alice, json={"password": PASSWORD})
    assert r.status_code == 409
    assert r.json()["code"] == "account.sole_owner"


def test_anonymization_after_grace_period(client, db, alice, wedding):
    r = client.request("DELETE", f"{API}/me", headers=alice, json={"password": PASSWORD})
    assert r.status_code == 202
    db.execute(update(User).values(deletion_requested_at=utcnow() - timedelta(days=31)))
    db.commit()

    stats = run_maintenance()
    assert stats["accounts_anonymized"] == 1

    db.expire_all()
    user = db.scalars(select(User)).one()
    assert user.status == "deleted"
    assert user.email.startswith("deleted+")
    assert user.display_name is None
    assert db.scalars(select(Wedding)).first() is None  # wesele tylko tej osoby usunięte
    r = client.post(f"{API}/auth/login", json={"email": "alice@example.com", "password": PASSWORD})
    assert r.status_code == 401


def test_audit_log_is_append_only(db, alice):
    import pytest
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError):
        db.execute(text("DELETE FROM audit_log"))
    db.rollback()


def _add_bob(client, alice, bob, wedding):
    from tests.conftest import token_from_last_email

    r = client.post(
        f"{API}/weddings/{wedding['id']}/invitations",
        headers=alice,
        json={"email": "bob@example.com", "role": "coorganizer"},
    )
    assert r.status_code == 201, r.text
    token = token_from_last_email("bob@example.com")
    r = client.post(f"{API}/invitations/accept", headers=bob, json={"token": token})
    assert r.status_code == 200, r.text
