"""Limity żądań przechowywane w PostgreSQL (działają przy wielu instancjach api).

Na MVP wystarczające. Przy dużym ruchu: przeniesienie do Redis (ADR-0002, kryteria rewizji).
"""

import hashlib
from datetime import datetime, timedelta

from sqlalchemy import BigInteger, DateTime, Identity, Index, String, delete, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base, utcnow
from app.core.errors import RateLimited


class RateLimitHit(Base):
    __tablename__ = "rate_limit_hits"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    key: Mapped[str] = mapped_column(String(200))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_rate_limit_hits_key_at", "key", "at"),)


def key_for(kind: str, value: str) -> str:
    """Klucz z hashem wartości: w bazie nie zostają e-maile ani adresy IP."""
    digest = hashlib.sha256(value.lower().encode()).hexdigest()[:32]
    return f"{kind}:{digest}"


def check(db: Session, key: str, limit: int, window: timedelta) -> None:
    since = utcnow() - window
    count, oldest = db.execute(
        select(func.count(), func.min(RateLimitHit.at)).where(
            RateLimitHit.key == key, RateLimitHit.at > since
        )
    ).one()
    if count >= limit and oldest is not None:
        retry_after = int((oldest + window - utcnow()).total_seconds())
        raise RateLimited(retry_after)


def record(db: Session, key: str) -> None:
    db.add(RateLimitHit(key=key))


def hit(db: Session, key: str, limit: int, window: timedelta) -> None:
    """Sprawdza limit i rejestruje próbę (zapis trafia do bazy przy commit wywołującego)."""
    check(db, key, limit, window)
    record(db, key)


def purge_older_than(db: Session, age: timedelta) -> int:
    result = db.execute(delete(RateLimitHit).where(RateLimitHit.at < utcnow() - age))
    return int(getattr(result, "rowcount", 0) or 0)
