"""Prywatne dane doboru usługodawców dla wesela: preferencje, rozmowy, kandydaci, zlecenia badań.

Wszystkie tabele mają `wedding_id` i kasują się razem z weselem (ON DELETE CASCADE); wspólny
katalog (`catalog_*`) pozostaje niezależny (ADR-0008).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow
from app.modules.vendors.models import CATEGORIES

MESSAGE_ROLES = ("user", "assistant", "notice")
MESSAGE_STATES = ("done", "pending", "failed")
CANDIDATE_STATES = ("saved", "rejected")
REQUEST_STATES = ("queued", "running", "done", "failed")


class VendorPreferences(TimestampMixin, Base):
    """Czego para szuka w danej kategorii. Budżet to ograniczenie doboru, nie dane dla firmy."""

    __tablename__ = "vendor_preferences"

    wedding_id: Mapped[UUID] = mapped_column(
        ForeignKey("weddings.id", ondelete="CASCADE"), primary_key=True
    )
    category: Mapped[str] = mapped_column(String(32), primary_key=True)
    scope_terms: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list)
    style_tags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    budget_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    notes: Mapped[str | None] = mapped_column(String(1000))
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(f"category IN {tuple(CATEGORIES)}", name="category"),
        CheckConstraint("budget_max IS NULL OR budget_max >= 0", name="budget_non_negative"),
    )


class Conversation(IdMixin, Base):
    __tablename__ = "concierge_conversations"

    wedding_id: Mapped[UUID] = mapped_column(
        ForeignKey("weddings.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    title: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Message(IdMixin, Base):
    __tablename__ = "concierge_messages"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("concierge_conversations.id", ondelete="CASCADE"), index=True
    )
    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(12))
    content: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(10), default="done")
    # Co asystent zrobił (narzędzia) — widoczne dla pary; karty wyników z dowodami.
    actions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    cards: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    author_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        CheckConstraint(f"role IN {MESSAGE_ROLES}", name="role"),
        CheckConstraint(f"state IN {MESSAGE_STATES}", name="state"),
        Index("ix_concierge_messages_conv_created", "conversation_id", "created_at"),
    )


class Candidate(IdMixin, TimestampMixin, Base):
    """Firma z katalogu zapisana przez parę (albo odrzucona) — ich lista, nie katalog."""

    __tablename__ = "concierge_candidates"

    wedding_id: Mapped[UUID] = mapped_column(
        ForeignKey("weddings.id", ondelete="CASCADE"), index=True
    )
    catalog_vendor_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_vendors.id", ondelete="CASCADE")
    )
    category: Mapped[str] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(10), default="saved")
    note: Mapped[str | None] = mapped_column(String(500))
    # Uzasadnienie z chwili zapisu (zamrożone razem z dowodami, żeby było czytelne później).
    reasoning: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Powiązanie z prywatnym usługodawcą po wybraniu „Dodaj do moich usługodawców”.
    vendor_id: Mapped[UUID | None] = mapped_column(ForeignKey("vendors.id", ondelete="SET NULL"))
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    __table_args__ = (
        UniqueConstraint("wedding_id", "catalog_vendor_id", name="uq_candidate_vendor"),
        CheckConstraint(f"state IN {CANDIDATE_STATES}", name="state"),
    )


class DiscoveryRequest(IdMixin, TimestampMixin, Base):
    """Prośba pary o dodatkowy research. Do badacza trafia wyłącznie kategoria i region."""

    __tablename__ = "discovery_requests"

    wedding_id: Mapped[UUID] = mapped_column(
        ForeignKey("weddings.id", ondelete="CASCADE"), index=True
    )
    requested_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    category: Mapped[str] = mapped_column(String(32))
    region: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(10), default="queued")
    # Wynik bez danych osobowych: ile źródeł odświeżono, czy wyszukiwanie nowych jest dostępne.
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"state IN {REQUEST_STATES}", name="state"),
        CheckConstraint(f"category IN {tuple(CATEGORIES)}", name="category"),
    )
