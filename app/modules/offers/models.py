from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin

OFFER_STATUSES = ("draft", "needs_review", "approved", "selected", "rejected")
OFFER_SOURCES = ("manual", "ai_extraction", "vendor_structured")
COMPONENT_KINDS = (
    "per_guest",
    "per_child",
    "per_crew",
    "fixed",
    "per_hour",
    "per_unit",
    "percent",
)
CONFIDENCE = ("high", "medium", "low", "unverified")
TERM_TYPES = (
    "deposit",
    "payment_schedule",
    "cancellation",
    "menu",
    "drinks",
    "corkage",
    "overtime",
    "other",
)


class Offer(IdMixin, TimestampMixin, Base):
    """Oferta usługodawcy. Prywatna dla wesela: nie agregujemy ofert między weselami."""

    __tablename__ = "offers"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    vendor_id: Mapped[UUID] = mapped_column(ForeignKey("vendors.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    valid_until: Mapped[date | None] = mapped_column(Date)
    min_guests: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(String(3), default="PLN")
    status: Mapped[str] = mapped_column(String(16), default="approved")
    source: Mapped[str] = mapped_column(String(24), default="manual")
    source_document_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="SET NULL")
    )
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    selected_budget_item_id: Mapped[UUID | None] = mapped_column()
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(f"status IN {OFFER_STATUSES}", name="status"),
        CheckConstraint(f"source IN {OFFER_SOURCES}", name="source"),
        CheckConstraint("min_guests IS NULL OR min_guests >= 0", name="min_guests"),
        Index("ix_offers_wedding_vendor", "wedding_id", "vendor_id"),
    )


class PricingComponent(IdMixin, Base):
    __tablename__ = "pricing_components"

    offer_id: Mapped[UUID] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(16))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    included: Mapped[bool] = mapped_column(Boolean, default=False)
    optional: Mapped[bool] = mapped_column(Boolean, default=False)
    event_kind: Mapped[str | None] = mapped_column(String(16))
    citation: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    confidence: Mapped[str] = mapped_column(String(16), default="high")

    __table_args__ = (
        CheckConstraint(f"kind IN {COMPONENT_KINDS}", name="kind"),
        CheckConstraint(f"confidence IN {CONFIDENCE}", name="confidence"),
        CheckConstraint("amount IS NULL OR amount >= 0", name="amount_non_negative"),
        CheckConstraint("quantity IS NULL OR quantity >= 0", name="quantity_non_negative"),
        CheckConstraint(
            "kind <> 'percent' OR amount IS NULL OR amount <= 100", name="percent_range"
        ),
    )


class OfferTerm(IdMixin, Base):
    """Fakty z oferty/umowy (zadatek, harmonogram płatności, odwołanie…) bez oceny prawnej."""

    __tablename__ = "offer_terms"

    offer_id: Mapped[UUID] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    term_type: Mapped[str] = mapped_column(String(24))
    value: Mapped[dict[str, Any]] = mapped_column(JSONB)
    citation: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    confidence: Mapped[str] = mapped_column(String(16), default="high")

    __table_args__ = (
        CheckConstraint(f"term_type IN {TERM_TYPES}", name="term_type"),
        CheckConstraint(f"confidence IN {CONFIDENCE}", name="confidence"),
    )
