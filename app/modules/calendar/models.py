from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, utcnow


class CalendarFeedToken(IdMixin, Base):
    """Prywatny adres kalendarza (ICS) członka wesela. W bazie tylko hash tokenu.

    Jeden aktywny adres na osobę i wesele; nowy unieważnia poprzedni. Dostęp wygasa
    razem z członkostwem w weselu.
    """

    __tablename__ = "calendar_feed_tokens"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_calendar_feed_tokens_wedding_user", "wedding_id", "user_id"),)
