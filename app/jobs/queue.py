"""Kolejka zadań w tabeli PostgreSQL (ADR-0003): SELECT ... FOR UPDATE SKIP LOCKED."""

from collections.abc import Collection
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    delete,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base, IdMixin, utcnow

JOB_STATUSES = ("queued", "running", "succeeded", "failed", "dead")
LOCK_DURATION = timedelta(minutes=5)


class Job(IdMixin, Base):
    __tablename__ = "jobs"

    type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    wedding_id: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"status IN {JOB_STATUSES}", name="status"),
        Index("ix_jobs_queued_run_after", "run_after", postgresql_where=text("status = 'queued'")),
    )


def enqueue(
    db: Session,
    job_type: str,
    payload: dict[str, Any],
    *,
    run_after: datetime | None = None,
    wedding_id: UUID | None = None,
    max_attempts: int = 5,
) -> Job:
    job = Job(
        type=job_type,
        payload=payload,
        run_after=run_after or utcnow(),
        wedding_id=wedding_id,
        max_attempts=max_attempts,
    )
    db.add(job)
    return job


def claim_next(db: Session, types: Collection[str] | None = None) -> Job | None:
    """Pobiera najstarsze gotowe zadanie; `types` zawęża do wskazanych typów (tor workera)."""
    now = utcnow()
    query = select(Job).where(Job.status == "queued", Job.run_after <= now)
    if types is not None:
        query = query.where(Job.type.in_(types))
    job = db.scalars(
        query.order_by(Job.run_after).limit(1).with_for_update(skip_locked=True)
    ).first()
    if job is None:
        return None
    job.status = "running"
    job.attempts += 1
    job.locked_until = now + LOCK_DURATION
    db.commit()
    return job


def extend_lock(db: Session, job_id: UUID) -> bool:
    """Odnawia blokadę trwającego zadania (heartbeat workera). False: zadanie już nie nasze."""
    result = db.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == "running")
        .values(locked_until=utcnow() + LOCK_DURATION)
    )
    db.commit()
    return bool(getattr(result, "rowcount", 0))


def requeue_stale(db: Session) -> int:
    """Zadania po awarii workera (przeterminowana blokada) wracają do kolejki."""
    stale = db.scalars(
        select(Job).where(Job.status == "running", Job.locked_until < utcnow())
    ).all()
    for job in stale:
        job.status = "queued"
        job.locked_until = None
    return len(stale)


def purge_finished(db: Session, older_than: timedelta) -> int:
    result = db.execute(
        delete(Job).where(
            Job.status.in_(("succeeded", "dead")), Job.finished_at < utcnow() - older_than
        )
    )
    return int(getattr(result, "rowcount", 0) or 0)
