from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, utcnow

RUN_STATUSES = ("queued", "running", "succeeded", "failed", "blocked")


class AiRun(IdMixin, Base):
    """Ślad audytowy każdego użycia AI: model, wersja promptu, wejście (hash), wynik, koszt."""

    __tablename__ = "ai_runs"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    task_type: Mapped[str] = mapped_column(String(32))
    document_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="SET NULL")
    )
    vendor_id: Mapped[UUID | None] = mapped_column(ForeignKey("vendors.id", ondelete="SET NULL"))
    requested_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(100))
    model_license: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(64))
    prompt_fingerprint: Mapped[str] = mapped_column(String(16))
    input_hash: Mapped[str | None] = mapped_column(String(64))
    external_processing: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    validation: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(String(300))
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    offer_id: Mapped[UUID | None] = mapped_column(ForeignKey("offers.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"status IN {RUN_STATUSES}", name="status"),
        Index("ix_ai_runs_wedding_created", "wedding_id", "created_at"),
        Index("ix_ai_runs_cache", "wedding_id", "input_hash", "prompt_version", "model"),
    )
