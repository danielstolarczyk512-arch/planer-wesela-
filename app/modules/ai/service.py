"""Uruchamianie AI z kontrolą: wyłącznik, limity, zgoda, cache, audyt, walidacja wyniku."""

import hashlib
from datetime import timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.errors import AppError, Conflict, NotFound, RateLimited
from app.jobs.queue import enqueue
from app.modules.ai import extractor, prompts
from app.modules.ai.models import AiRun
from app.modules.ai.providers import ProviderError, get_provider
from app.modules.ai.redaction import redact
from app.modules.documents import service as documents
from app.modules.identity.models import User
from app.modules.identity.service import ACTIVE_STATUSES, Principal, has_active_consent
from app.modules.offers import service as offers
from app.modules.vendors import service as vendors
from app.modules.vendors.models import Vendor
from app.modules.workspace.permissions import Action, authorize

log = structlog.get_logger()

EXTRACT_JOB = "ai_extract_offer"
TASK_OFFER = "offer_extraction"


class AiDisabled(AppError):
    status, code, title = 503, "ai.disabled", "Funkcje AI są wyłączone"


def request_offer_extraction(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    document_id: UUID,
    version_id: UUID,
    vendor_id: UUID,
) -> AiRun:
    settings = get_settings()
    if not settings.ai_enabled:
        raise AiDisabled("Analiza AI jest chwilowo wyłączona. Wpisz ofertę ręcznie.")
    authorize(db, principal.user.id, wedding_id, Action.RUN_AI)
    version = documents.get_version(db, principal, wedding_id, document_id, version_id)
    documents.ensure_text(version.text_status)
    vendors.get_in_wedding(db, wedding_id, vendor_id)

    since = utcnow() - timedelta(days=1)
    used = (
        db.scalar(
            select(func.count())
            .select_from(AiRun)
            .where(AiRun.wedding_id == wedding_id, AiRun.created_at > since)
        )
        or 0
    )
    if used >= settings.ai_max_runs_per_wedding_per_day:
        raise RateLimited(3600)

    provider = get_provider()
    if provider.external and not has_active_consent(
        db, principal.user.id, "ai_external_processing"
    ):
        raise Conflict(
            "Analiza u zewnętrznego dostawcy wymaga Twojej zgody "
            "(POST /me/consents, type=ai_external_processing).",
            code="ai.consent_required",
        )
    run = AiRun(
        wedding_id=wedding_id,
        task_type=TASK_OFFER,
        document_version_id=version.id,
        vendor_id=vendor_id,
        requested_by=principal.user.id,
        provider=provider.name,
        model=provider.model,
        model_license=provider.model_license,
        prompt_version=prompts.OFFER_EXTRACT_VERSION,
        prompt_fingerprint=prompts.prompt_fingerprint(),
        external_processing=provider.external,
    )
    db.add(run)
    db.flush()
    enqueue(db, EXTRACT_JOB, {"run_id": str(run.id)}, wedding_id=wedding_id, max_attempts=2)
    db.commit()
    return run


def _still_allowed(db: Session, run: AiRun, provider_name: str, external: bool) -> str | None:
    """Kontrola z chwili zlecenia powtórzona w workerze (audyt 2026-10-23, S6).

    Między zleceniem a wykonaniem można stracić rolę, konto albo wycofać zgodę; zmienić mógł się
    też dostawca. Zwraca powód odmowy albo None.
    """
    user = db.get(User, run.requested_by) if run.requested_by else None
    if user is None or user.status not in ACTIVE_STATUSES:
        return "Konto, które zleciło analizę, nie jest już aktywne."
    try:
        authorize(db, user.id, run.wedding_id, Action.RUN_AI)
    except AppError:
        return "Osoba, która zleciła analizę, nie ma już do niej uprawnień."
    if provider_name != run.provider or external != run.external_processing:
        return "Dostawca AI zmienił się po zleceniu. Zleć analizę ponownie."
    if external and not has_active_consent(db, user.id, "ai_external_processing"):
        return "Zgoda na analizę u zewnętrznego dostawcy została wycofana."
    return None


def _finish(db: Session, run: AiRun, status: str, error: str | None = None) -> None:
    run.status, run.error, run.finished_at = status, error, utcnow()
    db.commit()


def run_offer_extraction(db: Session, payload: dict[str, Any]) -> None:
    """Zadanie workera. Błędy dostawcy kończą się statusem failed (bez pętli ponowień)."""
    run = db.get(AiRun, UUID(payload["run_id"]))
    if run is None or run.status not in ("queued", "running"):
        return
    settings = get_settings()
    if not settings.ai_enabled:
        _finish(db, run, "blocked", "Funkcje AI zostały wyłączone przed uruchomieniem.")
        return
    provider = get_provider()
    refusal = _still_allowed(db, run, provider.name, provider.external)
    if refusal is not None:
        _finish(db, run, "blocked", refusal)
        return
    version = (
        documents.version_in_wedding(db, run.wedding_id, run.document_version_id)
        if run.document_version_id
        else None
    )
    vendor = db.get(Vendor, run.vendor_id) if run.vendor_id else None
    if version is None or vendor is None or version.text_status != "done":
        _finish(db, run, "failed", "Dokument lub usługodawca nie jest już dostępny.")
        return
    run.status = "running"
    db.commit()

    pages = documents.pages(version)
    document, truncated = extractor.build_document(pages, settings.ai_max_input_chars)
    user_text = document
    redactions: dict[str, int] = {}
    if provider.external:
        user_text, redactions = redact(document)
    user = prompts.OFFER_EXTRACT_USER.format(category=vendor.category, document=user_text)
    run.input_hash = hashlib.sha256((run.prompt_version + run.model + user).encode()).hexdigest()

    cached = db.scalars(
        select(AiRun)
        .where(
            AiRun.wedding_id == run.wedding_id,
            AiRun.input_hash == run.input_hash,
            AiRun.prompt_version == run.prompt_version,
            AiRun.model == run.model,
            AiRun.status == "succeeded",
            AiRun.id != run.id,
        )
        .order_by(AiRun.created_at.desc())
    ).first()
    if cached is not None and cached.output is not None:
        raw, run.cache_hit = cached.output, True
    else:
        try:
            result = provider.complete_json(
                prompts.OFFER_EXTRACT_SYSTEM, user, prompts.OFFER_SCHEMA
            )
        except ProviderError as exc:
            log.warning("ai_provider_error", run_id=str(run.id), error=str(exc))
            _finish(db, run, "failed", str(exc)[:300])
            return
        raw = result.data
        run.tokens_in, run.tokens_out = result.tokens_in, result.tokens_out
        run.duration_ms = result.duration_ms
    run.output = raw

    validated = extractor.validate(raw, "\n\n".join(pages), len(pages), pages)
    offer = offers.create_ai_draft(
        db,
        wedding_id=run.wedding_id,
        vendor_id=vendor.id,
        version_id=version.id,
        title=validated.title,
        min_guests=validated.min_guests,
        components=validated.components,
        terms=validated.terms,
        ai_run_id=run.id,
    )
    run.offer_id = offer.id
    run.validation = {
        **validated.stats,
        "input_truncated": truncated,
        "redactions": redactions,
        # fragmenty wyglądające na polecenia dla AI: para widzi ostrzeżenie przy szkicu
        "suspicious_instructions": validated.suspicious,
    }
    _finish(db, run, "succeeded")
    log.info("ai_run_succeeded", run_id=str(run.id), cache_hit=run.cache_hit, **validated.stats)


def get_run(db: Session, principal: Principal, wedding_id: UUID, run_id: UUID) -> AiRun:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    run = db.get(AiRun, run_id)
    if run is None or run.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono analizy.", code="ai.run_not_found")
    return run


def list_runs(db: Session, principal: Principal, wedding_id: UUID) -> list[AiRun]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return list(
        db.scalars(
            select(AiRun)
            .where(AiRun.wedding_id == wedding_id)
            .order_by(AiRun.created_at.desc())
            .limit(100)
        )
    )
