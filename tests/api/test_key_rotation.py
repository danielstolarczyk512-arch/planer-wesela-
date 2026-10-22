"""Etap 6: rotacja klucza szyfrowania uwag dietetycznych."""

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.core import crypto
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.modules.guests import service as guests
from app.modules.guests.models import Guest
from scripts import rotate_encryption_key

API = "/api/v1"


@pytest.fixture
def rotated_settings(monkeypatch):
    settings = get_settings()
    old_key = settings.data_encryption_key.get_secret_value()

    def rotate(previous: bool = True):
        monkeypatch.setattr(settings, "data_encryption_key", SecretStr(new_key))
        monkeypatch.setattr(settings, "data_encryption_key_version", 2)
        monkeypatch.setattr(
            settings,
            "data_encryption_previous_keys",
            SecretStr(f"1:{old_key}") if previous else None,
        )
        crypto._ciphers.cache_clear()

    new_key = crypto.generate_key()
    yield rotate
    crypto._ciphers.cache_clear()


def _note_and_version():
    with get_sessionmaker()() as db:
        g = db.scalars(select(Guest)).one()
        return guests.dietary_note(g), crypto.key_version(g.dietary_note_encrypted), g.version


def test_rotation_keeps_notes_readable(client, alice, wedding, rotated_settings, capsys):
    url = f"{API}/weddings/{wedding['id']}"
    h = client.post(f"{url}/households", headers=alice, json={"name": "Nowak"}).json()
    client.post(
        f"{url}/households/{h['id']}/guests",
        headers=alice,
        json={"first_name": "Jan", "dietary_note": "alergia na orzechy"},
    )
    assert _note_and_version()[:2] == ("alergia na orzechy", 1)

    rotated_settings(previous=True)
    assert _note_and_version()[:2] == ("alergia na orzechy", 1)  # stary klucz do odczytu

    assert rotate_encryption_key.main(["rotate", "--dry-run"]) == 0
    assert "'old_key': 1, 'rotated': 0" in capsys.readouterr().out
    _, version_before, record_version = _note_and_version()
    assert version_before == 1

    assert rotate_encryption_key.main(["rotate"]) == 0
    assert "'rotated': 1" in capsys.readouterr().out
    note, key_version, record_version_after = _note_and_version()
    assert (note, key_version) == ("alergia na orzechy", 2)
    assert record_version_after == record_version  # klienci nie dostaną konfliktu wersji

    rotated_settings(previous=False)  # stary klucz można już usunąć
    assert _note_and_version()[0] == "alergia na orzechy"


def test_invalid_previous_keys_rejected(rotated_settings, monkeypatch):
    monkeypatch.setattr(get_settings(), "data_encryption_previous_keys", SecretStr("zly-format"))
    crypto._ciphers.cache_clear()
    with pytest.raises(ValueError, match="format"):
        crypto.encrypt("x", b"ctx")


def test_mfa_secrets_rotate_with_key(client, rotated_settings):
    import pyotp

    from app.modules.identity import mfa
    from app.modules.identity.models import UserMfa
    from tests.conftest import PASSWORD, bearer, login, register

    register(client, "rot@example.com")
    tokens = login(client, "rot@example.com")
    secret = client.post(
        f"{API}/me/mfa/setup", json={"password": PASSWORD}, headers=bearer(tokens)
    ).json()["secret"]
    assert (
        client.post(
            f"{API}/me/mfa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=bearer(tokens)
        ).status_code
        == 200
    )
    rotated_settings()
    with get_sessionmaker()() as db:
        assert mfa.reencrypt_secrets(db, dry_run=False) == {
            "encrypted": 1,
            "old_key": 1,
            "rotated": 1,
        }
        record = db.scalars(select(UserMfa)).one()
        assert crypto.key_version(record.secret_encrypted) == 2
        assert mfa._secret(record) == secret
