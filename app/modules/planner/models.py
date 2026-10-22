from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow

TASK_STATUSES = ("todo", "in_progress", "done", "skipped")
DUE_MODES = ("relative", "absolute", "none")
TASK_SOURCES = ("template", "user", "ai")


class Task(IdMixin, TimestampMixin, Base):
    __tablename__ = "tasks"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    parent_task_id: Mapped[UUID | None] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    template_code: Mapped[str | None] = mapped_column(String(64))
    template_version: Mapped[str | None] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32), default="inne")
    priority: Mapped[int] = mapped_column(Integer, default=2)
    status: Mapped[str] = mapped_column(String(16), default="todo")
    due_mode: Mapped[str] = mapped_column(String(16), default="none")
    offset_days: Mapped[int | None] = mapped_column(Integer)
    due_date: Mapped[date | None] = mapped_column(Date)
    due_manually_set: Mapped[bool] = mapped_column(Boolean, default=False)
    assignee_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    vendor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vendors.id", ondelete="SET NULL"), index=True
    )
    # Pomocnik bez konta (np. „Tata — kierowcy”): widzi to zadanie na swoim linku.
    helper_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("helpers.id", ondelete="SET NULL"), index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(16), default="user")
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(f"status IN {TASK_STATUSES}", name="status"),
        CheckConstraint(f"due_mode IN {DUE_MODES}", name="due_mode"),
        CheckConstraint(f"source IN {TASK_SOURCES}", name="source"),
        CheckConstraint("priority BETWEEN 1 AND 4", name="priority_range"),
        CheckConstraint(
            "due_mode <> 'relative' OR offset_days IS NOT NULL", name="relative_has_offset"
        ),
        CheckConstraint("due_mode <> 'absolute' OR due_date IS NOT NULL", name="absolute_has_date"),
        Index("ix_tasks_wedding_status_due", "wedding_id", "status", "due_date"),
    )


class TaskDependency(Base):
    __tablename__ = "task_dependencies"

    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    depends_on_task_id: Mapped[UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True, index=True
    )

    __table_args__ = (CheckConstraint("task_id <> depends_on_task_id", name="not_self"),)


class CeremonyDocument(Base):
    """Dokument do ślubu z licznika ważności: data wydania, „zrobione”, ważność wg parafii.

    Zasady (okna, źródła) są w kodzie (`planner/documents.py`); tu tylko to, co wpisała para.
    """

    __tablename__ = "ceremony_documents"

    wedding_id: Mapped[UUID] = mapped_column(
        ForeignKey("weddings.id", ondelete="CASCADE"), primary_key=True
    )
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    issued_on: Mapped[date | None] = mapped_column(Date)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    valid_months: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(
            "valid_months IS NULL OR valid_months BETWEEN 1 AND 24", name="valid_months"
        ),
    )


class Helper(IdMixin, Base):
    """Pomocnik bez konta: bliska osoba, której para przypisuje zadania.

    Dostaje link (w bazie tylko hash tokenu) z listą swoich zadań i może je odhaczać.
    Nie widzi budżetu, gości ani innych zadań.
    """

    __tablename__ = "helpers"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_helpers_wedding", "wedding_id"),)


class TaskComment(IdMixin, Base):
    """Krótka rozmowa przy zadaniu (para i współorganizatorzy)."""

    __tablename__ = "task_comments"

    task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    author_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    text: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
