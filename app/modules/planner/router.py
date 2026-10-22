from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response

from app.core.deps import CurrentPrincipal, DbSession, IfMatchVersion, etag
from app.core.net import ip_prefix
from app.core.schemas import Page
from app.modules.planner import comments, documents, helpers, service
from app.modules.planner.models import Task
from app.modules.planner.schemas import (
    CatchUpOut,
    CeremonyDocumentIn,
    CeremonyDocumentsOut,
    CommentIn,
    CommentOut,
    DryRunIn,
    HelperDoneIn,
    HelperIn,
    HelperLink,
    HelperOut,
    HelperView,
    RescheduleIn,
    RescheduleOut,
    SyncTemplateOut,
    TaskCreate,
    TaskHelperIn,
    TaskOut,
    TaskStatus,
    TaskUpdate,
)
from app.modules.planner.templates import TEMPLATE_VERSION, tip_for, vendor_category_for
from app.modules.workspace.service import month_to_date

router = APIRouter(tags=["planer"])

Responses = dict[int | str, dict[str, Any]]
_READ: Responses = {
    401: {"description": "Brak uwierzytelnienia"},
    404: {"description": "Nie znaleziono lub brak dostępu"},
}
_WRITE: Responses = {
    **_READ,
    403: {"description": "Rola tylko do odczytu"},
    422: {"description": "Błąd walidacji"},
}
_PATCH: Responses = {
    **_WRITE,
    409: {"description": "Konflikt wersji"},
    428: {"description": "Brak If-Match"},
}


def task_out(task: Task, depends_on: list[UUID]) -> TaskOut:
    return TaskOut.model_validate(
        {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "category": task.category,
            "priority": task.priority,
            "status": task.status,
            "due_mode": task.due_mode,
            "offset_days": task.offset_days,
            "due_date": task.due_date,
            "due_manually_set": task.due_manually_set,
            "is_overdue": service.is_overdue(task),
            "assignee_user_id": task.assignee_user_id,
            "helper_id": task.helper_id,
            "parent_task_id": task.parent_task_id,
            "depends_on": depends_on,
            "vendor_id": task.vendor_id,
            "source": task.source,
            "template_code": task.template_code,
            "tip": tip_for(task.template_code),
            "vendor_category": vendor_category_for(task.template_code),
            "completed_at": task.completed_at,
            "version": task.version,
            "updated_at": task.updated_at,
        }
    )


def _one(db: DbSession, task: Task) -> TaskOut:
    return task_out(task, service.dependencies_of(db, [task.id])[task.id])


@router.get(
    "/weddings/{wedding_id}/tasks",
    responses=_READ,
    summary="Zadania (filtry: status, kategoria, termin, osoba, po terminie)",
)
def list_tasks(
    wedding_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    status: TaskStatus | None = None,
    category: Annotated[str | None, Query(max_length=32)] = None,
    due_before: date | None = None,
    assignee: UUID | None = None,
    overdue: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    cursor: Annotated[str | None, Query(max_length=64)] = None,
) -> Page[TaskOut]:
    tasks, next_cursor = service.list_tasks(
        db,
        principal,
        wedding_id,
        status=status,
        category=category,
        due_before=due_before,
        assignee=assignee,
        overdue=overdue,
        limit=limit,
        cursor=cursor,
    )
    deps = service.dependencies_of(db, [t.id for t in tasks])
    return Page[TaskOut](items=[task_out(t, deps[t.id]) for t in tasks], next_cursor=next_cursor)


@router.post(
    "/weddings/{wedding_id}/tasks",
    status_code=201,
    responses=_WRITE,
    summary="Nowe zadanie (termin konkretny lub względny do daty ślubu)",
)
def create_task(
    wedding_id: UUID, body: TaskCreate, principal: CurrentPrincipal, db: DbSession
) -> TaskOut:
    return _one(db, service.create_task(db, principal, wedding_id, body.model_dump()))


@router.get("/weddings/{wedding_id}/tasks/{task_id}", responses=_READ, summary="Zadanie")
def get_task(
    wedding_id: UUID, task_id: UUID, principal: CurrentPrincipal, db: DbSession, response: Response
) -> TaskOut:
    task = service.get_task(db, principal, wedding_id, task_id)
    response.headers["ETag"] = etag(task.version)
    return _one(db, task)


@router.patch(
    "/weddings/{wedding_id}/tasks/{task_id}",
    responses=_PATCH,
    summary="Edycja zadania (ręczny termin nie będzie przesuwany automatycznie)",
)
def update_task(
    wedding_id: UUID,
    task_id: UUID,
    principal: CurrentPrincipal,
    body: TaskUpdate,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> TaskOut:
    task = service.update_task(
        db, principal, wedding_id, task_id, body.model_dump(exclude_unset=True), version
    )
    response.headers["ETag"] = etag(task.version)
    return _one(db, task)


@router.post(
    "/weddings/{wedding_id}/tasks/{task_id}/complete",
    responses=_WRITE,
    summary="Oznacz jako wykonane",
)
def complete_task(
    wedding_id: UUID, task_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> TaskOut:
    return _one(db, service.change_status(db, principal, wedding_id, task_id, "done"))


@router.post(
    "/weddings/{wedding_id}/tasks/{task_id}/reopen",
    responses=_WRITE,
    summary="Przywróć do wykonania",
)
def reopen_task(
    wedding_id: UUID, task_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> TaskOut:
    return _one(db, service.change_status(db, principal, wedding_id, task_id, "todo"))


@router.delete(
    "/weddings/{wedding_id}/tasks/{task_id}",
    status_code=204,
    responses=_WRITE,
    summary="Usuń zadanie",
)
def delete_task(
    wedding_id: UUID, task_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.delete_task(db, principal, wedding_id, task_id)


@router.put(
    "/weddings/{wedding_id}/tasks/{task_id}/dependencies/{depends_on_id}",
    responses={**_WRITE, 422: {"description": "Cykl zależności"}},
    summary="Zadanie zależy od innego zadania",
)
def add_dependency(
    wedding_id: UUID, task_id: UUID, depends_on_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> TaskOut:
    return _one(db, service.add_dependency(db, principal, wedding_id, task_id, depends_on_id))


@router.delete(
    "/weddings/{wedding_id}/tasks/{task_id}/dependencies/{depends_on_id}",
    status_code=204,
    responses=_WRITE,
    summary="Usuń zależność",
)
def remove_dependency(
    wedding_id: UUID, task_id: UUID, depends_on_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.remove_dependency(db, principal, wedding_id, task_id, depends_on_id)


@router.post(
    "/weddings/{wedding_id}/reschedule",
    responses=_PATCH,
    summary="Zmiana daty ślubu z podglądem przesunięć terminów (dry_run)",
)
def reschedule(
    wedding_id: UUID,
    principal: CurrentPrincipal,
    body: RescheduleIn,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> RescheduleOut:
    wedding, changes, kept_manual, kept_finished = service.reschedule(
        db,
        principal,
        wedding_id,
        wedding_date=body.wedding_date,
        planned_month=month_to_date(body.planned_month),
        dry_run=body.dry_run,
        version=version,
    )
    response.headers["ETag"] = etag(wedding.version)
    return RescheduleOut.model_validate(
        {
            "dry_run": body.dry_run,
            "wedding_date": body.wedding_date,
            "planned_month": body.planned_month,
            "changes": changes,
            "kept_manual": kept_manual,
            "kept_finished": kept_finished,
        }
    )


@router.post(
    "/weddings/{wedding_id}/tasks/catch-up",
    responses=_WRITE,
    summary="Rozłóż zaległe zadania z planu na najbliższe tygodnie (dry_run = podgląd)",
)
def catch_up(
    wedding_id: UUID, body: DryRunIn, principal: CurrentPrincipal, db: DbSession
) -> CatchUpOut:
    changes = service.catch_up(db, principal, wedding_id, dry_run=body.dry_run)
    return CatchUpOut.model_validate({"dry_run": body.dry_run, "changes": changes})


@router.post(
    "/weddings/{wedding_id}/tasks/sync-template",
    responses=_WRITE,
    summary="Uzupełnij plan z szablonu (nowe zadania, niepasujące do ceremonii pomiń)",
)
def sync_template(
    wedding_id: UUID, body: DryRunIn, principal: CurrentPrincipal, db: DbSession
) -> SyncTemplateOut:
    to_add, to_skip = service.sync_template(db, principal, wedding_id, dry_run=body.dry_run)
    return SyncTemplateOut.model_validate(
        {
            "dry_run": body.dry_run,
            "template_version": TEMPLATE_VERSION,
            "to_add": [{"code": t.code, "title": t.title, "parent_code": t.parent} for t in to_add],
            "to_skip": [{"task_id": t.id, "title": t.title} for t in to_skip],
        }
    )


# --- licznik ważności dokumentów do ślubu -----------------------------------------------


@router.get(
    "/weddings/{wedding_id}/ceremony-documents",
    responses=_READ,
    summary="Dokumenty do ślubu: kiedy najwcześniej i najpóźniej, czy będą ważne w dniu ślubu",
)
def ceremony_documents(
    wedding_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> CeremonyDocumentsOut:
    return CeremonyDocumentsOut.model_validate(documents.overview(db, principal, wedding_id))


@router.put(
    "/weddings/{wedding_id}/ceremony-documents/{code}",
    responses=_WRITE,
    summary="Data wydania / „zrobione” / ważność wg parafii dla dokumentu do ślubu",
)
def save_ceremony_document(
    wedding_id: UUID,
    code: str,
    body: CeremonyDocumentIn,
    principal: CurrentPrincipal,
    db: DbSession,
) -> CeremonyDocumentsOut:
    documents.save(db, principal, wedding_id, code, body.model_dump())
    return CeremonyDocumentsOut.model_validate(documents.overview(db, principal, wedding_id))


# --- pomocnicy bez konta ---------------------------------------------------------------------

HL = "/weddings/{wedding_id}/helpers"
public_router = APIRouter(prefix="/helper", tags=["pomocnik (publiczne)"])
_PUBLIC: Responses = {
    404: {"description": "Link nieprawidłowy lub wyłączony"},
    429: {"description": "Za dużo prób"},
}


@router.get(HL, responses=_READ, summary="Pomocnicy bez konta i ich zadania (liczby)")
def list_helpers(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> list[HelperOut]:
    return [HelperOut.model_validate(h) for h in helpers.list_helpers(db, principal, wedding_id)]


@router.post(HL, status_code=201, responses=_WRITE, summary="Nowy pomocnik z linkiem (raz)")
def create_helper(
    wedding_id: UUID, body: HelperIn, principal: CurrentPrincipal, db: DbSession
) -> HelperLink:
    return HelperLink.model_validate(helpers.create(db, principal, wedding_id, body.name))


@router.post(
    f"{HL}/{{helper_id}}/link", responses=_WRITE, summary="Nowy link (poprzedni przestaje działać)"
)
def new_helper_link(
    wedding_id: UUID, helper_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> HelperLink:
    return HelperLink.model_validate(helpers.new_link(db, principal, wedding_id, helper_id))


@router.delete(
    f"{HL}/{{helper_id}}", status_code=204, responses=_WRITE, summary="Usunięcie pomocnika"
)
def delete_helper(
    wedding_id: UUID, helper_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    helpers.delete(db, principal, wedding_id, helper_id)


@router.put(
    "/weddings/{wedding_id}/tasks/{task_id}/helper",
    responses=_WRITE,
    summary="Przypisanie zadania pomocnikowi bez konta",
)
def assign_helper(
    wedding_id: UUID, task_id: UUID, body: TaskHelperIn, principal: CurrentPrincipal, db: DbSession
) -> TaskOut:
    task = helpers.assign(db, principal, wedding_id, task_id, body.helper_id)
    return task_out(task, service.dependencies_of(db, [task.id]).get(task.id, []))


@public_router.get("/{token}", responses=_PUBLIC, summary="Zadania pomocnika (bez logowania)")
def helper_view(token: str, request: Request, db: DbSession) -> HelperView:
    return HelperView.model_validate(helpers.public_view(db, token, ip_prefix(request)))


@public_router.put(
    "/{token}/tasks/{task_id}/done", responses=_PUBLIC, summary="Pomocnik odhacza zadanie"
)
def helper_done(
    token: str, task_id: UUID, body: HelperDoneIn, request: Request, db: DbSession
) -> HelperView:
    return HelperView.model_validate(
        helpers.public_done(db, token, ip_prefix(request), task_id, body.done)
    )


# --- komentarze przy zadaniach ------------------------------------------------------------------

TC = "/weddings/{wedding_id}/tasks/{task_id}/comments"


@router.get(TC, responses=_READ, summary="Komentarze przy zadaniu")
def list_comments(
    wedding_id: UUID, task_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> list[CommentOut]:
    return [
        CommentOut.model_validate(c)
        for c in comments.list_comments(db, principal, wedding_id, task_id)
    ]


@router.post(TC, status_code=201, responses=_WRITE, summary="Nowy komentarz")
def add_comment(
    wedding_id: UUID, task_id: UUID, body: CommentIn, principal: CurrentPrincipal, db: DbSession
) -> list[CommentOut]:
    return [
        CommentOut.model_validate(c)
        for c in comments.add(db, principal, wedding_id, task_id, body.text)
    ]


@router.delete(
    f"{TC}/{{comment_id}}",
    status_code=204,
    responses={**_WRITE, 403: {"description": "Usuwa autor albo właściciel"}},
    summary="Usunięcie komentarza",
)
def delete_comment(
    wedding_id: UUID, task_id: UUID, comment_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    comments.delete(db, principal, wedding_id, task_id, comment_id)
