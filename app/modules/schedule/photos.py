"""Zdjęcia grupowe dla fotografa: kto, w jakiej kolejności, ile to potrwa.

Para układa listę grup (osoby z listy gości i ewentualnie inne, np. „ksiądz”). Suma minut
podpowiada, ile czasu zarezerwować w harmonogramie. W dniu ślubu koordynator (świadek)
odhacza zrobione grupy, a fotograf widzi listę na swoim linku — z imionami i inicjałem
nazwiska, bez innych danych gości.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm.exc import StaleDataError

from app.core.errors import Conflict, NotFound, Unprocessable
from app.modules.audit import service as audit
from app.modules.guests.models import Guest
from app.modules.identity.service import Principal
from app.modules.schedule.models import PhotoGroup, PhotoGroupGuest
from app.modules.workspace.permissions import Action, authorize

PHOTO_CATEGORIES = ("photographer", "videographer")
# Typowa kolejność: najpierw starsi i najbliżsi (żeby mogli usiąść), na końcu duże grupy.
TYPICAL: tuple[str, ...] = (
    "Para Młoda z dziadkami",
    "Para Młoda z rodzicami Panny Młodej",
    "Para Młoda z rodzicami Pana Młodego",
    "Para Młoda z obojgiem rodziców",
    "Para Młoda z rodzeństwem",
    "Para Młoda ze świadkami",
    "Para Młoda z chrzestnymi",
    "Rodzina Panny Młodej",
    "Rodzina Pana Młodego",
    "Przyjaciele",
    "Wspólne zdjęcie wszystkich gości",
)


def _group(db: Session, wedding_id: UUID, group_id: UUID) -> PhotoGroup:
    g = db.get(PhotoGroup, group_id)
    if g is None or g.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono grupy.", code="photo_group.not_found")
    return g


def _record(
    db: Session, principal: Principal, wedding_id: UUID, entity_id: UUID, action: str
) -> None:
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="photo_group",
        entity_id=entity_id,
        wedding_id=wedding_id,
        action=action,
    )


def _ordered(db: Session, wedding_id: UUID) -> list[PhotoGroup]:
    return list(
        db.scalars(
            select(PhotoGroup)
            .where(PhotoGroup.wedding_id == wedding_id)
            .order_by(PhotoGroup.position, PhotoGroup.created_at)
        )
    )


def _members(db: Session, group_ids: list[UUID]) -> dict[UUID, list[Guest]]:
    out: dict[UUID, list[Guest]] = {g: [] for g in group_ids}
    if group_ids:
        for group_id, guest in db.execute(
            select(PhotoGroupGuest.group_id, Guest)
            .join(Guest, Guest.id == PhotoGroupGuest.guest_id)
            .where(PhotoGroupGuest.group_id.in_(group_ids))
            .order_by(Guest.first_name)
        ):
            out[group_id].append(guest)
    return out


def _name(g: Guest) -> str:
    return f"{g.first_name} {g.last_name}" if g.last_name else g.first_name


def short_name(g: Guest) -> str:
    """Imię i inicjał nazwiska — tyle wystarczy fotografowi."""
    return f"{g.first_name} {g.last_name[0]}." if g.last_name else g.first_name


def overview(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.DAY_READ)
    groups = _ordered(db, wedding_id)
    members = _members(db, [g.id for g in groups])
    return {
        "groups": [
            {
                "id": g.id,
                "title": g.title,
                "extra": g.extra,
                "minutes": g.minutes,
                "done": g.done,
                "version": g.version,
                "guests": [{"id": m.id, "name": _name(m)} for m in members[g.id]],
            }
            for g in groups
        ],
        "total_minutes": sum(g.minutes for g in groups),
        "remaining_minutes": sum(g.minutes for g in groups if not g.done),
    }


def _set_guests(db: Session, wedding_id: UUID, group: PhotoGroup, guest_ids: list[UUID]) -> None:
    ids = set(guest_ids)
    if ids:
        found = set(
            db.scalars(select(Guest.id).where(Guest.wedding_id == wedding_id, Guest.id.in_(ids)))
        )
        if found != ids:
            raise Unprocessable(
                "Część osób nie należy do tego wesela.", code="photo_group.unknown_guest"
            )
    db.execute(sql_delete(PhotoGroupGuest).where(PhotoGroupGuest.group_id == group.id))
    db.add_all(PhotoGroupGuest(group_id=group.id, guest_id=i) for i in ids)


def _next_position(db: Session, wedding_id: UUID) -> int:
    last = db.scalar(
        select(func.max(PhotoGroup.position)).where(PhotoGroup.wedding_id == wedding_id)
    )
    return 0 if last is None else last + 1


def create(db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    guest_ids = data.pop("guest_ids", [])
    g = PhotoGroup(wedding_id=wedding_id, position=_next_position(db, wedding_id), **data)
    db.add(g)
    db.flush()
    _set_guests(db, wedding_id, g, guest_ids)
    _record(db, principal, wedding_id, g.id, "create")
    db.commit()


def update(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    group_id: UUID,
    data: dict[str, Any],
    version: int,
) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    g = _group(db, wedding_id, group_id)
    if g.version != version:
        raise Conflict("Grupa zmieniła się w międzyczasie.", code="conflict.version_mismatch")
    guest_ids = data.pop("guest_ids", None)
    if guest_ids is not None:
        _set_guests(db, wedding_id, g, guest_ids)
    for k, v in data.items():
        if v is not None or k == "extra":
            setattr(g, k, v)
    if guest_ids is not None and not db.is_modified(g):
        flag_modified(g, "title")  # zmiana samego składu też podnosi wersję grupy (If-Match)
    _record(db, principal, wedding_id, g.id, "update")
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise Conflict(
            "Grupa zmieniła się w międzyczasie.", code="conflict.version_mismatch"
        ) from exc


def delete(db: Session, principal: Principal, wedding_id: UUID, group_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    db.delete(_group(db, wedding_id, group_id))
    _record(db, principal, wedding_id, group_id, "delete")
    db.commit()


def set_done(
    db: Session, principal: Principal, wedding_id: UUID, group_id: UUID, done: bool
) -> None:
    """Odhaczenie w dniu ślubu: także koordynator dnia."""
    authorize(db, principal.user.id, wedding_id, Action.DAY_RUN)
    g = _group(db, wedding_id, group_id)
    g.done = done
    _record(db, principal, wedding_id, g.id, "done" if done else "undone")
    db.commit()


def move(db: Session, principal: Principal, wedding_id: UUID, group_id: UUID, up: bool) -> None:
    """Zamiana miejscami z sąsiednią grupą."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    groups = _ordered(db, wedding_id)
    i = next((k for k, g in enumerate(groups) if g.id == group_id), None)
    if i is None:
        raise NotFound("Nie znaleziono grupy.", code="photo_group.not_found")
    j = i - 1 if up else i + 1
    if 0 <= j < len(groups):
        groups[i], groups[j] = groups[j], groups[i]
        for pos, g in enumerate(groups):
            g.position = pos
        _record(db, principal, wedding_id, group_id, "move")
    db.commit()


def add_typical(db: Session, principal: Principal, wedding_id: UUID) -> None:
    """Typowe grupy (bez osób — para dopisuje); grupy o tej samej nazwie pomijamy."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    have = {g.title.casefold() for g in _ordered(db, wedding_id)}
    position = _next_position(db, wedding_id)
    added = 0
    for title in TYPICAL:
        if title.casefold() in have:
            continue
        minutes = 5 if title.startswith("Wspólne") else 3
        db.add(PhotoGroup(wedding_id=wedding_id, title=title, minutes=minutes, position=position))
        position += 1
        added += 1
    if added:
        _record(db, principal, wedding_id, wedding_id, "add_typical")
    db.commit()


def vendor_list(db: Session, wedding_id: UUID, category: str) -> list[dict[str, Any]]:
    """Lista dla fotografa i filmowca: grupy, osoby (imię i inicjał), minuty."""
    if category not in PHOTO_CATEGORIES:
        return []
    groups = _ordered(db, wedding_id)
    members = _members(db, [g.id for g in groups])
    return [
        {
            "title": g.title,
            "people": [short_name(m) for m in members[g.id]],
            "extra": g.extra,
            "minutes": g.minutes,
        }
        for g in groups
    ]
