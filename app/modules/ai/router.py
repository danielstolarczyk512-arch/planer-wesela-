from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.deps import CurrentPrincipal, DbSession
from app.modules.ai import service
from app.modules.ai.models import AiRun

router = APIRouter(tags=["AI"])

Responses = dict[int | str, dict[str, Any]]
_READ: Responses = {
    401: {"description": "Brak uwierzytelnienia"},
    404: {"description": "Nie znaleziono lub brak dostępu"},
}
W = "/weddings/{wedding_id}"


class AnalyzeIn(BaseModel):
    vendor_id: UUID = Field(description="Usługodawca, którego dotyczy oferta")


class AiRunOut(BaseModel):
    id: UUID
    task_type: str
    status: Literal["queued", "running", "succeeded", "failed", "blocked"]
    provider: str
    model: str
    model_license: str | None
    prompt_version: str
    external_processing: bool
    cache_hit: bool
    document_version_id: UUID | None
    offer_id: UUID | None = Field(description="Szkic oferty do przejrzenia (status needs_review)")
    validation: dict[str, Any] | None
    error: str | None
    tokens_in: int | None
    tokens_out: int | None
    duration_ms: int | None
    created_at: datetime
    finished_at: datetime | None
    note: str = (
        "Wynik AI to szkic. Każdą pozycję porównaj z dokumentem; pozycje "
        "„unverified” nie mają potwierdzenia w tekście. To nie jest porada prawna."
    )


def run_out(r: AiRun) -> AiRunOut:
    return AiRunOut.model_validate(
        {
            "id": r.id,
            "task_type": r.task_type,
            "status": r.status,
            "provider": r.provider,
            "model": r.model,
            "model_license": r.model_license,
            "prompt_version": r.prompt_version,
            "external_processing": r.external_processing,
            "cache_hit": r.cache_hit,
            "document_version_id": r.document_version_id,
            "offer_id": r.offer_id,
            "validation": r.validation,
            "error": r.error,
            "tokens_in": r.tokens_in,
            "tokens_out": r.tokens_out,
            "duration_ms": r.duration_ms,
            "created_at": r.created_at,
            "finished_at": r.finished_at,
        }
    )


@router.post(
    f"{W}/documents/{{document_id}}/versions/{{version_id}}/analyze",
    status_code=202,
    responses={
        **_READ,
        403: {"description": "Rola bez prawa do AI"},
        409: {"description": "Brak zgody na zewnętrznego dostawcę"},
        422: {"description": "Tekst dokumentu nie jest gotowy"},
        429: {"description": "Dzienny limit analiz"},
        503: {"description": "AI wyłączone"},
    },
    summary="Analiza AI dokumentu → szkic oferty z cytatami (do przejrzenia)",
)
def analyze(
    wedding_id: UUID,
    document_id: UUID,
    version_id: UUID,
    body: AnalyzeIn,
    principal: CurrentPrincipal,
    db: DbSession,
) -> AiRunOut:
    return run_out(
        service.request_offer_extraction(
            db, principal, wedding_id, document_id, version_id, body.vendor_id
        )
    )


@router.get(f"{W}/ai-runs", responses=_READ, summary="Historia analiz AI (audyt)")
def list_runs(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> list[AiRunOut]:
    return [run_out(r) for r in service.list_runs(db, principal, wedding_id)]


@router.get(f"{W}/ai-runs/{{run_id}}", responses=_READ, summary="Status i wynik analizy AI")
def get_run(wedding_id: UUID, run_id: UUID, principal: CurrentPrincipal, db: DbSession) -> AiRunOut:
    return run_out(service.get_run(db, principal, wedding_id, run_id))
