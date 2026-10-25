"""Prywatne zapytania do firm: wersjonowana treść, zatwierdzenie pary, dostarczenie, odpowiedzi.

Rewizja treści jest niezmienna. Zgoda (`approved_at`) dotyczy dokładnie jednej rewizji i jej hasha
(temat + treść + adresat); każda zmiana tworzy nową rewizję bez zgody. Dostarczenie
(`MailDelivery`) ma unikalny klucz na rewizję, więc podwójne kliknięcie nie wyśle dwóch wiadomości.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow

DELIVERY_STATES = ("queued", "sending", "accepted", "failed", "uncertain")
RESPONSE_SOURCES = ("manual", "email")  # email: odbiór poczty (etap 4)
RESPONSE_STATES = ("assigned", "unassigned")


class Inquiry(IdMixin, TimestampMixin, Base):
    """Zapytanie do jednej firmy (jeden adresat). Zbiorcze „3 zapytania” to trzy rekordy."""

    __tablename__ = "inquiries"

    wedding_id: Mapped[UUID] = mapped_column(
        ForeignKey("weddings.id", ondelete="CASCADE"), index=True
    )
    vendor_id: Mapped[UUID] = mapped_column(ForeignKey("vendors.id", ondelete="CASCADE"))
    catalog_vendor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("catalog_vendors.id", ondelete="SET NULL")
    )
    category: Mapped[str] = mapped_column(String(32))
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    latest_revision_no: Mapped[int] = mapped_column(Integer, default=1)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InquiryRevision(IdMixin, Base):
    __tablename__ = "inquiry_revisions"

    inquiry_id: Mapped[UUID] = mapped_column(
        ForeignKey("inquiries.id", ondelete="CASCADE"), index=True
    )
    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    to_email: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    author_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("inquiry_id", "number", name="uq_revision_number"),)


class MailDelivery(IdMixin, TimestampMixin, Base):
    """Jedno dostarczenie jednej zatwierdzonej rewizji (outbox)."""

    __tablename__ = "mail_deliveries"

    revision_id: Mapped[UUID] = mapped_column(
        ForeignKey("inquiry_revisions.id", ondelete="CASCADE"), unique=True
    )
    inquiry_id: Mapped[UUID] = mapped_column(
        ForeignKey("inquiries.id", ondelete="CASCADE"), index=True
    )
    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    to_email: Mapped[str] = mapped_column(String(320))
    message_id: Mapped[str] = mapped_column(String(255), unique=True)
    state: Mapped[str] = mapped_column(String(12), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(200))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"state IN {DELIVERY_STATES}", name="state"),
        Index("ix_mail_deliveries_wedding_created", "wedding_id", "created_at"),
    )


class IncomingMessage(IdMixin, Base):
    """Odpowiedź firmy. MVP: wklejona ręcznie przez parę (odbiór poczty to etap 4)."""

    __tablename__ = "incoming_messages"

    wedding_id: Mapped[UUID] = mapped_column(
        ForeignKey("weddings.id", ondelete="CASCADE"), index=True
    )
    inquiry_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("inquiries.id", ondelete="SET NULL"), index=True
    )
    source: Mapped[str] = mapped_column(String(12), default="manual")
    status: Mapped[str] = mapped_column(String(12), default="assigned")
    subject: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    version_id: Mapped[UUID | None] = mapped_column()
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        CheckConstraint(f"source IN {RESPONSE_SOURCES}", name="source"),
        CheckConstraint(f"status IN {RESPONSE_STATES}", name="status"),
    )
