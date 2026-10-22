"""Zadania dla bliskich bez konta: pomocnik dostaje link tylko ze swoimi zadaniami i je odhacza.

Para tworzy pomocnika (np. „Tata — kierowcy”), przypisuje mu zadania i wysyła link (SMS,
komunikator — sami). Pomocnik nie zakłada konta: widzi tytuł, opis i termin swoich zadań,
może je oznaczyć jako zrobione. Nie widzi budżetu, gości ani zadań innych osób. W bazie tylko
hash tokenu; nowy link unieważnia poprzedni, usunięcie pomocnika zwalnia jego zadania.
"""

from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import ratelimit
from app.core.config import get_settings
from app.core.db import utcnow
from app.core.errors import NotFound, Unprocessable
from app.core.security import hash_token, new_token
from app.modules.audit import service as audit
from app.modules.identity.service import Principal
from app.modules.planner.models import Helper, Task
from app.modules.workspace.models import Wedding
from app.modules.workspace.permissions import Action, authorize

OPEN = ("todo", "in_progress")


def _record(
    db: Session,
    wedding_id: UUID,
    entity_type: str,
    entity_id: UUID,
    action: str,
    principal: Principal | None = None,
    changes: dict[str, Any] | None = None,
) -> None:
    audit.record(
        db,
        actor_type="user" if principal else "guest",
        actor_id=principal.user.id if principal else None,
        entity_type=entity_type,
        entity_id=entity_id,
        wedding_id=wedding_id,
        action=action,
        changes=changes,
    )


def _helper(db: Session, wedding_id: UUID, helper_id: UUID) -> Helper:
    h = db.get(Helper, helper_id)
    if h is None or h.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono pomocnika.", code="helper.not_found")
    return h


def list_helpers(db: Session, principal: Principal, wedding_id: UUID) -> list[dict[str, Any]]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    helpers = list(
        db.scalars(select(Helper).where(Helper.wedding_id == wedding_id).order_by(Helper.name))
    )
    counts = {
        helper_id: (open_n, done_n)
        for helper_id, open_n, done_n in db.execute(
            select(
                Task.helper_id,
                func.count().filter(Task.status.in_(OPEN)),
                func.count().filter(Task.status == "done"),
            )
            .where(Task.wedding_id == wedding_id, Task.helper_id.is_not(None))
            .group_by(Task.helper_id)
        )
    }
    return [
        {
            "id": h.id,
            "name": h.name,
            "has_link": h.token_hash is not None,
            "last_used_at": h.last_used_at,
            "open_tasks": counts.get(h.id, (0, 0))[0],
            "done_tasks": counts.get(h.id, (0, 0))[1],
        }
        for h in helpers
    ]


def _issue_link(h: Helper) -> dict[str, Any]:
    token, token_hash = new_token()
    h.token_hash = token_hash
    h.last_used_at = None
    return {"token": token, "url": f"{get_settings().public_app_url}/pomocnik/{token}"}


def create(db: Session, principal: Principal, wedding_id: UUID, name: str) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    h = Helper(wedding_id=wedding_id, name=name.strip())
    db.add(h)
    link = _issue_link(h)
    db.flush()
    _record(db, wedding_id, "helper", h.id, "create", principal)
    db.commit()
    return {"helper_id": h.id, **link}


def new_link(
    db: Session, principal: Principal, wedding_id: UUID, helper_id: UUID
) -> dict[str, Any]:
    """Nowy link — poprzedni przestaje działać. Token widoczny tylko raz."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    h = _helper(db, wedding_id, helper_id)
    link = _issue_link(h)
    _record(db, wedding_id, "helper", h.id, "new_link", principal)
    db.commit()
    return {"helper_id": h.id, **link}


def delete(db: Session, principal: Principal, wedding_id: UUID, helper_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    db.delete(_helper(db, wedding_id, helper_id))  # zadania zostają, bez pomocnika (SET NULL)
    _record(db, wedding_id, "helper", helper_id, "delete", principal)
    db.commit()


def assign(
    db: Session, principal: Principal, wedding_id: UUID, task_id: UUID, helper_id: UUID | None
) -> Task:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    task = db.get(Task, task_id)
    if task is None or task.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono zadania.", code="task.not_found")
    if helper_id is not None:
        h = db.get(Helper, helper_id)
        if h is None or h.wedding_id != wedding_id:
            raise Unprocessable("Nie ma takiego pomocnika.", code="helper.unknown")
    old = task.helper_id
    task.helper_id = helper_id
    _record(
        db,
        wedding_id,
        "task",
        task.id,
        "helper",
        principal,
        {"helper_id": [str(old) if old else None, str(helper_id) if helper_id else None]},
    )
    db.commit()
    return task


# --- link pomocnika (publiczny) --------------------------------------------------------------


def _by_token(db: Session, token: str, ip: str) -> Helper:
    ratelimit.hit(db, ratelimit.key_for("helper:ip", ip), 120, timedelta(minutes=10))
    db.commit()
    h = db.scalars(select(Helper).where(Helper.token_hash == hash_token(token))).first()
    if h is None:
        raise NotFound("Link nieprawidłowy lub wyłączony.", code="helper_link.not_found")
    return h


def public_view(db: Session, token: str, ip: str) -> dict[str, Any]:
    h = _by_token(db, token, ip)
    h.last_used_at = utcnow()
    wedding = db.get_one(Wedding, h.wedding_id)
    tasks = list(
        db.scalars(
            select(Task)
            .where(Task.helper_id == h.id, Task.status != "skipped")
            .order_by(Task.status == "done", Task.due_date.asc().nulls_last(), Task.title)
        )
    )
    db.commit()
    return {
        "helper_name": h.name,
        "wedding_name": wedding.name,
        "wedding_date": wedding.wedding_date,
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "due_date": t.due_date,
                "done": t.status == "done",
            }
            for t in tasks
        ],
    }


def public_done(db: Session, token: str, ip: str, task_id: UUID, done: bool) -> dict[str, Any]:
    h = _by_token(db, token, ip)
    task = db.get(Task, task_id)
    if task is None or task.helper_id != h.id:
        raise NotFound("Nie znaleziono zadania.", code="task.not_found")
    old = task.status
    task.status = "done" if done else "todo"
    task.completed_at = utcnow() if done else None
    _record(
        db,
        h.wedding_id,
        "task",
        task.id,
        "status",
        changes={"status": [old, task.status], "via": [None, "helper_link"]},
    )
    db.commit()
    return public_view(db, token, ip)
