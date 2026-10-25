"""Proces worker: zadania z kolejki + okresowe utrzymanie (retencja, sprzątanie).

Uruchomienie: python -m app.jobs.worker

Tory (WP_WORKER_LANE): `all` — wszystkie zadania i utrzymanie (dev, jedyny worker);
`fast` — tylko szybkie zadania (e-maile), bez utrzymania. W produkcji działają oba: OCR, AI
i automat stołów (minuty) nie wstrzymują wtedy resetu hasła ani linków RSVP.
"""

import signal
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from types import FrameType
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import ratelimit
from app.core.config import get_settings
from app.core.db import get_engine, get_sessionmaker, utcnow
from app.core.email import SEND_EMAIL_JOB, send_email
from app.core.logging import configure_logging
from app.jobs.queue import Job, claim_next, extend_lock, purge_finished, requeue_stale
from app.modules.ai import service as ai
from app.modules.audit import service as audit
from app.modules.documents import service as documents
from app.modules.seating import service as seating

log = structlog.get_logger()

Handler = Callable[[Session, dict[str, Any]], None]

# Payload tych zadań zawiera dane jednorazowe (np. linki z tokenem): czyścimy po wykonaniu.
SCRUB_PAYLOAD = {SEND_EMAIL_JOB}
MAINTENANCE_INTERVAL = timedelta(minutes=15)
MAINTENANCE_LOCK_ID = 7_340_001  # pg_advisory_lock: jedna instancja utrzymania naraz
DAILY_INTERVAL = timedelta(hours=24)  # retencja audytu i sprzątanie plików (kosztowne)
_last_daily: datetime | None = None
# Odnowienie blokady co minutę (blokada 5 min): długi OCR/AI (do 10 min) nie zostanie uznany
# za osierocony i uruchomiony drugi raz przez inny worker.
HEARTBEAT_INTERVAL = 60.0


def _send_email(_: Session, payload: dict[str, Any]) -> None:
    send_email(payload["to"], payload["subject"], payload["body"], payload.get("html"))


HANDLERS: dict[str, Handler] = {
    SEND_EMAIL_JOB: _send_email,
    documents.SCAN_JOB: documents.run_scan,
    documents.EXTRACT_JOB: documents.run_extraction,
    documents.DELETE_PREFIX_JOB: documents.run_delete_prefix,
    ai.EXTRACT_JOB: ai.run_offer_extraction,
    seating.AUTO_JOB: seating.run_auto_job,
}


# Zadania, które obsługuje tor `fast`: krótkie i pilne dla użytkownika.
FAST_JOBS = frozenset({SEND_EMAIL_JOB})


def lane_types(lane: str) -> frozenset[str] | None:
    """Typy zadań toru; None = wszystkie."""
    return FAST_JOBS if lane == "fast" else None


def _backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(30 * 2 ** (attempts - 1), 3600))


@contextmanager
def _heartbeat(job_id: UUID, interval: float | None = None) -> Iterator[None]:
    """Wątek odnawiający blokadę zadania, dopóki handler pracuje (osobna sesja bazy)."""
    stop = threading.Event()
    every = HEARTBEAT_INTERVAL if interval is None else interval

    def beat() -> None:
        while not stop.wait(every):
            try:
                with get_sessionmaker()() as db:
                    if not extend_lock(db, job_id):
                        return
            except Exception as exc:  # brak bazy chwilowo: spróbujemy przy następnym takcie
                log.warning("job_heartbeat_failed", job_id=str(job_id), error=type(exc).__name__)

    thread = threading.Thread(target=beat, name=f"heartbeat-{job_id}", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=5)


def run_job(job_id: UUID, handlers: dict[str, Handler] | None = None) -> None:
    handlers = handlers or HANDLERS
    session_factory = get_sessionmaker()
    with session_factory() as db:
        job = db.get_one(Job, job_id)
        handler = handlers.get(job.type)
        try:
            if handler is None:
                raise LookupError(f"Brak obsługi zadania typu {job.type}")
            with _heartbeat(job_id):
                handler(db, job.payload)
            job.status = "succeeded"
            job.finished_at = utcnow()
            job.last_error = None
            if job.type in SCRUB_PAYLOAD:
                job.payload = {"scrubbed": True}
            db.commit()
            log.info("job_succeeded", job_id=str(job.id), type=job.type)
        except Exception as exc:
            db.rollback()
            job = db.get_one(Job, job_id)
            # Bez treści wyjątku (może zawierać adres e-mail): tylko typ błędu.
            job.last_error = type(exc).__name__
            if job.attempts >= job.max_attempts:
                job.status = "dead"
                job.finished_at = utcnow()
                if job.type in SCRUB_PAYLOAD:
                    job.payload = {"scrubbed": True}
            else:
                job.status = "queued"
                job.run_after = utcnow() + _backoff(job.attempts)
            job.locked_until = None
            db.commit()
            log.warning(
                "job_failed",
                job_id=str(job.id),
                type=job.type,
                error_type=type(exc).__name__,
                status=job.status,
            )


def run_once(
    handlers: dict[str, Handler] | None = None, types: frozenset[str] | None = None
) -> bool:
    """Wykonuje jedno zadanie (z typów toru). Zwraca False, gdy kolejka jest pusta."""
    with get_sessionmaker()() as db:
        job = claim_next(db, types)
        job_id = job.id if job else None
    if job_id is None:
        return False
    run_job(job_id, handlers)
    return True


def run_maintenance() -> dict[str, int]:
    # Blokada sesyjna na osobnym połączeniu: trwa przez wszystkie kroki mimo commitów
    # (sesja ORM po commit może dostać z puli inne połączenie).
    with get_engine().connect() as lock_conn:
        locked = lock_conn.execute(
            text("SELECT pg_try_advisory_lock(:id)"), {"id": MAINTENANCE_LOCK_ID}
        ).scalar()
        lock_conn.commit()
        if not locked:
            return {}
        try:
            stats = _maintenance_steps()
        finally:
            lock_conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": MAINTENANCE_LOCK_ID})
            lock_conn.commit()
    log.info("maintenance_done", **stats)
    return stats


def _maintenance_steps() -> dict[str, int]:
    from app.core import idempotency
    from app.modules.guests import service as guests
    from app.modules.identity import service as identity
    from app.modules.notifications import service as notifications

    with get_sessionmaker()() as db:
        stats = {
            "stale_jobs_requeued": requeue_stale(db),
            "finished_jobs_purged": purge_finished(db, timedelta(days=30)),
            "rate_limit_hits_purged": ratelimit.purge_older_than(db, timedelta(days=1)),
            "idempotency_keys_purged": idempotency.purge_expired(db),
        }
        db.commit()
        stats["expired_credentials_purged"] = identity.purge_expired_credentials(db)
        stats["accounts_anonymized"] = identity.anonymize_due_accounts(db)
        stats["weddings_guests_anonymized"] = guests.anonymize_after_wedding(db)
        stats["digests_queued"] = notifications.send_digests(db)
        stats["files_queued_for_scan"] = documents.queue_unscanned(db)
        stats["seating_auto_runs_purged"] = seating.purge_auto_runs(db)
        global _last_daily
        if _last_daily is None or utcnow() - _last_daily > DAILY_INTERVAL:
            stats |= audit.purge_expired(db)
            stats["orphan_files_purged"] = documents.purge_orphan_files(db)
            _last_daily = utcnow()
    return stats


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    stopping = False

    def _stop(signum: int, _frame: FrameType | None) -> None:
        nonlocal stopping
        stopping = True
        log.info("worker_stopping", signal=signum)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    types = lane_types(settings.worker_lane)
    log.info("worker_started", lane=settings.worker_lane)
    last_maintenance = 0.0
    while not stopping:
        if (
            settings.worker_lane == "all"
            and time.monotonic() - last_maintenance > MAINTENANCE_INTERVAL.total_seconds()
        ):
            try:
                run_maintenance()
            except Exception:
                log.exception("maintenance_failed")
            last_maintenance = time.monotonic()
        try:
            worked = run_once(types=types)
        except Exception:
            log.exception("worker_loop_error")
            worked = False
        if not worked:
            time.sleep(1.0)
    log.info("worker_stopped")


if __name__ == "__main__":
    main()
