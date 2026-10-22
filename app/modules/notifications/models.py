from datetime import date
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

DIGEST_MODES = ("daily", "weekly", "off")


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    digest: Mapped[str] = mapped_column(String(8), default="daily")

    __table_args__ = (CheckConstraint(f"digest IN {DIGEST_MODES}", name="digest"),)


class DigestLog(Base):
    """Zapobiega wysłaniu tego samego podsumowania dwa razy (wiele instancji workera)."""

    __tablename__ = "digest_log"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    wedding_id: Mapped[UUID] = mapped_column(
        ForeignKey("weddings.id", ondelete="CASCADE"), primary_key=True
    )
    sent_on: Mapped[date] = mapped_column(Date, primary_key=True)
