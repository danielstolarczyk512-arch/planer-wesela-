from datetime import date, datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.core.schemas import PatchModel
from app.modules.workspace.schemas import PlannedMonth, check_wedding_dates

TaskStatus = Literal["todo", "in_progress", "done", "skipped"]
Category = Field(default="inne", min_length=1, max_length=32)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    category: str = Category
    priority: int = Field(default=2, ge=1, le=4)
    due_date: date | None = Field(default=None, description="Konkretny termin")
    offset_days: int | None = Field(
        default=None,
        ge=-1000,
        le=365,
        description="Termin względny: dni względem daty ślubu (ujemne = przed)",
    )
    parent_task_id: UUID | None = None
    assignee_user_id: UUID | None = None
    vendor_id: UUID | None = Field(default=None, description="Usługodawca, którego dotyczy zadanie")

    @model_validator(mode="after")
    def _one_due_kind(self) -> Self:
        if self.due_date is not None and self.offset_days is not None:
            raise ValueError("Podaj due_date albo offset_days, nie oba.")
        return self


class TaskUpdate(PatchModel):
    NOT_NULL = ("title", "category", "priority", "status")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    category: str | None = Field(default=None, min_length=1, max_length=32)
    priority: int | None = Field(default=None, ge=1, le=4)
    status: TaskStatus | None = None
    due_date: date | None = None
    offset_days: int | None = Field(default=None, ge=-1000, le=365)
    clear_due: bool = Field(default=False, description="Usuń termin zadania")
    assignee_user_id: UUID | None = None
    vendor_id: UUID | None = None

    @model_validator(mode="after")
    def _one_due_kind(self) -> Self:
        given = [self.due_date is not None, self.offset_days is not None, self.clear_due]
        if sum(given) > 1:
            raise ValueError("Podaj tylko jedno z: due_date, offset_days, clear_due.")
        return self


class TaskOut(BaseModel):
    id: UUID
    title: str
    description: str | None
    category: str
    priority: int
    status: TaskStatus
    due_mode: Literal["relative", "absolute", "none"]
    offset_days: int | None
    due_date: date | None
    due_manually_set: bool
    is_overdue: bool
    assignee_user_id: UUID | None
    helper_id: UUID | None = Field(description="Pomocnik bez konta, który widzi zadanie na linku")
    parent_task_id: UUID | None
    depends_on: list[UUID]
    vendor_id: UUID | None
    source: str
    template_code: str | None
    tip: str | None = Field(description="Wskazówka z szablonu (nie porada prawna)")
    vendor_category: str | None = Field(
        description="Kategoria usługodawcy, którego dotyczy zadanie z szablonu"
    )
    completed_at: datetime | None
    version: int
    updated_at: datetime


class RescheduleIn(BaseModel):
    wedding_date: date | None = None
    planned_month: PlannedMonth | None = None
    dry_run: bool = True

    @model_validator(mode="after")
    def _exactly_one(self) -> Self:
        if (self.wedding_date is None) == (self.planned_month is None):
            raise ValueError("Podaj dokładnie jedno: wedding_date albo planned_month.")
        check_wedding_dates(self.wedding_date, self.planned_month)
        return self


class TaskDateChange(BaseModel):
    task_id: UUID
    title: str
    old_due_date: date | None
    new_due_date: date
    becomes_overdue: bool


class RescheduleOut(BaseModel):
    dry_run: bool
    wedding_date: date | None
    planned_month: str | None
    changes: list[TaskDateChange]
    kept_manual: int = Field(description="Zadania z ręcznie ustawionym terminem: bez zmian")
    kept_finished: int = Field(description="Zadania zakończone lub pominięte: bez zmian")
    note: str = (
        "Przesunięto tylko otwarte zadania z terminem liczonym od daty ślubu. "
        "Terminy płatności i zadania z ręcznym terminem nie są zmieniane automatycznie."
    )


class DryRunIn(BaseModel):
    dry_run: bool = True


class CatchUpOut(BaseModel):
    dry_run: bool
    changes: list[TaskDateChange]
    note: str = (
        "Zaległe zadania z planu przygotowań dostają nowe terminy w najbliższych tygodniach. "
        "Terminy dalej liczą się od daty ślubu; zadania z ręcznym terminem zostają bez zmian."
    )


class TemplateTaskPreview(BaseModel):
    code: str
    title: str
    parent_code: str | None


class SkippedTaskPreview(BaseModel):
    task_id: UUID
    title: str


class SyncTemplateOut(BaseModel):
    dry_run: bool
    template_version: str
    to_add: list[TemplateTaskPreview]
    to_skip: list[SkippedTaskPreview] = Field(
        description="Zadania niepasujące do typu ceremonii: zostaną pominięte (nie usunięte)"
    )


# --- licznik ważności dokumentów do ślubu -----------------------------------------------

DocStatus = Literal["no_date", "too_early", "now", "late", "ok", "expires", "done"]


class CeremonyDocumentOut(BaseModel):
    code: str
    title: str
    hint: str
    source: str = Field(description="Źródło zasady (adres strony)")
    source_label: str
    has_validity: bool = Field(description="Dokument ma termin ważności (data wydania)")
    editable_validity: bool = Field(description="Ważność zależy od parafii i można ją zmienić")
    valid_months: int | None
    earliest: date | None = Field(description="Najwcześniej (żeby był ważny w dniu ślubu)")
    latest: date | None = Field(description="Najpóźniej")
    issued_on: date | None
    expires_on: date | None
    done: bool
    status: DocStatus


class CeremonyDocumentsOut(BaseModel):
    ceremony_type: str
    wedding_day: date | None
    approximate: bool = Field(description="Data przybliżona (tylko planowany miesiąc)")
    items: list[CeremonyDocumentOut]


class CeremonyDocumentIn(BaseModel):
    issued_on: date | None = None
    done: bool = False
    valid_months: int | None = Field(default=None, ge=1, le=24)


# --- pomocnicy bez konta ---------------------------------------------------------------------


class HelperIn(BaseModel):
    name: str = Field(min_length=1, max_length=80, examples=["Tata — kierowcy"])


class HelperOut(BaseModel):
    id: UUID
    name: str
    has_link: bool
    last_used_at: datetime | None = Field(description="Kiedy pomocnik ostatnio otworzył link")
    open_tasks: int
    done_tasks: int


class HelperLink(BaseModel):
    helper_id: UUID
    token: str = Field(description="Pokazywany tylko raz; w bazie tylko hash")
    url: str


class TaskHelperIn(BaseModel):
    helper_id: UUID | None = Field(description="null = bez pomocnika")


class HelperTask(BaseModel):
    id: UUID
    title: str
    description: str | None
    due_date: date | None
    done: bool


class HelperView(BaseModel):
    helper_name: str
    wedding_name: str
    wedding_date: date | None
    tasks: list[HelperTask]


class HelperDoneIn(BaseModel):
    done: bool


class CommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class CommentOut(BaseModel):
    id: UUID
    text: str
    author_user_id: UUID | None
    author_name: str
    created_at: datetime
    mine: bool
