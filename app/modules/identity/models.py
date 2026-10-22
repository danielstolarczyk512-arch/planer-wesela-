from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow

GLOBAL_ROLES = ("user", "moderator", "admin")
USER_STATUSES = ("active", "locked", "pending_deletion", "deleted")
TOKEN_PURPOSES = ("verify_email", "reset_password")
CONSENT_TYPES = ("terms", "privacy", "marketing", "ai_external_processing")
USER_MANAGED_CONSENTS = ("marketing", "ai_external_processing")


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(100))
    locale: Mapped[str] = mapped_column(String(10), default="pl-PL")
    global_role: Mapped[str] = mapped_column(String(16), default="user")
    status: Mapped[str] = mapped_column(String(24), default="active")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"global_role IN {GLOBAL_ROLES}", name="global_role"),
        CheckConstraint(f"status IN {USER_STATUSES}", name="status"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None


class AuthSession(IdMixin, Base):
    """Sesja = rodzina rotowanych refresh tokenów. W bazie tylko hash tokena."""

    __tablename__ = "sessions"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    family_id: Mapped[UUID] = mapped_column()
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(32))
    replaced_by_id: Mapped[UUID | None] = mapped_column()
    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip_prefix: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        Index("ix_sessions_user_revoked", "user_id", "revoked_at"),
        Index("ix_sessions_family", "family_id"),
    )


class OneTimeToken(IdMixin, Base):
    __tablename__ = "one_time_tokens"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(32))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint(f"purpose IN {TOKEN_PURPOSES}", name="purpose"),)


class Consent(IdMixin, Base):
    """Historia zgód: tylko dopisywanie i oznaczanie wycofania (dowód zgody)."""

    __tablename__ = "consents"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(32))
    document_version: Mapped[str | None] = mapped_column(String(32))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"type IN {CONSENT_TYPES}", name="type"),
        Index("ix_consents_user_type", "user_id", "type"),
    )


class UserMfa(Base):
    """Weryfikacja dwuetapowa (TOTP). Sekret zaszyfrowany (AES-GCM, kontekst: id użytkownika).

    `enabled_at` puste = konfiguracja rozpoczęta, ale niepotwierdzona kodem z aplikacji.
    `last_used_step` blokuje ponowne użycie tego samego kodu (okno 30 s).
    """

    __tablename__ = "user_mfa"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    secret_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_step: Mapped[int | None] = mapped_column(BigInteger)


class MfaRecoveryCode(IdMixin, Base):
    """Jednorazowe kody zapasowe; w bazie tylko skrót SHA-256."""

    __tablename__ = "mfa_recovery_codes"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
