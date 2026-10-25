"""Badacz katalogu: planowanie, pobieranie źródła, decyzje o ponowieniu/zatrzymaniu.

Zasady niezawodności (ADR-0008):
- harmonogram tworzy małe zadania `discovery_fetch_source` pod blokadą doradczą PostgreSQL —
  dwie repliki schedulera albo restart nie podwajają zadań, a zadanie, które trafi do kolejki
  dwa razy, drugi raz nic nie robi (`next_check_at` w przyszłości);
- jedno pobranie naraz na domenę (wiersz domeny `FOR UPDATE SKIP LOCKED`), odstęp między
  pobraniami, dzienny limit, `Retry-After`, wyłącznik awaryjny po serii awarii domeny;
- 401/403/CAPTCHA/robots.txt = zatrzymanie źródła (`blocked`), 404/410 = `gone` z zachowaniem
  historii; nic z tego nie jest obchodzone innym klientem ani nagłówkami.
"""

import hashlib
import random
import time
import urllib.robotparser
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import structlog
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import utcnow
from app.core.errors import Conflict, Unprocessable
from app.jobs.queue import Job, enqueue, requeue_stale
from app.modules.audit import service as audit
from app.modules.catalog import ingest as catalog_ingest
from app.modules.catalog.models import (
    DiscoveryControl,
    DomainState,
    SourceObservation,
    VendorSource,
)
from app.modules.discovery import extract
from app.modules.discovery.fetcher import FetchResult, fetch_page
from app.modules.discovery.safety import UnsafeUrl, resolve_public, validate_url
from app.modules.vendors.models import CATEGORIES

log = structlog.get_logger()

FETCH_JOB = "discovery_fetch_source"
REQUEST_JOB = "discovery_request"  # zlecenie pary; obsługa w concierge.service
DISCOVERY_JOBS = frozenset({FETCH_JOB, REQUEST_JOB})
SCHEDULER_LOCK_ID = 7_340_002
ROBOTS_TTL = timedelta(hours=24)
CIRCUIT_THRESHOLD = 5
CIRCUIT_OPEN = timedelta(hours=6)
BOT_TOKEN = "NaszDzienBot"  # noqa: S105  # nosec B105 - nazwa agenta w robots.txt, nie sekret
BLOCKING = {
    "access_denied": "Strona odmawia dostępu (401/403) — nie obchodzimy zabezpieczeń.",
    "captcha": "Strona wymaga rozwiązania CAPTCHA — nie obchodzimy zabezpieczeń.",
    "unsafe_url": "Adres nie przeszedł kontroli bezpieczeństwa.",
    "cross_domain_redirect": "Strona przekierowuje na inną domenę — dodaj nowy adres jako źródło.",
    "robots_disallowed": "robots.txt nie zezwala na pobranie tej strony.",
}
FAILING = {
    "unsupported_type": "Strona nie jest dokumentem HTML.",
    "too_large": "Strona przekracza dozwolony rozmiar.",
    "too_many_redirects": "Zbyt wiele przekierowań.",
    "client_error": "Strona zwróciła błąd (4xx).",
}
TRANSIENT = frozenset({"rate_limited", "server_error", "timeout", "network_error"})


def _sleep(seconds: float) -> None:  # osobna funkcja: testy podmieniają bez czekania
    time.sleep(seconds)


def get_control(db: Session) -> DiscoveryControl:
    settings = get_settings()
    db.execute(
        pg_insert(DiscoveryControl)
        .values(id=1, paused=False, daily_fetch_limit=settings.discovery_daily_fetch_limit)
        .on_conflict_do_nothing(index_elements=["id"])
    )
    return db.get_one(DiscoveryControl, 1, populate_existing=True)


def beat_worker() -> None:
    """Tętno procesu badacza (widoczne w panelu): ostatnia aktywność workera, także bezczynnego."""
    from app.core.db import get_sessionmaker

    with get_sessionmaker()() as db:
        get_control(db).worker_heartbeat_at = utcnow()
        db.commit()


def capabilities() -> dict[str, Any]:
    """Co badacz naprawdę potrafi — GUI mówi o tym wprost."""
    return {
        "refresh_known_sources": True,
        "search_new_sources": {
            "configured": False,
            "reason": (
                "Brak skonfigurowanego, legalnego i bezpłatnego źródła adresów. "
                "Aktualizujemy podane strony firm; nie przeszukujemy całego internetu."
            ),
        },
    }


# --- źródła ---------------------------------------------------------------------------------


def add_source(
    db: Session,
    admin_id: UUID,
    *,
    url: str,
    category: str,
    region_hint: str | None,
    access_basis: str | None,
    refresh_interval_days: int,
    catalog_vendor_id: UUID | None = None,
) -> VendorSource:
    settings = get_settings()
    if category not in CATEGORIES:
        raise Unprocessable("Nieznana kategoria.", code="discovery.bad_category")
    try:
        target = validate_url(url, allow_private=settings.discovery_allow_private_hosts)
        resolve_public(
            target.host, target.port, allow_private=settings.discovery_allow_private_hosts
        )
    except UnsafeUrl as exc:
        raise Unprocessable(f"Adres odrzucony: {exc.reason}.", code="discovery.unsafe_url") from exc
    if db.scalar(select(VendorSource.id).where(VendorSource.url == target.url)):
        raise Conflict("Ten adres jest już źródłem.", code="discovery.source_exists")
    domain = target.host.removeprefix("www.")
    source = VendorSource(
        url=target.url,
        domain=domain,
        category=category,
        region_hint=region_hint,
        access_basis=access_basis or "strona firmy podana przez administratora",
        refresh_interval_days=refresh_interval_days,
        catalog_vendor_id=catalog_vendor_id,
        created_by=admin_id,
    )
    db.add(source)
    db.flush()
    audit.record(
        db,
        actor_type="admin",
        actor_id=admin_id,
        entity_type="catalog_source",
        entity_id=source.id,
        action="create",
        changes={"url": target.url, "category": category},
    )
    return source


# --- harmonogram ----------------------------------------------------------------------------


def schedule_due(db: Session, *, now: datetime | None = None) -> int:
    """Jeden obieg schedulera. Zwraca liczbę zaplanowanych zadań."""
    now = now or utcnow()
    got = db.execute(
        text("SELECT pg_try_advisory_xact_lock(:id)"), {"id": SCHEDULER_LOCK_ID}
    ).scalar()
    if not got:
        db.rollback()
        return 0
    control = get_control(db)
    control.scheduler_heartbeat_at = now
    queued = 0
    requeue_stale(db)
    if not control.paused:
        pending = set(
            db.scalars(
                select(Job.payload["source_id"].astext).where(
                    Job.type == FETCH_JOB, Job.status.in_(("queued", "running"))
                )
            )
        )
        due = db.scalars(
            select(VendorSource)
            .where(VendorSource.state == "active", VendorSource.next_check_at <= now)
            .order_by(VendorSource.next_check_at)
            .limit(50)
        ).all()
        for source in due:
            if str(source.id) in pending:
                continue
            enqueue(db, FETCH_JOB, {"source_id": str(source.id)}, max_attempts=3)
            queued += 1
    db.commit()  # zwalnia blokadę transakcyjną
    return queued


def purge_old(db: Session) -> dict[str, int]:
    """Retencja: wyciągi stron po 90 dniach, same wpisy o pobraniach po roku.

    Fakty i pakiety zachowują cytat dowodowy; usunięcie obserwacji tylko zeruje wskazanie.
    """
    retention = timedelta(days=get_settings().discovery_observation_retention_days)
    cleared = db.execute(
        update(SourceObservation)
        .where(
            SourceObservation.fetched_at < utcnow() - retention,
            SourceObservation.excerpt.is_not(None),
        )
        .values(excerpt=None)
    )
    deleted = db.execute(
        delete(SourceObservation).where(
            SourceObservation.fetched_at < utcnow() - timedelta(days=365)
        )
    )
    return {
        "excerpts_cleared": int(getattr(cleared, "rowcount", 0) or 0),
        "observations_deleted": int(getattr(deleted, "rowcount", 0) or 0),
    }


# --- pobieranie źródła ----------------------------------------------------------------------


def _defer(source: VendorSource, until: datetime) -> None:
    source.next_check_at = max(source.next_check_at, until)


def _domain_row(db: Session, domain: str) -> DomainState | None:
    db.execute(pg_insert(DomainState).values(domain=domain).on_conflict_do_nothing())
    return db.scalar(
        select(DomainState)
        .where(DomainState.domain == domain)
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    )


def _robots(
    db: Session, state: DomainState, source: VendorSource, settings: Settings, now: datetime
) -> str:
    """'allow' | 'deny' | 'retry'. Brak robots.txt (4xx) = brak ograniczeń (RFC 9309)."""
    parts = urlsplit(source.url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    if (
        state.robots_txt is None
        or state.robots_checked_at is None
        or (now - state.robots_checked_at > ROBOTS_TTL)
    ):
        result = fetch_page(robots_url, settings, accept=("text/",))
        state.last_fetch_at = utcnow()
        if result.outcome == "ok":
            state.robots_txt = (result.text or "")[:200_000]
        elif result.outcome in ("gone", "client_error", "access_denied", "unsupported_type"):
            state.robots_txt = ""
        else:
            return "retry"
        state.robots_checked_at = now
        _sleep(settings.discovery_domain_min_interval_seconds)
    parser = urllib.robotparser.RobotFileParser()
    parser.parse((state.robots_txt or "").splitlines())
    return "allow" if parser.can_fetch(BOT_TOKEN, source.url) else "deny"


def _backoff(failures: int, retry_after: int | None) -> timedelta:
    base = min(60 * 2 ** max(failures - 1, 0), 3600)
    jitter = random.uniform(0.5, 1.5)  # noqa: S311 - rozproszenie ponowień, nie kryptografia
    return timedelta(seconds=max(base * jitter, retry_after or 0))


def run_fetch_source(db: Session, payload: dict[str, Any]) -> None:
    """Zadanie workera `discovery`. Błędy źródła są stanem źródła, nie awarią zadania."""
    settings = get_settings()
    source = db.get(VendorSource, UUID(payload["source_id"]), populate_existing=True)
    if source is None or source.state != "active":
        return
    control = get_control(db)
    now = utcnow()
    if control.paused or source.next_check_at > now:
        db.commit()
        return  # pauza albo duplikat zadania (źródło odświeżone w międzyczasie)
    control.worker_heartbeat_at = now
    used = db.scalar(
        select(func.count())
        .select_from(SourceObservation)
        .where(SourceObservation.fetched_at > now - timedelta(hours=24))
    )
    if (used or 0) >= control.daily_fetch_limit:
        _defer(source, now + timedelta(hours=1))
        db.commit()
        return
    state = _domain_row(db, source.domain)
    if state is None:  # inny worker pobiera z tej domeny: jedno pobranie naraz
        _defer(source, now + timedelta(seconds=30))
        db.commit()
        return
    gate = max(
        (state.circuit_open_until or now),
        (state.retry_after_until or now),
        (state.last_fetch_at or now - timedelta(days=1))
        + timedelta(seconds=settings.discovery_domain_min_interval_seconds),
    )
    if gate > now:
        _defer(source, gate)
        db.commit()
        return

    verdict = _robots(db, state, source, settings, now)
    if verdict == "retry":
        _transient(db, source, state, settings, "network_error", None, now)
        _record(db, source, FetchResult("network_error", detail="robots.txt"), None)
        db.commit()
        return
    if verdict == "deny":
        result = FetchResult("robots_disallowed", final_url=source.url)
    else:
        result = fetch_page(source.url, settings)
    state.last_fetch_at = utcnow()
    _apply(db, source, state, settings, result)
    db.commit()


def _record(
    db: Session,
    source: VendorSource,
    result: FetchResult,
    content_hash: str | None,
    *,
    excerpt: str | None = None,
    unchanged: bool = False,
) -> SourceObservation:
    obs = SourceObservation(
        source_id=source.id,
        http_status=result.status,
        outcome=result.outcome,
        final_url=result.final_url,
        content_hash=content_hash,
        parser_version=extract.PARSER_VERSION if result.outcome == "ok" else None,
        excerpt=excerpt,
        unchanged=unchanged,
    )
    db.add(obs)
    db.flush()
    return obs


def _apply(
    db: Session, source: VendorSource, state: DomainState, settings: Settings, result: FetchResult
) -> None:
    now = utcnow()
    source.last_checked_at = now
    if result.outcome == "ok":
        _apply_ok(db, source, state, settings, result, now)
    elif result.outcome == "gone":
        _record(db, source, result, None)
        source.state, source.state_reason = "gone", "Strona zniknęła (404/410)."
        source.consecutive_failures = 0
        catalog_ingest.withdraw_source(db, source, "source_gone", now)
        _problem(db, source, "Strona zniknęła (404/410). Dane z niej nie są już aktualne.")
    elif result.outcome in BLOCKING:
        _record(db, source, result, None)
        source.state, source.state_reason = "blocked", BLOCKING[result.outcome]
        _problem(db, source, BLOCKING[result.outcome])
    elif result.outcome in TRANSIENT:
        _record(db, source, result, None)
        _transient(db, source, state, settings, result.outcome, result.retry_after, now)
    else:
        _record(db, source, result, None)
        source.state = "failed"
        source.state_reason = FAILING.get(result.outcome, "Nieudane pobranie.")
        _problem(db, source, source.state_reason)
    log.info(
        "discovery_fetch", source_id=str(source.id), outcome=result.outcome, status=result.status
    )


def _apply_ok(
    db: Session,
    source: VendorSource,
    state: DomainState,
    settings: Settings,
    result: FetchResult,
    now: datetime,
) -> None:
    digest = hashlib.sha256(result.body or b"").hexdigest()
    unchanged = digest == source.last_content_hash and source.last_success_at is not None
    source.consecutive_failures = 0
    state.consecutive_failures, state.circuit_open_until, state.retry_after_until = 0, None, None
    source.next_check_at = now + timedelta(days=source.refresh_interval_days)
    source.last_success_at, source.state_reason = now, None
    control = get_control(db)
    control.last_success_at = now
    if unchanged:
        _record(db, source, result, digest, unchanged=True)
        catalog_ingest.refresh_unchanged(db, source, now)
        return
    extracted = extract.extract(result.text or "", result.final_url or source.url)
    obs = _record(db, source, result, digest, excerpt=extracted.text)
    source.last_content_hash = digest
    if extracted.name is None and not extracted.facts and not extracted.packages:
        _problem(db, source, "Nie udało się odczytać z tej strony żadnych danych firmy.", weak=True)
        return
    stats = catalog_ingest.ingest(db, source, obs, extracted, now)
    log.info(
        "discovery_ingested",
        source_id=str(source.id),
        **stats.__dict__ | {"vendor_id": str(stats.vendor_id)},
    )


def _transient(
    db: Session,
    source: VendorSource,
    state: DomainState,
    settings: Settings,
    outcome: str,
    retry_after: int | None,
    now: datetime,
) -> None:
    source.consecutive_failures += 1
    state.consecutive_failures += 1
    if retry_after:
        state.retry_after_until = now + timedelta(seconds=retry_after)
    if state.consecutive_failures >= CIRCUIT_THRESHOLD:
        state.circuit_open_until = now + CIRCUIT_OPEN
    if source.consecutive_failures >= settings.discovery_max_attempts:
        source.state = "failed"
        source.state_reason = f"Po {source.consecutive_failures} nieudanych próbach ({outcome})."
        _problem(db, source, source.state_reason)
    else:
        source.next_check_at = now + _backoff(source.consecutive_failures, retry_after)


def _problem(db: Session, source: VendorSource, summary: str, *, weak: bool = False) -> None:
    catalog_ingest.open_review(
        db,
        kind="weak_evidence" if weak else "source_problem",
        summary=f"{source.url}: {summary}",
        dedupe_key=f"source:{source.id}:{'weak' if weak else 'problem'}",
        vendor_id=source.catalog_vendor_id,
        source_id=source.id,
    )
