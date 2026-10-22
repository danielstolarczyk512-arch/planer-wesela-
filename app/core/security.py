"""Hasła (Argon2id), tokeny jednorazowe/refresh (tylko hash w bazie) i access JWT."""

import hashlib
import secrets
from datetime import timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from zxcvbn import zxcvbn

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.errors import Unauthorized

_hasher = PasswordHasher()  # Argon2id, parametry domyślne biblioteki (profil RFC 9106)
_DUMMY_HASH = _hasher.hash("wyrownanie-czasu-odpowiedzi")

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128

# Polskie hasła z wycieków, których nie zna słownik zxcvbn (sprawdzane przed oceną zxcvbn).
_COMMON_PASSWORDS = frozenset(
    {
        "1234567890",
        "12345678910",
        "qwertyuiop",
        "qwerty1234",
        "1q2w3e4r5t",
        "password12",
        "password123",
        "haslo12345",
        "haslo123456",
        "zaq12wsxcde",
        "polska1234",
        "kochamcie1",
        "kochamcie123",
        "zaq1@wsx",
        "abcdefghij",
        "wesele2026",
        "wesele2027",
        "slub123456",
        "iloveyou12",
        "0987654321",
        "1111111111",
        "aaaaaaaaaa",
        "qazwsxedcr",
        "monika1234",
        "marcin1234",
    }
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def verify_dummy(password: str) -> None:
    """Wyrównuje czas odpowiedzi, gdy konto nie istnieje (utrudnia enumerację kont)."""
    verify_password(_DUMMY_HASH, password)


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# Słowa, od których Polacy często zaczynają hasła (zxcvbn ma słowniki głównie angielskie):
# imiona, zdrobnienia, miesiące, dni, miasta, kluby, kolory, popularne rzeczowniki.
# Lista własna projektu; każde słowo także bez polskich znaków (np. „slonecznik”).
_CONTEXT_WORDS = (
    "wesele",
    "ślub",
    "slub",
    "hasło",
    "haslo",
    "kocham",
    "kochanie",
    "polska",
    "zaq1",
    "misiek",
    "skarb",
    "mojeslub",
    "weselnyplaner",
    "słonecznik",
    "slonecznik",
    "kwiatek",
    "różyczka",
    "rozyczka",
    "stokrotka",
    "tulipan",
    "konwalia",
    "niezapominajka",
    "bratek",
    "kotek",
    "kotka",
    "piesek",
    "misio",
    "misiaczek",
    "żabka",
    "zabka",
    "myszka",
    "rybka",
    "ptaszek",
    "słoneczko",
    "sloneczko",
    "gwiazdka",
    "aniołek",
    "aniolek",
    "serduszko",
    "kochana",
    "kochany",
    "skarbie",
    "mamusia",
    "tatuś",
    "tatus",
    "mama",
    "tata",
    "babcia",
    "dziadek",
    "niebo",
    "morze",
    "góry",
    "gory",
    "jezioro",
    "tęcza",
    "tecza",
    "zima",
    "wiosna",
    "lato",
    "jesień",
    "jesien",
    "styczeń",
    "styczen",
    "luty",
    "marzec",
    "kwiecień",
    "kwiecien",
    "maj",
    "czerwiec",
    "lipiec",
    "sierpień",
    "sierpien",
    "wrzesień",
    "wrzesien",
    "październik",
    "pazdziernik",
    "listopad",
    "grudzień",
    "grudzien",
    "poniedziałek",
    "poniedzialek",
    "wtorek",
    "środa",
    "sroda",
    "czwartek",
    "piątek",
    "piatek",
    "sobota",
    "niedziela",
    "warszawa",
    "kraków",
    "krakow",
    "gdańsk",
    "gdansk",
    "wrocław",
    "wroclaw",
    "poznań",
    "poznan",
    "łódź",
    "lodz",
    "szczecin",
    "lublin",
    "katowice",
    "białystok",
    "bialystok",
    "gdynia",
    "toruń",
    "torun",
    "legia",
    "lech",
    "wisła",
    "wisla",
    "cracovia",
    "górnik",
    "gornik",
    "śląsk",
    "slask",
    "pogoń",
    "pogon",
    "jagiellonia",
    "kasia",
    "ania",
    "basia",
    "gosia",
    "magda",
    "monika",
    "agnieszka",
    "karolina",
    "natalia",
    "aleksandra",
    "ola",
    "marta",
    "ewa",
    "joanna",
    "tomek",
    "michał",
    "michal",
    "piotr",
    "paweł",
    "pawel",
    "kuba",
    "jakub",
    "marcin",
    "łukasz",
    "lukasz",
    "krzysiek",
    "mateusz",
    "bartek",
    "daniel",
    "adam",
    "kamil",
    "dupa",
    "cześć",
    "czesc",
    "siema",
    "witaj",
    "zaraz",
    "kurczak",
    "pizza",
    "czekolada",
    "kawa",
    "herbata",
    "komputer",
    "internet",
    "zielony",
    "czerwony",
    "niebieski",
    "żółty",
    "zolty",
    "czarny",
    "biały",
    "bialy",
    "wolność",
    "wolnosc",
    "ojczyzna",
    "bóg",
    "bog",
    "polak",
    "polka",
    "orzeł",
    "orzel",
)
PASSWORD_MIN_SCORE = 2  # zxcvbn 0..4; 2 = odporne na zgadywanie online przy limicie prób


def password_problems(password: str, email: str | None = None) -> list[str]:
    problems: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        problems.append(f"Hasło musi mieć co najmniej {PASSWORD_MIN_LENGTH} znaków.")
    if len(password) > PASSWORD_MAX_LENGTH:
        problems.append(f"Hasło może mieć najwyżej {PASSWORD_MAX_LENGTH} znaków.")
    if password.lower() in _COMMON_PASSWORDS:
        problems.append("To hasło jest zbyt popularne.")
    elif PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        # Ocena offline (bez wysyłania hasła gdziekolwiek): słowniki, wzorce klawiatury, daty.
        # zxcvbn przyjmuje do 72 znaków; dłuższe hasło oceniamy po początku (i tak jest mocne).
        inputs = [*_CONTEXT_WORDS, *([email, email.split("@", 1)[0]] if email else [])]
        if zxcvbn(password[:72], user_inputs=inputs)["score"] < PASSWORD_MIN_SCORE:
            problems.append(
                "Hasło jest zbyt łatwe do odgadnięcia. Dodaj kilka mniej oczywistych słów."
            )
    if email:
        local = email.split("@", 1)[0].lower()
        if len(local) >= 4 and local in password.lower():
            problems.append("Hasło nie może zawierać nazwy z adresu e-mail.")
    return problems


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token() -> tuple[str, str]:
    """Zwraca (token dla klienta, hash do bazy)."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def create_access_token(user_id: UUID, session_id: UUID) -> tuple[str, int]:
    settings = get_settings()
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "typ": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    token = jwt.encode(
        payload, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm
    )
    return token, int(ttl.total_seconds())


def decode_access_token(token: str) -> tuple[UUID, UUID]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "sid"]},
        )
        if payload.get("typ") != "access":
            raise Unauthorized(code="auth.invalid_token")
        return UUID(payload["sub"]), UUID(payload["sid"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise Unauthorized(
            "Token jest nieprawidłowy lub wygasł.", code="auth.invalid_token"
        ) from exc
