"""Planer: zadania z szablonu, terminy względne/bezwzględne, zależności, przeliczanie terminów."""

import math
from collections import defaultdict
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core import clock
from app.core.db import utcnow
from app.core.errors import Conflict, NotFound, Unprocessable
from app.core.ids import uuid7
from app.core.schemas import decode_cursor, encode_cursor
from app.modules.audit import service as audit
from app.modules.identity.service import Principal
from app.modules.planner.models import Task, TaskDependency
from app.modules.planner.templates import (
    BY_CODE,
    ORDER,
    TEMPLATE_VERSION,
    TaskTemplate,
    templates_for,
)
from app.modules.vendors.models import Vendor
from app.modules.workspace.models import Wedding, WeddingMember
from app.modules.workspace.permissions import Action, authorize

OPEN_STATUSES = ("todo", "in_progress")


def wedding_anchor(wedding: Wedding) -> date | None:
    """Data odniesienia dla terminów względnych: data ślubu albo 1. dzień planowanego miesiąca."""
    return wedding.wedding_date or wedding.planned_month


def _relative_date(anchor: date | None, offset: int | None) -> date | None:
    if anchor is None or offset is None:
        return None
    return anchor + timedelta(days=offset)


def is_overdue(task: Task) -> bool:
    return (
        task.status in OPEN_STATUSES
        and task.due_date is not None
        and (task.due_date < clock.today())
    )


def _conflict() -> Conflict:
    return Conflict(
        "Zadanie zmieniło się w międzyczasie. Pobierz aktualną wersję.",
        code="conflict.version_mismatch",
    )


# --- integracja z modułem workspace --------------------------------------------------------


def generate_for_wedding(db: Session, wedding: Wedding) -> int:
    """Zadania z szablonu dla nowego wesela (deterministycznie, bez AI)."""
    templates = templates_for(wedding.ceremony_type)
    _create_from_templates(db, wedding, templates, {})
    return len(templates)


def _create_from_templates(
    db: Session, wedding: Wedding, templates: list[TaskTemplate], existing: dict[str, Task]
) -> list[Task]:
    """Tworzy zadania z szablonu (z podzadaniami i zależnościami) i rozkłada zaległe.

    Identyfikatory i terminy ustalane są przed zapisem, żeby nowe zadania miały wersję 1.
    """
    anchor = wedding_anchor(wedding)
    created: dict[str, Task] = {}
    for t in templates:
        parent = created.get(t.parent) or existing.get(t.parent) if t.parent else None
        task = Task(
            id=uuid7(),
            wedding_id=wedding.id,
            parent_task_id=parent.id if parent else None,
            template_code=t.code,
            template_version=TEMPLATE_VERSION,
            title=t.title,
            category=t.category,
            priority=t.priority,
            status="todo",  # wartości domyślne kolumn są potrzebne przed zapisem
            due_mode="relative",
            offset_days=t.offset_days,
            due_date=_relative_date(anchor, t.offset_days),
            due_manually_set=False,
            source="template",
        )
        created[t.code] = task
    tasks = list(created.values())
    if anchor is not None:
        _apply_catch_up(_catch_up_plan(tasks, anchor, clock.today()), tasks, anchor)
    db.add_all(tasks)
    db.flush()
    known = {**existing, **created}
    for t in templates:
        for dep in t.depends_on:
            if dep in known:
                db.add(TaskDependency(task_id=created[t.code].id, depends_on_task_id=known[dep].id))
    db.flush()
    return tasks


# --- nadrabianie zaległości ------------------------------------------------------------------

CATCH_UP_MIN_DAYS = 14
CATCH_UP_MAX_DAYS = 60


def catch_up_dates(anchor: date, today: date, count: int) -> list[date]:
    """Terminy dla `count` zaległych zadań, równo rozłożone od jutra.

    Okno to ćwierć czasu do ślubu, ale 14-60 dni i zawsze przed dniem ślubu. Para, która
    zaczyna planować późno, dostaje plan na najbliższe tygodnie zamiast listy „po terminie”.
    """
    days_left = (anchor - today).days
    if count == 0:
        return []
    if days_left <= 1:
        return [today] * count
    window = min(max(CATCH_UP_MIN_DAYS, days_left // 4), CATCH_UP_MAX_DAYS, days_left - 1)
    return [
        today + timedelta(days=max(1, math.ceil((i + 1) * window / count))) for i in range(count)
    ]


def _catch_up_plan(tasks: list[Task], anchor: date, today: date) -> list[tuple[Task, date]]:
    """Zaległe zadania nadrzędne (otwarte, liczone od daty ślubu) i ich nowe terminy.

    Kolejność wg pierwotnego terminu i priorytetu zachowuje kolejność zależności z szablonu.
    """
    late = sorted(
        (
            t
            for t in tasks
            if t.parent_task_id is None
            and t.status in OPEN_STATUSES
            and t.due_mode == "relative"
            and not t.due_manually_set
            and t.due_date is not None
            and t.due_date < today
        ),
        key=lambda t: (t.offset_days or 0, t.priority),
    )
    return list(zip(late, catch_up_dates(anchor, today, len(late)), strict=True))


def _apply_catch_up(plan: list[tuple[Task, date]], tasks: list[Task], anchor: date) -> None:
    """Nowy termin zostaje względny (przesunie się ze zmianą daty ślubu); podzadania razem."""
    children: dict[UUID, list[Task]] = defaultdict(list)
    for t in tasks:
        if t.parent_task_id is not None:
            children[t.parent_task_id].append(t)
    for task, new_due in plan:
        for t in [task, *children.get(task.id, [])]:
            if t is task or (t.status in OPEN_STATUSES and not t.due_manually_set):
                t.due_date = new_due
                t.offset_days = (new_due - anchor).days


def catch_up(
    db: Session, principal: Principal, wedding_id: UUID, *, dry_run: bool
) -> list[dict[str, Any]]:
    """Rozłożenie zaległych zadań na najbliższe tygodnie (podgląd albo zapis)."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    wedding = db.get_one(Wedding, wedding_id)
    anchor = wedding_anchor(wedding)
    if anchor is None:
        return []
    tasks = list(db.scalars(select(Task).where(Task.wedding_id == wedding_id)))
    plan = _catch_up_plan(tasks, anchor, clock.today())
    changes = [
        {
            "task_id": t.id,
            "title": t.title,
            "old_due_date": t.due_date,
            "new_due_date": d,
            "becomes_overdue": False,
        }
        for t, d in plan
    ]
    if dry_run or not plan:
        return changes
    _apply_catch_up(plan, tasks, anchor)
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="wedding",
        entity_id=wedding_id,
        wedding_id=wedding_id,
        action="tasks_catch_up",
        changes={"tasks_moved": [None, len(plan)]},
    )
    db.commit()
    return changes


# --- uzupełnianie z szablonu -----------------------------------------------------------------


def sync_template(
    db: Session, principal: Principal, wedding_id: UUID, *, dry_run: bool
) -> tuple[list[TaskTemplate], list[Task]]:
    """Brakujące zadania z szablonu (po zmianie typu ceremonii lub nowej wersji szablonu)
    oraz otwarte zadania szablonowe, które nie dotyczą już tej ceremonii (do pominięcia).

    Nic nie jest usuwane: niepasujące zadania dostają status „pominięte” i da się je przywrócić.
    """
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    wedding = db.get_one(Wedding, wedding_id)
    tasks = list(db.scalars(select(Task).where(Task.wedding_id == wedding_id)))
    existing = {t.template_code: t for t in tasks if t.template_code}
    applicable = templates_for(wedding.ceremony_type)
    applicable_codes = {t.code for t in applicable}
    to_add = [t for t in applicable if t.code not in existing]
    to_skip = [
        t
        for t in tasks
        if t.source == "template"
        and t.template_code in BY_CODE
        and t.template_code not in applicable_codes
        and t.status == "todo"
    ]
    if dry_run or not (to_add or to_skip):
        return to_add, to_skip
    _create_from_templates(db, wedding, to_add, existing)
    for t in to_skip:
        _set_status(t, "skipped")
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="wedding",
        entity_id=wedding_id,
        wedding_id=wedding_id,
        action="tasks_sync_template",
        changes={"added": [None, len(to_add)], "skipped": [None, len(to_skip)]},
    )
    db.commit()
    return to_add, to_skip


def _open_relative_tasks(db: Session, wedding_id: UUID) -> list[Task]:
    return list(
        db.scalars(
            select(Task).where(
                Task.wedding_id == wedding_id,
                Task.due_mode == "relative",
                Task.status.in_(OPEN_STATUSES),
                Task.due_manually_set.is_(False),
            )
        )
    )


def on_anchor_change(db: Session, wedding: Wedding, old_anchor: date | None) -> None:
    """Wywoływane przy zmianie daty w PATCH /weddings/{id}.

    Pierwsze ustalenie daty uzupełnia terminy. Zmiana istniejącej daty wymaga świadomej
    decyzji przez /reschedule (podgląd zmian), więc PATCH jest wtedy odrzucany.
    """
    new_anchor = wedding_anchor(wedding)
    if new_anchor == old_anchor:
        return
    tasks = _open_relative_tasks(db, wedding.id)
    if old_anchor is not None and any(t.due_date is not None for t in tasks):
        raise Conflict(
            "Zmiana daty ślubu przesuwa terminy zadań. Użyj POST /weddings/{id}/reschedule, "
            "aby zobaczyć podgląd zmian i je zatwierdzić.",
            code="wedding.reschedule_required",
        )
    for task in tasks:
        task.due_date = _relative_date(new_anchor, task.offset_days)


# --- zadania ----------------------------------------------------------------------------


def _get(db: Session, wedding_id: UUID, task_id: UUID) -> Task:
    task = db.get(Task, task_id)
    if task is None or task.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono zadania.", code="task.not_found")
    return task


def dependencies_of(db: Session, task_ids: list[UUID]) -> dict[UUID, list[UUID]]:
    result: dict[UUID, list[UUID]] = defaultdict(list)
    if not task_ids:
        return result
    for dep in db.scalars(select(TaskDependency).where(TaskDependency.task_id.in_(task_ids))):
        result[dep.task_id].append(dep.depends_on_task_id)
    return result


def list_tasks(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    *,
    status: str | None,
    category: str | None,
    due_before: date | None,
    assignee: UUID | None,
    overdue: bool | None,
    limit: int,
    cursor: str | None,
) -> tuple[list[Task], str | None]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    stmt = select(Task).where(Task.wedding_id == wedding_id)
    if status:
        stmt = stmt.where(Task.status == status)
    if category:
        stmt = stmt.where(Task.category == category)
    if due_before:
        stmt = stmt.where(Task.due_date <= due_before)
    if assignee:
        stmt = stmt.where(Task.assignee_user_id == assignee)
    if overdue is True:
        stmt = stmt.where(Task.status.in_(OPEN_STATUSES), Task.due_date < clock.today())
    if cursor:
        stmt = stmt.where(Task.id > decode_cursor(cursor))
    rows = list(db.scalars(stmt.order_by(Task.id).limit(limit + 1)))
    next_cursor = encode_cursor(rows[limit - 1].id) if len(rows) > limit else None
    rows = rows[:limit]
    # Przy tym samym terminie i priorytecie: kolejność z szablonu (np. lista dokumentów).
    rows.sort(
        key=lambda t: (
            t.due_date is None,
            t.due_date or date.max,
            t.priority,
            ORDER.get(t.template_code or "", len(ORDER)),
        )
    )
    return rows, next_cursor


def _check_assignee(db: Session, wedding_id: UUID, user_id: UUID | None) -> None:
    if user_id is not None and db.get(WeddingMember, (wedding_id, user_id)) is None:
        raise Unprocessable(
            "Osoba odpowiedzialna musi być członkiem wesela.", code="task.invalid_assignee"
        )


def _check_vendor(db: Session, wedding_id: UUID, vendor_id: UUID | None) -> None:
    if vendor_id is None:
        return
    vendor = db.get(Vendor, vendor_id)
    if vendor is None or vendor.wedding_id != wedding_id:
        raise Unprocessable("Usługodawca musi należeć do tego wesela.", code="task.invalid_vendor")


def create_task(db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]) -> Task:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    wedding = db.get_one(Wedding, wedding_id)
    _check_assignee(db, wedding_id, data.get("assignee_user_id"))
    _check_vendor(db, wedding_id, data.get("vendor_id"))
    if data.get("parent_task_id"):
        _get(db, wedding_id, data["parent_task_id"])
    task = Task(wedding_id=wedding_id, source="user", **data)
    if data.get("offset_days") is not None:
        task.due_mode = "relative"
        task.due_date = _relative_date(wedding_anchor(wedding), task.offset_days)
    elif data.get("due_date") is not None:
        task.due_mode = "absolute"
        task.due_manually_set = True
    db.add(task)
    db.flush()
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="task",
        entity_id=task.id,
        wedding_id=wedding_id,
        action="create",
    )
    db.commit()
    return task


def get_task(db: Session, principal: Principal, wedding_id: UUID, task_id: UUID) -> Task:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return _get(db, wedding_id, task_id)


def _set_status(task: Task, status: str) -> None:
    task.status = status
    task.completed_at = utcnow() if status == "done" else None


def update_task(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    task_id: UUID,
    data: dict[str, Any],
    version: int,
) -> Task:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    task = _get(db, wedding_id, task_id)
    if task.version != version:
        raise _conflict()
    wedding = db.get_one(Wedding, wedding_id)
    if "assignee_user_id" in data:
        _check_assignee(db, wedding_id, data["assignee_user_id"])
    if "vendor_id" in data:
        _check_vendor(db, wedding_id, data["vendor_id"])
    before = {k: getattr(task, k, None) for k in data}
    clear_due = data.pop("clear_due", False)
    nullable = ("description", "assignee_user_id", "vendor_id")
    for key in ("title", "description", "category", "priority", "assignee_user_id", "vendor_id"):
        if key in data and (data[key] is not None or key in nullable):
            setattr(task, key, data[key])
    if data.get("status"):
        _set_status(task, data["status"])
    if clear_due:
        task.due_mode, task.offset_days, task.due_date = "none", None, None
        task.due_manually_set = True
    elif data.get("due_date") is not None:
        task.due_mode, task.offset_days, task.due_date = "absolute", None, data["due_date"]
        task.due_manually_set = True  # ręczny termin nie jest przesuwany automatycznie
    elif data.get("offset_days") is not None:
        task.due_mode, task.offset_days = "relative", data["offset_days"]
        task.due_date = _relative_date(wedding_anchor(wedding), task.offset_days)
        task.due_manually_set = False
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="task",
        entity_id=task.id,
        wedding_id=wedding_id,
        action="update",
        changes=audit.diff(before, {k: getattr(task, k, None) for k in before}),
    )
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise _conflict() from exc
    return task


def change_status(
    db: Session, principal: Principal, wedding_id: UUID, task_id: UUID, status: str
) -> Task:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    task = _get(db, wedding_id, task_id)
    old = task.status
    _set_status(task, status)
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="task",
        entity_id=task.id,
        wedding_id=wedding_id,
        action="status",
        changes={"status": [old, status]},
    )
    db.commit()
    return task


def delete_task(db: Session, principal: Principal, wedding_id: UUID, task_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    task = _get(db, wedding_id, task_id)
    db.delete(task)
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="task",
        entity_id=task_id,
        wedding_id=wedding_id,
        action="delete",
    )
    db.commit()


# --- zależności -------------------------------------------------------------------------


def _creates_cycle(db: Session, task_id: UUID, depends_on: UUID) -> bool:
    """Czy dodanie krawędzi task → depends_on tworzy cykl (DFS po zależnościach)."""
    stack, seen = [depends_on], set()
    while stack:
        current = stack.pop()
        if current == task_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(
            db.scalars(
                select(TaskDependency.depends_on_task_id).where(TaskDependency.task_id == current)
            )
        )
    return False


def add_dependency(
    db: Session, principal: Principal, wedding_id: UUID, task_id: UUID, depends_on_id: UUID
) -> Task:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    task = _get(db, wedding_id, task_id)
    _get(db, wedding_id, depends_on_id)
    if db.get(TaskDependency, (task_id, depends_on_id)) is not None:
        return task
    if task_id == depends_on_id or _creates_cycle(db, task_id, depends_on_id):
        raise Unprocessable("Ta zależność utworzyłaby cykl.", code="task.dependency_cycle")
    db.add(TaskDependency(task_id=task_id, depends_on_task_id=depends_on_id))
    db.commit()
    return task


def remove_dependency(
    db: Session, principal: Principal, wedding_id: UUID, task_id: UUID, depends_on_id: UUID
) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    _get(db, wedding_id, task_id)
    dep = db.get(TaskDependency, (task_id, depends_on_id))
    if dep is None:
        raise NotFound("Nie znaleziono zależności.", code="task.dependency_not_found")
    db.delete(dep)
    db.commit()


# --- zmiana daty ślubu -------------------------------------------------------------------


def reschedule(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    *,
    wedding_date: date | None,
    planned_month: date | None,
    dry_run: bool,
    version: int,
) -> tuple[Wedding, list[dict[str, Any]], int, int]:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    wedding = db.get_one(Wedding, wedding_id)
    if wedding.version != version:
        raise Conflict("Dane wesela zmieniły się w międzyczasie.", code="conflict.version_mismatch")
    if wedding_date is not None and wedding_date < clock.today():
        raise Unprocessable("Data ślubu nie może być w przeszłości.", code="wedding.date_in_past")
    new_anchor = wedding_date or planned_month
    today = clock.today()
    all_tasks = list(db.scalars(select(Task).where(Task.wedding_id == wedding_id)))
    changes: list[dict[str, Any]] = []
    kept_manual = kept_finished = 0
    for task in all_tasks:
        if task.due_mode != "relative":
            if task.due_mode == "absolute":
                kept_manual += 1
            continue
        if task.status not in OPEN_STATUSES:
            kept_finished += 1
            continue
        if task.due_manually_set:
            kept_manual += 1
            continue
        new_due = _relative_date(new_anchor, task.offset_days)
        if new_due is not None and new_due != task.due_date:
            changes.append(
                {
                    "task": task,
                    "task_id": task.id,
                    "title": task.title,
                    "old_due_date": task.due_date,
                    "new_due_date": new_due,
                    "becomes_overdue": new_due < today,
                }
            )
    if not dry_run:
        old = {"wedding_date": wedding.wedding_date, "planned_month": wedding.planned_month}
        wedding.wedding_date = wedding_date
        wedding.planned_month = planned_month if wedding_date is None else None
        for change in changes:
            change["task"].due_date = change["new_due_date"]
        audit.record(
            db,
            actor_type="user",
            actor_id=principal.user.id,
            entity_type="wedding",
            entity_id=wedding_id,
            wedding_id=wedding_id,
            action="reschedule",
            changes={
                **audit.diff(
                    old,
                    {"wedding_date": wedding.wedding_date, "planned_month": wedding.planned_month},
                ),
                "tasks_moved": [None, len(changes)],
            },
        )
        try:
            db.commit()
        except StaleDataError as exc:
            db.rollback()
            raise Conflict(
                "Dane wesela zmieniły się w międzyczasie.", code="conflict.version_mismatch"
            ) from exc
    else:
        db.rollback()
    for change in changes:
        change.pop("task")
    return wedding, changes, kept_manual, kept_finished
