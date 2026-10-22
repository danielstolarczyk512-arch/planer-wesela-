from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow

DOCUMENT_KINDS = ("offer", "contract", "invoice", "payment_proof", "other")
TEXT_STATUSES = ("pending", "processing", "done", "failed")
# not_scanned: skaner wyłączony (dev/testy) albo plik sprzed wdrożenia skanera.
SCAN_STATUSES = ("not_scanned", "pending", "clean", "infected")
DOWNLOADABLE = ("not_scanned", "clean")


class Document(IdMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16), default="other")
    title: Mapped[str] = mapped_column(String(200))
    vendor_id: Mapped[UUID | None] = mapped_column(ForeignKey("vendors.id", ondelete="SET NULL"))
    current_version_id: Mapped[UUID | None] = mapped_column()
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(f"kind IN {DOCUMENT_KINDS}", name="kind"),
        Index("ix_documents_wedding_kind", "wedding_id", "kind"),
    )


class DocumentVersion(IdMixin, Base):
    """Wersja pliku. Treść umów może zawierać dane osobowe: dostęp tylko członków wesela."""

    __tablename__ = "document_versions"

    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    version_no: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    original_filename: Mapped[str] = mapped_column(String(150))
    uploaded_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    text_status: Mapped[str] = mapped_column(String(16), default="pending")
    extracted_text: Mapped[str | None] = mapped_column(Text)
    page_offsets: Mapped[list[Any] | None] = mapped_column(JSONB)
    page_count: Mapped[int | None] = mapped_column(Integer)
    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False)
    text_error: Mapped[str | None] = mapped_column(String(300))
    scan_status: Mapped[str] = mapped_column(String(16), default="not_scanned")
    scan_signature: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        CheckConstraint(f"scan_status IN {SCAN_STATUSES}", name="scan_status"),
        UniqueConstraint("document_id", "version_no", name="uq_document_versions_doc_no"),
        CheckConstraint(f"text_status IN {TEXT_STATUSES}", name="text_status"),
        Index("ix_document_versions_wedding_sha", "wedding_id", "sha256"),
        Index("ix_document_versions_document", "document_id"),
    )
