"""Po weselu: co mają oddać usługodawcy (zdjęcia, film) i lista spraw przy zmianie nazwiska."""

from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin


class Deliverable(IdMixin, TimestampMixin, Base):
    """Rzecz do odebrania od usługodawcy po weselu, np. „Zdjęcia (galeria online)” do 30.09."""

    __tablename__ = "deliverables"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    vendor_id: Mapped[UUID | None] = mapped_column(ForeignKey("vendors.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(120))
    due_on: Mapped[date | None] = mapped_column(Date)
    received_on: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (Index("ix_deliverables_wedding", "wedding_id", "due_on"),)


class AfterCheck(Base):
    """Odhaczona pozycja listy „po weselu” (np. zmiana nazwiska w banku)."""

    __tablename__ = "after_checks"

    wedding_id: Mapped[UUID] = mapped_column(
        ForeignKey("weddings.id", ondelete="CASCADE"), primary_key=True
    )
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    done_on: Mapped[date] = mapped_column(Date)
