from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core.deps import CurrentPrincipal, DbSession
from app.core.schemas import Money
from app.modules.overview import attention, search, service

router = APIRouter(tags=["wesela"])

Responses = dict[int | str, dict[str, Any]]
_READ: Responses = {
    401: {"description": "Brak uwierzytelnienia"},
    404: {"description": "Nie znaleziono lub brak dostępu"},
}


class WeddingBrief(BaseModel):
    id: UUID
    name: str
    wedding_date: date | None
    planned_month: str | None
    days_to_wedding: int | None


class TaskBrief(BaseModel):
    id: UUID
    title: str
    due_date: date | None
    priority: int


class TasksSummary(BaseModel):
    total: int
    done: int
    open: int
    overdue: int
    due_next_14_days: list[TaskBrief]


class BudgetSummary(BaseModel):
    total_budget: Money | None
    estimated_total: Money
    paid_total: Money
    remaining_to_pay: Money
    over_budget: bool
    overdue_payments: int
    upcoming_payments_30d: int


class GuestsSummary(BaseModel):
    planned: int
    invited: int
    confirmed: int
    pending_answers: int


class WeddingSummary(BaseModel):
    wedding: WeddingBrief
    tasks: TasksSummary
    budget: BudgetSummary
    guests: GuestsSummary


@router.get(
    "/weddings/{wedding_id}/summary",
    responses=_READ,
    summary="Pulpit: termin, zadania, budżet, goście w jednym zapytaniu",
)
def wedding_summary(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> WeddingSummary:
    s = service.summary(db, principal, wedding_id)
    b = s["budget"]
    money = ("estimated_total", "paid_total", "remaining_to_pay")
    s["budget"] = {
        **b,
        **{k: Money(amount=b[k]) for k in money},
        "total_budget": Money(amount=b["total_budget"]) if b["total_budget"] is not None else None,
    }
    return WeddingSummary.model_validate(s)


@router.get(
    "/weddings/{wedding_id}/export",
    responses={**_READ, 403: {"description": "Rola bez prawa eksportu"}},
    summary="Pełny eksport danych wesela (JSON, RODO art. 15 i 20)",
)
def wedding_export(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> dict[str, Any]:
    return service.export_wedding(db, principal, wedding_id)


class AttentionItem(BaseModel):
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    link: str  # ścieżka w weselu, np. „frekwencja” → /w/{id}/frekwencja


@router.get(
    "/weddings/{wedding_id}/attention",
    responses=_READ,
    summary="Wymaga uwagi: najważniejsze ostrzeżenia z całego wesela (ekran Dziś)",
)
def wedding_attention(
    wedding_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> list[AttentionItem]:
    return [AttentionItem.model_validate(i) for i in attention.attention(db, principal, wedding_id)]


class WeddingSearchHit(BaseModel):
    kind: Literal["task", "guest", "vendor", "expense"]
    id: UUID = Field(description="Zadanie, rodzina (dla gościa), usługodawca albo wydatek")
    title: str
    subtitle: str


class WeddingSearchOut(BaseModel):
    query: str
    results: list[WeddingSearchHit]


@router.get(
    "/weddings/{wedding_id}/search",
    responses=_READ,
    summary="Wyszukiwarka: zadania, goście, usługodawcy, wydatki",
)
def search_wedding(
    wedding_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    q: Annotated[str, Query(max_length=80)] = "",
) -> WeddingSearchOut:
    return WeddingSearchOut.model_validate(search.search(db, principal, wedding_id, q))
