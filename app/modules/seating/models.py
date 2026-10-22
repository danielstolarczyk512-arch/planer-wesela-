from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow

SHAPES = ("round", "rectangular", "square")
# regular: zwykły stół; head: stół pary młodej (automat go nie wypełnia);
# kids: stół dziecięcy (automat sadza tam tylko dzieci i nastolatków).
TABLE_KINDS = ("regular", "head", "kids")
RULE_KINDS = ("together", "apart")


class SeatingTable(IdMixin, TimestampMixin, Base):
    __tablename__ = "seating_tables"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(8), default="regular")
    shape: Mapped[str] = mapped_column(String(12), default="round")
    capacity: Mapped[int] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    # Układ sali: środek stołu w metrach od lewego górnego rogu sali i obrót (stopnie).
    pos_x: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    pos_y: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    rotation: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint("capacity BETWEEN 1 AND 40", name="capacity_range"),
        CheckConstraint("rotation BETWEEN 0 AND 359", name="rotation_range"),
        CheckConstraint(f"kind IN {TABLE_KINDS}", name="kind"),
        CheckConstraint(f"shape IN {SHAPES}", name="shape"),
        Index("ix_seating_tables_wedding", "wedding_id", "sort_order"),
    )


class SeatAssignment(Base):
    """Gość przy stole. `locked` = ustawione ręcznie, automat tego nie zmienia."""

    __tablename__ = "seat_assignments"

    guest_id: Mapped[UUID] = mapped_column(
        ForeignKey("guests.id", ondelete="CASCADE"), primary_key=True
    )
    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    table_id: Mapped[UUID] = mapped_column(ForeignKey("seating_tables.id", ondelete="CASCADE"))
    seat_number: Mapped[int | None] = mapped_column(Integer)
    locked: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        CheckConstraint("seat_number IS NULL OR seat_number BETWEEN 1 AND 40", name="seat_range"),
        Index("ix_seat_assignments_table", "table_id"),
        Index("ix_seat_assignments_wedding", "wedding_id"),
        Index(
            "uq_seat_assignments_seat",
            "table_id",
            "seat_number",
            unique=True,
            postgresql_where=text("seat_number IS NOT NULL"),
        ),
    )


class SeatingRule(IdMixin, TimestampMixin, Base):
    """Życzenie pary: dwie osoby razem albo osobno (np. skłócone ciocie)."""

    __tablename__ = "seating_rules"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(8))
    guest_a_id: Mapped[UUID] = mapped_column(ForeignKey("guests.id", ondelete="CASCADE"))
    guest_b_id: Mapped[UUID] = mapped_column(ForeignKey("guests.id", ondelete="CASCADE"))
    note: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        CheckConstraint(f"kind IN {RULE_KINDS}", name="kind"),
        CheckConstraint("guest_a_id < guest_b_id", name="ordered_pair"),
        UniqueConstraint("guest_a_id", "guest_b_id", name="uq_seating_rules_pair"),
        Index("ix_seating_rules_wedding", "wedding_id"),
    )


class SeatingRoom(Base):
    """Układ sali: wymiary (m) i elementy stałe — parkiet, scena, bar, wejście, bufet."""

    __tablename__ = "seating_rooms"

    wedding_id: Mapped[UUID] = mapped_column(
        ForeignKey("weddings.id", ondelete="CASCADE"), primary_key=True
    )
    width_m: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("20"))
    length_m: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("12"))
    # [{kind, label, x, y, w, h}] — środek elementu i wymiary w metrach.
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012


AUTO_RUN_STATUSES = ("queued", "running", "done", "failed")


class SeatingAutoRun(IdMixin, Base):
    """Automatyczne usadzenie liczone w workerze (solver zajmuje CPU do kilkunastu sekund).

    Wynik to podgląd: para zapisuje go przez PUT …/seating/assignments.
    """

    __tablename__ = "seating_auto_runs"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    requested_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"status IN {AUTO_RUN_STATUSES}", name="status"),
        Index("ix_seating_auto_runs_wedding", "wedding_id", "created_at"),
    )
