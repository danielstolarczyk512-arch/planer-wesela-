import time
from decimal import Decimal
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from app.core.errors import Unauthorized, Unprocessable
from app.core.ids import uuid7
from app.core.schemas import Money, decode_cursor, encode_cursor
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    new_token,
    password_problems,
    verify_password,
)


def test_uuid7_version_variant_and_order():
    first = uuid7()
    time.sleep(0.002)
    second = uuid7()
    assert first.version == 7
    assert first.variant == "specified in RFC 4122"
    assert first < second


def test_password_hash_roundtrip():
    h = hash_password("Bardzo-dlugie-haslo-1")
    assert h.startswith("$argon2id$")
    assert verify_password(h, "Bardzo-dlugie-haslo-1")
    assert not verify_password(h, "inne-haslo-123456")
    assert not verify_password("nie-hash", "cokolwiek")


@pytest.mark.parametrize(
    ("password", "expected_fragment"),
    [
        ("krotkie", "co najmniej"),
        ("x" * 129, "najwyżej"),
        ("qwertyuiop", "popularne"),
        ("ania.kowalska-2026", "nazwy z adresu"),
        ("password2026", "łatwe do odgadnięcia"),  # słownik + rok
        ("asdfghjkl;'", "łatwe do odgadnięcia"),  # wzorzec klawiatury
        ("wesele12345", "łatwe do odgadnięcia"),  # słowo z kontekstu aplikacji
    ],
)
def test_password_policy_rejects(password, expected_fragment):
    problems = password_problems(password, "ania.kowalska@example.com")
    assert any(expected_fragment in p for p in problems)


def test_password_policy_accepts_strong():
    assert password_problems("Zielony-Kubek-Na-Stole-77", "ania@example.com") == []


def test_tokens_are_random_and_hashed():
    token, token_hash = new_token()
    assert len(token) >= 40
    assert token_hash == hash_token(token)
    assert token not in token_hash
    assert new_token()[0] != token


def test_access_token_roundtrip_and_tamper():
    uid, sid = uuid7(), uuid7()
    token, ttl = create_access_token(uid, sid)
    assert ttl == 15 * 60
    assert decode_access_token(token) == (uid, sid)
    with pytest.raises(Unauthorized):
        decode_access_token(token[:-2] + "xx")


def test_cursor_roundtrip_and_invalid():
    value = uuid7()
    assert decode_cursor(encode_cursor(value)) == value
    with pytest.raises(Unprocessable):
        decode_cursor("@@nie-kursor@@")


@given(
    st.decimals(
        min_value=0,
        max_value=Decimal("9999999999.99"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    )
)
def test_money_serializes_with_two_decimals(amount: Decimal):
    dumped = Money(amount=amount).model_dump(mode="json")
    assert dumped["currency"] == "PLN"
    assert Decimal(dumped["amount"]) == amount
    assert len(dumped["amount"].split(".")[1]) == 2


@pytest.mark.parametrize("amount", ["-1", "1.001", "12345678901.00"])
def test_money_rejects_invalid(amount: str):
    with pytest.raises(ValidationError):
        Money(amount=Decimal(amount))


def test_money_rejects_other_currency():
    with pytest.raises(ValidationError):
        Money.model_validate({"amount": "10.00", "currency": "EUR"})


def test_uuid7_is_uuid():
    assert isinstance(uuid7(), UUID)


def test_polish_words_make_passwords_weak_but_passphrases_pass():
    from app.core.security import password_problems

    # Popularne polskie słowa z cyframi — także bez polskich znaków.
    for weak in ("słonecznik12", "slonecznik2026", "warszawa1234", "październik1"):
        assert password_problems(weak), weak
    # Kilka niezwiązanych słów nadal wystarcza (zalecenie w GUI).
    assert password_problems("tulipan-rower-mostek-41") == []
