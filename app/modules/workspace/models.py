from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow

CEREMONY_TYPES = ("civil", "concordat", "religious_other", "humanist", "undecided")
WEDDING_STATUSES = ("planning", "completed", "archived")
EVENT_KINDS = ("ceremony", "reception", "after_party", "other")
MEMBER_ROLES = ("owner", "coorganizer", "viewer", "coordinator", "sponsor")
INVITABLE_ROLES = ("coorganizer", "viewer", "coordinator", "sponsor")


class Wedding(IdMixin, TimestampMixin, Base):
    __tablename__ = "weddings"

    name: Mapped[str] = mapped_column(String(120))
    wedding_date: Mapped[date | None] = mapped_column(Date)
    planned_month: Mapped[date | None] = mapped_column(Date)
    ceremony_type: Mapped[str] = mapped_column(String(24), default="undecided")
    city: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(64))
    guest_count_planned: Mapped[int | None] = mapped_column(Integer)
    total_budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="PLN")
    style: Mapped[str | None] = mapped_column(String(120))
    colors: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    priorities: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Warsaw")
    status: Mapped[str] = mapped_column(String(16), default="planning")
    # Ustawiane przez zadanie retencji (dane gości zanonimizowane po weselu).
    guests_anonymized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(f"ceremony_type IN {CEREMONY_TYPES}", name="ceremony_type"),
        CheckConstraint(f"status IN {WEDDING_STATUSES}", name="status"),
        CheckConstraint("guest_count_planned >= 0", name="guest_count_non_negative"),
        CheckConstraint("total_budget >= 0", name="budget_non_negative"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_iso"),
        CheckConstraint("extract(day from planned_month) = 1", name="planned_month_first_day"),
    )


class Event(IdMixin, TimestampMixin, Base):
    """Wydarzenie wesela: ceremonia, przyjęcie, poprawiny."""

    __tablename__ = "events"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(120))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    address: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(f"kind IN {EVENT_KINDS}", name="kind"),
        CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at", name="ends_after_starts"
        ),
        Index("ix_events_wedding_starts", "wedding_id", "starts_at"),
    )


class WeddingMember(Base):
    __tablename__ = "wedding_members"

    wedding_id: Mapped[UUID] = mapped_column(
        ForeignKey("weddings.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Rola „sponsor”: widzi tylko wkład tego źródła finansowania (np. rodzice).
    funder_id: Mapped[UUID | None] = mapped_column(ForeignKey("funders.id", ondelete="SET NULL"))

    __table_args__ = (CheckConstraint(f"role IN {MEMBER_ROLES}", name="role"),)


class WeddingInvitation(IdMixin, Base):
    __tablename__ = "wedding_invitations"

    wedding_id: Mapped[UUID] = mapped_column(
        ForeignKey("weddings.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(16))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    funder_id: Mapped[UUID | None] = mapped_column(ForeignKey("funders.id", ondelete="SET NULL"))

    __table_args__ = (CheckConstraint(f"role IN {INVITABLE_ROLES}", name="role"),)
