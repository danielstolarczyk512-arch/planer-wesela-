"""Komentarze przy zadaniach: krótka rozmowa pary i współorganizatorów, żeby ustalenia nie ginęły
w komunikatorach. Czytają wszyscy z odczytem planu; piszą role z prawem zapisu; usuwa autor albo
właściciel wesela."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Forbidden, NotFound
from app.modules.audit import service as audit
from app.modules.identity.models import User
from app.modules.identity.service import Principal
from app.modules.planner.models import Task, TaskComment
from app.modules.workspace.permissions import Action, authorize


def _task(db: Session, wedding_id: UUID, task_id: UUID) -> Task:
    t = db.get(Task, task_id)
    if t is None or t.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono zadania.", code="task.not_found")
    return t


def list_comments(
    db: Session, principal: Principal, wedding_id: UUID, task_id: UUID
) -> list[dict[str, Any]]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    _task(db, wedding_id, task_id)
    rows = db.execute(
        select(TaskComment, User.display_name, User.email)
        .outerjoin(User, User.id == TaskComment.author_user_id)
        .where(TaskComment.task_id == task_id)
        .order_by(TaskComment.created_at)
    )
    return [
        {
            "id": c.id,
            "text": c.text,
            "author_user_id": c.author_user_id,
            "author_name": name or (email.split("@")[0] if email else "konto usunięte"),
            "created_at": c.created_at,
            "mine": c.author_user_id == principal.user.id,
        }
        for c, name, email in rows
    ]


def add(
    db: Session, principal: Principal, wedding_id: UUID, task_id: UUID, text: str
) -> list[dict[str, Any]]:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    _task(db, wedding_id, task_id)
    c = TaskComment(
        task_id=task_id, wedding_id=wedding_id, author_user_id=principal.user.id, text=text.strip()
    )
    db.add(c)
    db.flush()
    # Bez treści w audycie (może zawierać dane osobowe): tylko fakt dodania.
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="task_comment",
        entity_id=c.id,
        wedding_id=wedding_id,
        action="create",
    )
    db.commit()
    return list_comments(db, principal, wedding_id, task_id)


def delete(
    db: Session, principal: Principal, wedding_id: UUID, task_id: UUID, comment_id: UUID
) -> None:
    member = authorize(db, principal.user.id, wedding_id, Action.WRITE)
    c = db.get(TaskComment, comment_id)
    if c is None or c.task_id != task_id or c.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono komentarza.", code="task_comment.not_found")
    if c.author_user_id != principal.user.id and member.role != "owner":
        raise Forbidden("Usunąć może autor albo właściciel wesela.", code="task_comment.forbidden")
    db.delete(c)
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="task_comment",
        entity_id=comment_id,
        wedding_id=wedding_id,
        action="delete",
    )
    db.commit()


def counts(db: Session, wedding_id: UUID) -> dict[UUID, int]:
    """Liczba komentarzy przy zadaniach (do znacznika na liście)."""
    from sqlalchemy import func

    return dict(
        db.execute(
            select(TaskComment.task_id, func.count())
            .where(TaskComment.wedding_id == wedding_id)
            .group_by(TaskComment.task_id)
        ).all()
    )
