"""Logika kont: rejestracja, logowanie, sesje, hasła, zgody, usuwanie konta."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.core import mail_templates, ratelimit
from app.core.config import get_settings
from app.core.db import utcnow
from app.core.email import queue_mail
from app.core.errors import (
    Conflict,
    Forbidden,
    NotFound,
    RateLimited,
    Unauthorized,
    Unprocessable,
)
from app.core.ids import uuid7
from app.core.security import (
    create_access_token,
    hash_password,
    hash_token,
    needs_rehash,
    new_token,
    password_problems,
    verify_dummy,
    verify_password,
)
from app.modules.audit import service as audit
from app.modules.identity import mfa
from app.modules.identity.models import (
    AuthSession,
    Consent,
    MfaRecoveryCode,
    OneTimeToken,
    User,
    UserMfa,
)

ACTIVE_STATUSES = ("active", "pending_deletion")


@dataclass(frozen=True)
class Principal:
    user: User
    session_id: UUID
    family_id: UUID  # rodzina sesji = jedno urządzenie/logowanie


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    expires_in: int


def _ensure_password_ok(password: str, email: str) -> None:
    problems = password_problems(password, email)
    if problems:
        raise Unprocessable(
            "Hasło nie spełnia wymagań.",
            code="auth.weak_password",
            errors=[
                {"loc": ["body", "password"], "msg": p, "type": "weak_password"} for p in problems
            ],
        )


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalars(select(User).where(User.email == email)).first()


def _issue_one_time_token(db: Session, user: User, purpose: str, ttl: timedelta) -> str:
    token, token_hash = new_token()
    db.add(
        OneTimeToken(
            user_id=user.id, purpose=purpose, token_hash=token_hash, expires_at=utcnow() + ttl
        )
    )
    return token


def _consume_one_time_token(db: Session, token: str, purpose: str) -> OneTimeToken:
    ott = db.scalars(
        select(OneTimeToken)
        .where(OneTimeToken.token_hash == hash_token(token), OneTimeToken.purpose == purpose)
        .with_for_update()
    ).first()
    if ott is None or ott.used_at is not None or ott.expires_at <= utcnow():
        raise Unprocessable("Link jest nieprawidłowy lub wygasł.", code="auth.invalid_token")
    ott.used_at = utcnow()
    return ott


def _queue_verification_email(db: Session, user: User) -> None:
    settings = get_settings()
    token = _issue_one_time_token(
        db, user, "verify_email", timedelta(hours=settings.email_verification_ttl_hours)
    )
    queue_mail(
        db,
        user.email,
        mail_templates.build(
            "Potwierdź adres e-mail",
            heading="Potwierdź adres e-mail",
            paragraphs=[
                "Cześć! Potwierdź adres e-mail, żeby dokończyć zakładanie konta w Nasz dzień."
            ],
            action=("Potwierdź adres", f"{settings.public_app_url}/potwierdz-email?token={token}"),
            note=f"Link jest ważny {settings.email_verification_ttl_hours} h. "
            "Jeśli to nie Ty, zignoruj tę wiadomość.",
            settings_link=False,
        ),
    )


# --- rejestracja i weryfikacja -------------------------------------------------


def register(db: Session, *, email: str, password: str, display_name: str | None, ip: str) -> None:
    """Zawsze kończy się tak samo dla klienta (bez ujawniania, czy konto istnieje)."""
    settings = get_settings()
    ratelimit.hit(db, ratelimit.key_for("register:ip", ip), 10, timedelta(hours=1))
    _ensure_password_ok(password, email)

    existing = get_user_by_email(db, email)
    if existing is not None:
        if existing.status != "deleted":
            queue_mail(
                db,
                existing.email,
                mail_templates.build(
                    "Próba rejestracji na Twój adres",
                    heading="Ktoś próbował założyć konto na Twój adres",
                    paragraphs=[
                        "Ktoś (może Ty) próbował założyć konto na ten adres, "
                        "ale konto już istnieje."
                    ],
                    action=("Zresetuj hasło", f"{settings.public_app_url}/zapomniane-haslo"),
                    note="Jeśli to nie Ty, zignoruj tę wiadomość — konto jest bezpieczne.",
                    settings_link=False,
                ),
            )
        db.commit()
        return

    user = User(email=email, password_hash=hash_password(password), display_name=display_name)
    db.add(user)
    db.flush()
    db.add(Consent(user_id=user.id, type="terms", document_version=settings.terms_version))
    db.add(Consent(user_id=user.id, type="privacy", document_version=settings.privacy_version))
    _queue_verification_email(db, user)
    audit.record(
        db,
        actor_type="user",
        actor_id=user.id,
        entity_type="user",
        entity_id=user.id,
        action="register",
    )
    db.commit()


def verify_email(db: Session, *, token: str, ip: str) -> None:
    ratelimit.hit(db, ratelimit.key_for("token:ip", ip), 30, timedelta(minutes=15))
    db.commit()
    ott = _consume_one_time_token(db, token, "verify_email")
    user = db.get_one(User, ott.user_id)
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()
        audit.record(
            db,
            actor_type="user",
            actor_id=user.id,
            entity_type="user",
            entity_id=user.id,
            action="verify_email",
        )
    db.commit()


def resend_verification(db: Session, principal: Principal) -> None:
    user = principal.user
    ratelimit.hit(db, ratelimit.key_for("verify_resend", str(user.id)), 3, timedelta(hours=1))
    if user.email_verified_at is None:
        _queue_verification_email(db, user)
    db.commit()


# --- logowanie i sesje ---------------------------------------------------------


def _create_session(
    db: Session, user: User, *, family_id: UUID | None, user_agent: str | None, ip: str | None
) -> tuple[AuthSession, str]:
    token, token_hash = new_token()
    session = AuthSession(
        id=uuid7(),
        user_id=user.id,
        family_id=family_id or uuid7(),
        refresh_token_hash=token_hash,
        expires_at=utcnow() + timedelta(days=get_settings().refresh_token_ttl_days),
        user_agent=user_agent,
        ip_prefix=ip,
    )
    db.add(session)
    return session, token


def _tokens_for(session: AuthSession, refresh_token: str) -> IssuedTokens:
    access, expires_in = create_access_token(session.user_id, session.id)
    return IssuedTokens(access_token=access, refresh_token=refresh_token, expires_in=expires_in)


def login(
    db: Session, *, email: str, password: str, ip: str, user_agent: str | None
) -> "IssuedTokens | mfa.MfaChallenge":
    settings = get_settings()
    window = timedelta(minutes=settings.login_window_minutes)
    email_key = ratelimit.key_for("login_fail:email", email)
    ip_key = ratelimit.key_for("login_fail:ip", ip)
    ratelimit.check(db, email_key, settings.login_max_failures, window)
    ratelimit.check(db, ip_key, settings.login_max_failures * 10, window)

    user = get_user_by_email(db, email)
    if user is None:
        verify_dummy(password)
    valid = (
        user is not None
        and user.status != "deleted"
        and verify_password(user.password_hash, password)
    )
    if not valid or user is None:
        ratelimit.record(db, email_key)
        ratelimit.record(db, ip_key)
        audit.security_event(db, "login_failed", user_id=user.id if user else None, ip_prefix=ip)
        db.commit()
        raise Unauthorized("Nieprawidłowy e-mail lub hasło.", code="auth.invalid_credentials")
    if user.status == "locked":
        raise Forbidden("Konto jest zablokowane.", code="account.locked")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    if mfa.is_enabled(db, user.id):
        # Hasło poprawne, ale sesja dopiero po kodzie z aplikacji (drugi krok).
        audit.security_event(db, "login_password_ok_mfa_pending", user_id=user.id, ip_prefix=ip)
        db.commit()
        return mfa.issue_challenge(user.id)
    session, refresh = _create_session(db, user, family_id=None, user_agent=user_agent, ip=ip)
    audit.security_event(db, "login_succeeded", user_id=user.id, ip_prefix=ip)
    db.commit()
    return _tokens_for(session, refresh)


def login_mfa(
    db: Session, *, mfa_token: str, code: str, ip: str, user_agent: str | None
) -> IssuedTokens:
    """Drugi krok logowania: token wyzwania z kroku hasła + kod TOTP lub zapasowy."""
    ratelimit.hit(db, ratelimit.key_for("mfa_login:ip", ip), 50, timedelta(minutes=15))
    user, _kind = mfa.resolve_challenge(db, mfa_token, code)
    session, refresh = _create_session(db, user, family_id=None, user_agent=user_agent, ip=ip)
    audit.security_event(db, "login_succeeded", user_id=user.id, ip_prefix=ip)
    db.commit()
    return _tokens_for(session, refresh)


def refresh(db: Session, *, refresh_token: str, ip: str, user_agent: str | None) -> IssuedTokens:
    session = db.scalars(
        select(AuthSession)
        .where(AuthSession.refresh_token_hash == hash_token(refresh_token))
        .with_for_update()
    ).first()
    invalid = Unauthorized("Sesja wygasła. Zaloguj się ponownie.", code="auth.invalid_refresh")
    if session is None:
        raise invalid
    now = utcnow()
    if session.revoked_at is not None:
        if session.revoked_reason == "rotated" and _concurrent_retry(db, session, now):
            # Równoległe ponowienie z tego samego urządzenia: wydajemy kolejnego następcę
            # w tej samej rodzinie, bez unieważniania pierwszego (oba klienty działają dalej).
            user = db.get_one(User, session.user_id)
            if user.status not in ACTIVE_STATUSES:
                raise invalid
            sibling, sibling_refresh = _create_session(
                db, user, family_id=session.family_id, user_agent=user_agent, ip=ip
            )
            audit.security_event(
                db,
                "refresh_token_retry",
                user_id=session.user_id,
                ip_prefix=ip,
                details={"family_id": str(session.family_id)},
            )
            db.commit()
            return _tokens_for(sibling, sibling_refresh)
        if session.revoked_reason == "rotated":
            # Ponowne użycie zrotowanego tokena = możliwa kradzież: zamykamy całą rodzinę.
            _revoke_where(db, AuthSession.family_id == session.family_id, "reuse_detected")
            audit.security_event(
                db,
                "refresh_token_reuse",
                user_id=session.user_id,
                ip_prefix=ip,
                details={"family_id": str(session.family_id)},
            )
            db.commit()
        raise invalid
    if session.expires_at <= now:
        raise invalid
    user = db.get_one(User, session.user_id)
    if user.status not in ACTIVE_STATUSES:
        raise invalid

    new_session, new_refresh = _create_session(
        db, user, family_id=session.family_id, user_agent=user_agent, ip=ip
    )
    session.revoked_at = now
    session.revoked_reason = "rotated"
    session.replaced_by_id = new_session.id
    db.commit()
    return _tokens_for(new_session, new_refresh)


def _concurrent_retry(db: Session, session: AuthSession, now: datetime) -> bool:
    """Zrotowany token użyty ponownie w oknie tolerancji, a jego następca jest nieużyty."""
    grace = timedelta(seconds=get_settings().refresh_reuse_grace_seconds)
    if session.revoked_at is None or now - session.revoked_at > grace:
        return False
    successor = db.get(AuthSession, session.replaced_by_id) if session.replaced_by_id else None
    return successor is not None and successor.revoked_at is None and successor.expires_at > now


def _revoke_where(db: Session, condition: Any, reason: str) -> None:
    db.execute(
        update(AuthSession)
        .where(condition, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utcnow(), revoked_reason=reason)
    )


def authenticate(db: Session, user_id: UUID, session_id: UUID) -> Principal:
    """Weryfikacja sesji przy każdym żądaniu: wylogowanie działa natychmiast."""
    inactive = Unauthorized("Sesja jest nieaktywna.", code="auth.session_inactive")
    session = db.get(AuthSession, session_id)
    if session is None or session.user_id != user_id:
        raise inactive
    if session.revoked_at is not None:
        # Access token wydany przed rotacją refresh tokena jest ważny (max 15 min),
        # ale tylko dopóki rodzina sesji ma aktywnego następcę (np. brak wylogowania).
        if session.revoked_reason != "rotated" or not _family_active(db, session.family_id):
            raise inactive
    elif session.expires_at <= utcnow():
        raise inactive
    user = db.get(User, user_id)
    if user is None or user.status not in ACTIVE_STATUSES:
        raise Unauthorized("Konto jest nieaktywne.", code="auth.account_inactive")
    return Principal(user=user, session_id=session.id, family_id=session.family_id)


def _family_active(db: Session, family_id: UUID) -> bool:
    return (
        db.scalars(
            select(AuthSession.id).where(
                AuthSession.family_id == family_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > utcnow(),
            )
        ).first()
        is not None
    )


def logout(db: Session, principal: Principal) -> None:
    _revoke_where(db, AuthSession.family_id == principal.family_id, "logout")
    db.commit()


def list_sessions(db: Session, principal: Principal) -> list[AuthSession]:
    return list(
        db.scalars(
            select(AuthSession)
            .where(
                AuthSession.user_id == principal.user.id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > utcnow(),
            )
            .order_by(AuthSession.created_at.desc())
        )
    )


def revoke_session(db: Session, principal: Principal, session_id: UUID) -> None:
    session = db.get(AuthSession, session_id)
    if session is None or session.user_id != principal.user.id or session.revoked_at is not None:
        raise NotFound(code="session.not_found")
    _revoke_where(db, AuthSession.family_id == session.family_id, "user_revoked")
    db.commit()


# --- hasła -----------------------------------------------------------------------


def forgot_password(db: Session, *, email: str, ip: str) -> None:
    settings = get_settings()
    ratelimit.hit(db, ratelimit.key_for("forgot:ip", ip), 10, timedelta(hours=1))
    email_key = ratelimit.key_for("forgot:email", email)
    try:
        ratelimit.check(db, email_key, 3, timedelta(hours=1))
    except RateLimited:
        # Limit per e-mail przekroczony: cicho nic nie wysyłamy (bez ujawniania konta).
        db.commit()
        return
    ratelimit.record(db, email_key)
    user = get_user_by_email(db, email)
    if user is not None and user.status in ACTIVE_STATUSES:
        token = _issue_one_time_token(
            db, user, "reset_password", timedelta(minutes=settings.password_reset_ttl_minutes)
        )
        queue_mail(
            db,
            user.email,
            mail_templates.build(
                "Reset hasła",
                heading="Ustaw nowe hasło",
                paragraphs=["Otrzymaliśmy prośbę o reset hasła do Twojego konta."],
                action=("Ustaw nowe hasło", f"{settings.public_app_url}/nowe-haslo?token={token}"),
                note=f"Link jest ważny {settings.password_reset_ttl_minutes} min. "
                "Jeśli to nie Ty, zignoruj tę wiadomość. Hasło się nie zmieni.",
                settings_link=False,
            ),
        )
        audit.security_event(db, "password_reset_requested", user_id=user.id, ip_prefix=ip)
    db.commit()


def reset_password(db: Session, *, token: str, new_password: str, ip: str) -> None:
    ratelimit.hit(db, ratelimit.key_for("token:ip", ip), 30, timedelta(minutes=15))
    db.commit()
    ott = _consume_one_time_token(db, token, "reset_password")
    user = db.get_one(User, ott.user_id)
    _ensure_password_ok(new_password, user.email)
    user.password_hash = hash_password(new_password)
    # Unieważnij pozostałe linki resetu i wszystkie sesje.
    db.execute(
        update(OneTimeToken)
        .where(
            OneTimeToken.user_id == user.id,
            OneTimeToken.purpose == "reset_password",
            OneTimeToken.used_at.is_(None),
        )
        .values(used_at=utcnow())
    )
    _revoke_where(db, AuthSession.user_id == user.id, "password_reset")
    audit.security_event(db, "password_reset", user_id=user.id, ip_prefix=ip)
    db.commit()


def change_password(
    db: Session, principal: Principal, *, current_password: str, new_password: str
) -> None:
    user = principal.user
    if not verify_password(user.password_hash, current_password):
        raise Unauthorized("Nieprawidłowe obecne hasło.", code="auth.invalid_credentials")
    _ensure_password_ok(new_password, user.email)
    user.password_hash = hash_password(new_password)
    _revoke_where(
        db,
        (AuthSession.user_id == user.id) & (AuthSession.family_id != principal.family_id),
        "password_changed",
    )
    audit.security_event(db, "password_changed", user_id=user.id)
    db.commit()


# --- profil i zgody ----------------------------------------------------------------


def update_profile(db: Session, principal: Principal, changes: dict[str, Any]) -> User:
    user = principal.user
    before = {k: getattr(user, k) for k in changes}
    for key, value in changes.items():
        if key == "locale" and value is None:
            continue
        setattr(user, key, value)
    audit.record(
        db,
        actor_type="user",
        actor_id=user.id,
        entity_type="user",
        entity_id=user.id,
        action="update_profile",
        changes=audit.diff(before, changes),
    )
    db.commit()
    return user


def list_consents(db: Session, principal: Principal) -> list[Consent]:
    return list(
        db.scalars(
            select(Consent).where(Consent.user_id == principal.user.id).order_by(Consent.granted_at)
        )
    )


def _active_consent(db: Session, user_id: UUID, consent_type: str) -> Consent | None:
    return db.scalars(
        select(Consent).where(
            Consent.user_id == user_id,
            Consent.type == consent_type,
            Consent.withdrawn_at.is_(None),
        )
    ).first()


def grant_consent(db: Session, principal: Principal, consent_type: str) -> Consent:
    existing = _active_consent(db, principal.user.id, consent_type)
    if existing is not None:
        return existing
    consent = Consent(user_id=principal.user.id, type=consent_type)
    db.add(consent)
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="consent",
        entity_id=consent_type,
        action="grant",
    )
    db.commit()
    return consent


def withdraw_consent(db: Session, principal: Principal, consent_type: str) -> None:
    consent = _active_consent(db, principal.user.id, consent_type)
    if consent is None:
        raise NotFound(code="consent.not_found")
    consent.withdrawn_at = utcnow()
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="consent",
        entity_id=consent_type,
        action="withdraw",
    )
    db.commit()


def has_active_consent(db: Session, user_id: UUID, consent_type: str) -> bool:
    return _active_consent(db, user_id, consent_type) is not None


# --- eksport i usunięcie konta (RODO) -------------------------------------------


def deletion_scheduled_at(user: User) -> datetime | None:
    if user.deletion_requested_at is None:
        return None
    return user.deletion_requested_at + timedelta(days=get_settings().account_deletion_grace_days)


def export_account(db: Session, principal: Principal) -> dict[str, Any]:
    from app.modules.workspace import service as workspace  # import lokalny: brak cykli

    user = principal.user
    return {
        "exported_at": utcnow().isoformat(),
        "account": {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "locale": user.locale,
            "email_verified_at": _iso(user.email_verified_at),
            "mfa_enabled": mfa.is_enabled(db, user.id),
            "created_at": _iso(user.created_at),
        },
        "consents": [
            {
                "type": c.type,
                "document_version": c.document_version,
                "granted_at": _iso(c.granted_at),
                "withdrawn_at": _iso(c.withdrawn_at),
            }
            for c in list_consents(db, principal)
        ],
        "active_sessions": [
            {"created_at": _iso(s.created_at), "user_agent": s.user_agent, "ip_prefix": s.ip_prefix}
            for s in list_sessions(db, principal)
        ],
        "weddings": workspace.export_for_user(db, user.id),
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def request_account_deletion(db: Session, principal: Principal, *, password: str) -> datetime:
    from app.modules.workspace import service as workspace

    user = principal.user
    if not verify_password(user.password_hash, password):
        raise Unauthorized("Nieprawidłowe hasło.", code="auth.invalid_credentials")
    if user.status == "pending_deletion":
        raise Conflict("Usunięcie konta jest już zaplanowane.", code="account.deletion_pending")
    workspace.ensure_user_can_be_deleted(db, user.id)
    user.status = "pending_deletion"
    user.deletion_requested_at = utcnow()
    _revoke_where(
        db,
        (AuthSession.user_id == user.id) & (AuthSession.family_id != principal.family_id),
        "account_deletion",
    )
    scheduled = user.deletion_requested_at + timedelta(
        days=get_settings().account_deletion_grace_days
    )
    queue_mail(
        db,
        user.email,
        mail_templates.build(
            "Zaplanowano usunięcie konta",
            heading="Zaplanowano usunięcie konta",
            paragraphs=[
                f"Twoje konto zostanie trwale usunięte {scheduled:%d.%m.%Y}.",
                "Aby anulować, zaloguj się i anuluj usunięcie w ustawieniach konta.",
            ],
            action=("Otwórz ustawienia konta", f"{get_settings().public_app_url}/ustawienia"),
            settings_link=False,
        ),
    )
    audit.security_event(db, "account_deletion_requested", user_id=user.id)
    db.commit()
    return scheduled


def cancel_account_deletion(db: Session, principal: Principal) -> None:
    user = principal.user
    if user.status != "pending_deletion":
        raise Conflict("Usunięcie konta nie jest zaplanowane.", code="account.deletion_not_pending")
    user.status = "active"
    user.deletion_requested_at = None
    audit.security_event(db, "account_deletion_cancelled", user_id=user.id)
    db.commit()


def anonymize_user(db: Session, user: User) -> None:
    """Trwała anonimizacja jednego konta (bez commit): członkostwa, sesje, MFA, dane osobowe."""
    from app.modules.workspace import service as workspace

    workspace.remove_user_everywhere(db, user.id)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.execute(delete(OneTimeToken).where(OneTimeToken.user_id == user.id))
    db.execute(delete(UserMfa).where(UserMfa.user_id == user.id))
    db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id))
    user.email = f"deleted+{user.id}@invalid.local"
    user.display_name = None
    # „!” = brak hasła: logowanie niemożliwe.
    user.password_hash = "!"  # noqa: S105  # nosec B105
    user.status = "deleted"
    user.email_verified_at = None
    audit.record(
        db,
        actor_type="system",
        actor_id=None,
        entity_type="user",
        entity_id=user.id,
        action="anonymize",
    )


def anonymize_due_accounts(db: Session) -> int:
    """Zadanie okresowe: trwała anonimizacja kont po okresie karencji."""
    cutoff = utcnow() - timedelta(days=get_settings().account_deletion_grace_days)
    users = db.scalars(
        select(User).where(User.status == "pending_deletion", User.deletion_requested_at <= cutoff)
    ).all()
    for user in users:
        anonymize_user(db, user)
    db.commit()
    return len(users)


def purge_expired_credentials(db: Session) -> int:
    now = utcnow()
    removed = db.execute(
        delete(AuthSession).where(
            or_(
                AuthSession.expires_at < now - timedelta(days=30),
                AuthSession.revoked_at < now - timedelta(days=30),
            )
        )
    )
    removed_tokens = db.execute(
        delete(OneTimeToken).where(OneTimeToken.expires_at < now - timedelta(days=7))
    )
    db.commit()
    return int(getattr(removed, "rowcount", 0) or 0) + int(
        getattr(removed_tokens, "rowcount", 0) or 0
    )
