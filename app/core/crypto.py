"""Szyfrowanie wybranych kolumn (AES-256-GCM) dla danych szczególnie wrażliwych.

Format: 1 bajt wersji klucza + 12 bajtów nonce + szyfrogram z tagiem. Kontekst (np. id gościa)
jest wiązany jako associated data, więc szyfrogramu nie da się przenieść do innego rekordu.

Rotacja: szyfrujemy zawsze bieżącym kluczem (WP_DATA_ENCRYPTION_KEY_VERSION), odczytujemy
kluczem wskazanym przez bajt wersji (bieżący albo z WP_DATA_ENCRYPTION_PREVIOUS_KEYS).
"""

import base64
import binascii
import os
from functools import lru_cache

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings


def _key(raw: str, name: str) -> AESGCM:
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except (ValueError, binascii.Error) as exc:
        raise ValueError(f"{name} musi być kluczem base64 (32 bajty)") from exc
    if len(key) != 32:
        raise ValueError(f"{name} musi mieć 32 bajty (AES-256)")
    return AESGCM(key)


@lru_cache
def _ciphers() -> tuple[int, dict[int, AESGCM]]:
    """(bieżąca wersja, {wersja: szyfr})."""
    settings = get_settings()
    current = settings.data_encryption_key_version
    keys = {
        current: _key(settings.data_encryption_key.get_secret_value(), "WP_DATA_ENCRYPTION_KEY")
    }
    previous = settings.data_encryption_previous_keys
    for item in previous.get_secret_value().split(",") if previous else []:
        version, sep, raw = item.strip().partition(":")
        if not sep or not version.isdigit() or not 1 <= int(version) <= 255:
            raise ValueError("WP_DATA_ENCRYPTION_PREVIOUS_KEYS: format 'wersja:klucz,...'")
        if int(version) == current:
            raise ValueError("Stary klucz nie może mieć wersji bieżącego klucza")
        keys[int(version)] = _key(raw, f"Klucz w wersji {version}")
    return current, keys


def current_version() -> int:
    return _ciphers()[0]


def key_version(blob: bytes) -> int:
    return blob[0]


def encrypt(plaintext: str, context: bytes) -> bytes:
    version, keys = _ciphers()
    nonce = os.urandom(12)
    return bytes([version]) + nonce + keys[version].encrypt(nonce, plaintext.encode(), context)


def decrypt(blob: bytes, context: bytes) -> str:
    _, keys = _ciphers()
    cipher = keys.get(blob[0]) if blob else None
    if cipher is None:
        raise ValueError("Nieznana wersja klucza szyfrowania")
    return cipher.decrypt(blob[1:13], blob[13:], context).decode()


def generate_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode()
