"""Weryfikacja dwuetapowa (TOTP, RFC 6238) i kody zapasowe.

- Sekret: 160 bitów (pyotp), zaszyfrowany AES-GCM z kontekstem użytkownika (app.core.crypto).
- Kod z aplikacji (Google Authenticator, Aegis, 1Password…): okno ±1 krok (30 s), każdy krok
  można użyć tylko raz (`last_used_step`), limit 5 błędnych prób na 15 min na konto.
- Kody zapasowe: 10 kodów po 10 znaków, pokazywane raz; w bazie tylko SHA-256; każdy jednorazowy.
- Logowanie z MFA: hasło → krótki token wyzwania (JWT typ „mfa”, 5 min, jednorazowy) → kod.
"""

import secrets
import time
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

import jwt
import pyotp
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core import crypto, mail_templates, ratelimit
from app.core.config import get_settings
from app.core.db import utcnow
from app.core.email import queue_mail
from app.core.errors import Conflict, RateLimited, Unauthorized, Unprocessable
from app.core.qr import qr_svg
from app.core.security import hash_token, verify_password
from app.modules.audit import service as audit
from app.modules.identity.models import MfaRecoveryCode, User, UserMfa

ISSUER = "Nasz dzień"
CHALLENGE_TTL = timedelta(minutes=5)
MAX_FAILURES = 5
FAILURE_WINDOW = timedelta(minutes=15)
RECOVERY_CODES = 10
_RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # bez 0/o, 1/l/i


@dataclass(frozen=True)
class SetupData:
    secret: str
    otpauth_uri: str
    qr_svg: str


@dataclass(frozen=True)
class MfaChallenge:
    mfa_token: str
    expires_in: int


def _context(user_id: UUID) -> bytes:
    return f"mfa:{user_id}".encode()


def _secret(record: UserMfa) -> str:
    return crypto.decrypt(record.secret_encrypted, _context(record.user_id))


def get(db: Session, user_id: UUID) -> UserMfa | None:
    return db.get(UserMfa, user_id)


def is_enabled(db: Session, user_id: UUID) -> bool:
    record = get(db, user_id)
    return record is not None and record.enabled_at is not None


def _require_password(user: User, password: str) -> None:
    if not verify_password(user.password_hash, password):
        raise Unauthorized("Nieprawidłowe hasło.", code="auth.invalid_credentials")


def _fail_key(user_id: UUID) -> str:
    return ratelimit.key_for("mfa_fail", str(user_id))


def _normalize(code: str) -> str:
    return "".join(code.split()).replace("-", "").lower()


def _verify_totp(db: Session, record: UserMfa, code: str) -> bool:
    digits = _normalize(code)
    if not (digits.isdigit() and len(digits) == 6):
        return False
    totp = pyotp.TOTP(_secret(record))
    now = int(time.time())
    for drift in (0, -1, 1):
        step = now // 30 + drift
        if step <= (record.last_used_step or -1):
            continue  # ten kod (lub starszy) był już użyty
        if secrets.compare_digest(totp.at(step * 30), digits):
            record.last_used_step = step
            return True
    return False


def _use_recovery_code(db: Session, user_id: UUID, code: str) -> bool:
    digest = hash_token(_normalize(code))
    match = db.scalars(
        select(MfaRecoveryCode).where(
            MfaRecoveryCode.user_id == user_id,
            MfaRecoveryCode.code_hash == digest,
            MfaRecoveryCode.used_at.is_(None),
        )
    ).first()
    if match is None:
        return False
    match.used_at = utcnow()
    return True


def _check_code(db: Session, user: User, code: str, *, allow_recovery: bool = True) -> str:
    """Sprawdza kod; zwraca „totp” albo „recovery”. Błąd liczy się do limitu prób."""
    key = _fail_key(user.id)
    ratelimit.check(db, key, MAX_FAILURES, FAILURE_WINDOW)
    record = get(db, user.id)
    if record is None or record.enabled_at is None:
        raise Conflict("Weryfikacja dwuetapowa nie jest włączona.", code="mfa.not_enabled")
    if _verify_totp(db, record, code):
        return "totp"
    if allow_recovery and _use_recovery_code(db, user.id, code):
        return "recovery"
    ratelimit.record(db, key)
    audit.security_event(db, "mfa_failed", user_id=user.id)
    db.commit()
    raise Unauthorized("Nieprawidłowy kod.", code="mfa.invalid_code")


def _new_recovery_codes(db: Session, user_id: UUID) -> list[str]:
    db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user_id))
    codes = []
    for _ in range(RECOVERY_CODES):
        raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
        db.add(MfaRecoveryCode(user_id=user_id, code_hash=hash_token(raw)))
    return codes


# --- konfiguracja ----------------------------------------------------------------------


def start_setup(db: Session, user: User, *, password: str) -> SetupData:
    _require_password(user, password)
    if is_enabled(db, user.id):
        raise Conflict("Weryfikacja dwuetapowa jest już włączona.", code="mfa.already_enabled")
    secret = pyotp.random_base32()
    record = get(db, user.id)
    blob = crypto.encrypt(secret, _context(user.id))
    if record is None:
        db.add(UserMfa(user_id=user.id, secret_encrypted=blob))
    else:
        record.secret_encrypted, record.created_at, record.last_used_step = blob, utcnow(), None
    db.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=ISSUER)
    # SVG bez stylów inline (CSP): czarne moduły na białym tle, czytelne w obu motywach.
    qr = qr_svg(uri, scale=5)
    return SetupData(secret=secret, otpauth_uri=uri, qr_svg=qr)


def enable(db: Session, user: User, *, code: str) -> list[str]:
    record = get(db, user.id)
    if record is None:
        raise Conflict("Najpierw rozpocznij konfigurację.", code="mfa.setup_required")
    if record.enabled_at is not None:
        raise Conflict("Weryfikacja dwuetapowa jest już włączona.", code="mfa.already_enabled")
    key = _fail_key(user.id)
    ratelimit.check(db, key, MAX_FAILURES, FAILURE_WINDOW)
    if not _verify_totp(db, record, code):
        ratelimit.record(db, key)
        db.commit()
        raise Unprocessable(
            "Kod się nie zgadza. Sprawdź godzinę w telefonie i wpisz aktualny kod.",
            code="mfa.invalid_code",
        )
    record.enabled_at = utcnow()
    codes = _new_recovery_codes(db, user.id)
    audit.security_event(db, "mfa_enabled", user_id=user.id)
    queue_mail(
        db,
        user.email,
        mail_templates.build(
            "Włączono weryfikację dwuetapową",
            heading="Włączono weryfikację dwuetapową",
            paragraphs=[
                "Na Twoim koncie włączono weryfikację dwuetapową. "
                "Przy logowaniu poprosimy o kod z aplikacji."
            ],
            note="Jeśli to nie Ty, natychmiast zmień hasło i skontaktuj się z nami.",
            settings_link=False,
        ),
    )
    db.commit()
    return codes


def disable(db: Session, user: User, *, password: str, code: str) -> None:
    _require_password(user, password)
    _check_code(db, user, code)
    db.execute(delete(UserMfa).where(UserMfa.user_id == user.id))
    db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id))
    audit.security_event(db, "mfa_disabled", user_id=user.id)
    queue_mail(
        db,
        user.email,
        mail_templates.build(
            "Wyłączono weryfikację dwuetapową",
            heading="Wyłączono weryfikację dwuetapową",
            paragraphs=["Na Twoim koncie wyłączono weryfikację dwuetapową."],
            note="Jeśli to nie Ty, natychmiast zmień hasło i skontaktuj się z nami.",
            settings_link=False,
        ),
    )
    db.commit()


def regenerate_recovery_codes(db: Session, user: User, *, password: str, code: str) -> list[str]:
    _require_password(user, password)
    _check_code(db, user, code, allow_recovery=False)
    codes = _new_recovery_codes(db, user.id)
    audit.security_event(db, "mfa_recovery_regenerated", user_id=user.id)
    db.commit()
    return codes


def remaining_recovery_codes(db: Session, user_id: UUID) -> int:
    return len(
        db.scalars(
            select(MfaRecoveryCode.id).where(
                MfaRecoveryCode.user_id == user_id, MfaRecoveryCode.used_at.is_(None)
            )
        ).all()
    )


# --- logowanie -------------------------------------------------------------------------


def issue_challenge(user_id: UUID) -> MfaChallenge:
    settings = get_settings()
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "typ": "mfa",
        "jti": secrets.token_urlsafe(16),
        "iat": int(now.timestamp()),
        "exp": int((now + CHALLENGE_TTL).timestamp()),
    }
    token = jwt.encode(
        payload, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm
    )
    return MfaChallenge(mfa_token=token, expires_in=int(CHALLENGE_TTL.total_seconds()))


def resolve_challenge(db: Session, mfa_token: str, code: str) -> tuple[User, str]:
    """Token wyzwania + kod → użytkownik (token jednorazowy). Zwraca też rodzaj kodu."""
    settings = get_settings()
    expired = Unauthorized("Logowanie wygasło. Wpisz hasło ponownie.", code="mfa.challenge_expired")
    try:
        payload = jwt.decode(
            mfa_token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "jti"]},
        )
    except jwt.PyJWTError as exc:
        raise expired from exc
    if payload.get("typ") != "mfa":
        raise expired
    user = db.get(User, UUID(payload["sub"]))
    if user is None or user.status in ("deleted", "locked"):
        raise expired
    used_key = ratelimit.key_for("mfa_challenge_used", payload["jti"])
    try:
        ratelimit.check(db, used_key, 1, CHALLENGE_TTL)
    except RateLimited as exc:
        raise expired from exc
    kind = _check_code(db, user, code)
    ratelimit.record(db, used_key)
    if kind == "recovery":
        audit.security_event(db, "mfa_recovery_used", user_id=user.id)
    return user, kind


def reencrypt_secrets(db: Session, *, dry_run: bool) -> dict[str, int]:
    """Rotacja klucza: przeszyfrowanie sekretów TOTP bieżącym kluczem (jak uwagi dietetyczne)."""
    current = crypto.current_version()
    stats = {"encrypted": 0, "old_key": 0, "rotated": 0}
    for user_id, blob in db.execute(select(UserMfa.user_id, UserMfa.secret_encrypted)).all():
        stats["encrypted"] += 1
        if crypto.key_version(blob) == current:
            continue
        stats["old_key"] += 1
        if dry_run:
            continue
        fresh = crypto.encrypt(crypto.decrypt(blob, _context(user_id)), _context(user_id))
        result = db.execute(
            update(UserMfa)
            .where(UserMfa.user_id == user_id, UserMfa.secret_encrypted == blob)
            .values(secret_encrypted=fresh)
        )
        stats["rotated"] += int(getattr(result, "rowcount", 0) or 0)
    db.commit()
    return stats
