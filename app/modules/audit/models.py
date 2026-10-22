from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Identity, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utcnow

ACTOR_TYPES = ("user", "system", "guest", "admin")


class AuditLog(Base):
    """Dziennik zmian, tylko do dopisywania. Bez danych wrażliwych w `changes`."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor_type: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[UUID | None] = mapped_column()
    # Celowo bez FK: wpisy przeżywają usunięcie wesela/konta.
    wedding_id: Mapped[UUID | None] = mapped_column()
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    request_id: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        CheckConstraint(f"actor_type IN {ACTOR_TYPES}", name="actor_type"),
        Index("ix_audit_log_wedding_occurred", "wedding_id", "occurred_at"),
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
    )


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    type: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[UUID | None] = mapped_column()
    ip_prefix: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    __table_args__ = (Index("ix_security_events_user_occurred", "user_id", "occurred_at"),)
