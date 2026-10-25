"""Proces `discovery-scheduler`: co minutę planuje zadania odświeżenia źródeł.

Uruchomienie: python -m app.modules.discovery.scheduler
Wiele replik jest bezpiecznych (blokada doradcza PostgreSQL w `schedule_due`).
"""

import signal
import time
from types import FrameType

import structlog

from app.core.config import get_settings
from app.core.db import get_sessionmaker, utcnow
from app.core.logging import configure_logging
from app.modules.discovery import service

log = structlog.get_logger()
TICK_SECONDS = 60.0
DAY_SECONDS = 24 * 3600.0


def tick() -> int:
    with get_sessionmaker()() as db:
        return service.schedule_due(db)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    stopping = False

    def _stop(signum: int, _frame: FrameType | None) -> None:
        nonlocal stopping
        stopping = True
        log.info("discovery_scheduler_stopping", signal=signum)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log.info("discovery_scheduler_started", at=utcnow().isoformat())
    last_purge = 0.0
    while not stopping:
        try:
            queued = tick()
            if queued:
                log.info("discovery_scheduled", jobs=queued)
            if time.monotonic() - last_purge > DAY_SECONDS:
                with get_sessionmaker()() as db:
                    stats = service.purge_old(db)
                    db.commit()
                log.info("discovery_retention", **stats)
                last_purge = time.monotonic()
        except Exception:
            log.exception("discovery_scheduler_error")
        # sen w krótkich odcinkach: szybka reakcja na SIGTERM
        for _ in range(int(TICK_SECONDS)):
            if stopping:
                break
            time.sleep(1.0)
    log.info("discovery_scheduler_stopped")


if __name__ == "__main__":
    main()
