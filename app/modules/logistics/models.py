"""Transport i noclegi gości: kursy (autokar, bus) z miejscami oraz pokoje z listą osób."""

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

from app.core.db import Base, IdMixin, TimestampMixin

RUN_KINDS = ("there", "back", "other")


class TransportRun(IdMixin, TimestampMixin, Base):
    """Kurs, np. „Autokar: kościół → sala” albo „Powrót o 1:00”."""

    __tablename__ = "transport_runs"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    vendor_id: Mapped[UUID | None] = mapped_column(ForeignKey("vendors.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(8), default="there")
    departs_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    from_place: Mapped[str | None] = mapped_column(String(120))
    to_place: Mapped[str | None] = mapped_column(String(120))
    capacity: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    # Goście widzą kurs w formularzu RSVP i mogą się na niego zapisać (tylko liczba wolnych miejsc).
    show_to_guests: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(f"kind IN {RUN_KINDS}", name="kind"),
        CheckConstraint("capacity BETWEEN 1 AND 500", name="capacity"),
        Index("ix_transport_runs_wedding", "wedding_id", "departs_at"),
    )


class TransportSeat(Base):
    """Gość na kursie (ten sam gość może jechać „tam” i „z powrotem”)."""

    __tablename__ = "transport_seats"

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("transport_runs.id", ondelete="CASCADE"), primary_key=True
    )
    guest_id: Mapped[UUID] = mapped_column(
        ForeignKey("guests.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class LodgingRoom(IdMixin, TimestampMixin, Base):
    """Pokój na nocleg: obiekt, nazwa/numer, liczba miejsc, noce."""

    __tablename__ = "lodging_rooms"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    place: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(60))
    beds: Mapped[int] = mapped_column(Integer)
    check_in: Mapped[date | None] = mapped_column(Date)
    check_out: Mapped[date | None] = mapped_column(Date)
    paid_by: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint("beds BETWEEN 1 AND 20", name="beds"),
        CheckConstraint(
            "check_in IS NULL OR check_out IS NULL OR check_out > check_in", name="nights"
        ),
        Index("ix_lodging_rooms_wedding", "wedding_id", "place"),
    )


class RoomGuest(Base):
    """Gość w pokoju (jeden pokój na gościa)."""

    __tablename__ = "room_guests"

    room_id: Mapped[UUID] = mapped_column(
        ForeignKey("lodging_rooms.id", ondelete="CASCADE"), index=True
    )
    guest_id: Mapped[UUID] = mapped_column(
        ForeignKey("guests.id", ondelete="CASCADE"), primary_key=True
    )
