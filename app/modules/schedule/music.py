"""Muzyka: utwory na momenty wesela, „koniecznie” i „nie grać”, propozycje gości z RSVP.

Para układa listę dla DJ-a lub zespołu. Gość może zaproponować utwór w formularzu RSVP
(gdy para to włączy) — propozycja czeka na zatwierdzenie. Zatwierdzone utwory widzi DJ,
zespół lub muzyk na swoim linku; zmiana listy podnosi wersję programu do potwierdzenia.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.errors import Conflict, NotFound
from app.modules.audit import service as audit
from app.modules.guests.models import GuestInfo, Household
from app.modules.identity.service import Principal
from app.modules.schedule.models import MUSIC_MOMENTS, MusicEntry
from app.modules.workspace.permissions import Action, authorize

MUSIC_CATEGORIES = ("dj", "band", "musician")
GUEST_LIMIT = 3  # propozycji na zaproszenie — żeby lista nie zamieniła się w koncert życzeń
MOMENT_LABELS = {
    "ceremony": "Ceremonia",
    "entrance": "Wejście pary",
    "first_dance": "Pierwszy taniec",
    "parents": "Podziękowania dla rodziców",
    "cake": "Tort",
    "oczepiny": "Oczepiny",
    "last_dance": "Ostatni taniec",
    "must": "Koniecznie zagrajcie",
    "avoid": "Nie grać",
    "other": "Inne",
}
_ORDER = {m: i for i, m in enumerate(MUSIC_MOMENTS)}


def _entry(db: Session, wedding_id: UUID, entry_id: UUID) -> MusicEntry:
    e = db.get(MusicEntry, entry_id)
    if e is None or e.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono utworu.", code="music.not_found")
    return e


def _record(
    db: Session,
    wedding_id: UUID,
    entity_id: UUID,
    action: str,
    principal: Principal | None = None,
) -> None:
    audit.record(
        db,
        actor_type="user" if principal else "guest",
        actor_id=principal.user.id if principal else None,
        entity_type="music_entry",
        entity_id=entity_id,
        wedding_id=wedding_id,
        action=action,
    )


def _sorted(entries: list[MusicEntry]) -> list[MusicEntry]:
    return sorted(entries, key=lambda e: (_ORDER[e.moment], e.position, e.created_at))


def _rows(db: Session, wedding_id: UUID) -> list[tuple[MusicEntry, str | None]]:
    rows = db.execute(
        select(MusicEntry, Household.name)
        .outerjoin(Household, Household.id == MusicEntry.household_id)
        .where(MusicEntry.wedding_id == wedding_id)
    ).all()
    order = {e.id: i for i, e in enumerate(_sorted([e for e, _ in rows]))}
    return sorted(((e, name) for e, name in rows), key=lambda r: order[r[0].id])


def out(entry: MusicEntry, household_name: str | None = None) -> dict[str, Any]:
    return {
        "id": entry.id,
        "moment": entry.moment,
        "title": entry.title,
        "artist": entry.artist,
        "note": entry.note,
        "status": entry.status,
        "suggested_by": household_name,
        "from_guest": entry.household_id is not None or entry.status == "suggested",
        "version": entry.version,
    }


def overview(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    info = db.get(GuestInfo, wedding_id)
    rows = _rows(db, wedding_id)
    return {
        "song_requests": bool(info and info.song_requests),
        "entries": [out(e, name) for e, name in rows],
        "waiting": sum(1 for e, _ in rows if e.status == "suggested"),
    }


def _next_position(db: Session, wedding_id: UUID, moment: str) -> int:
    last = db.scalar(
        select(func.max(MusicEntry.position)).where(
            MusicEntry.wedding_id == wedding_id, MusicEntry.moment == moment
        )
    )
    return 0 if last is None else last + 1


def create(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]
) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    e = MusicEntry(
        wedding_id=wedding_id,
        status="approved",
        position=_next_position(db, wedding_id, data["moment"]),
        **data,
    )
    db.add(e)
    db.flush()
    _record(db, wedding_id, e.id, "create", principal)
    db.commit()
    return out(e)


def update(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    entry_id: UUID,
    data: dict[str, Any],
    version: int,
) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    e = _entry(db, wedding_id, entry_id)
    if e.version != version:
        raise Conflict("Utwór zmienił się w międzyczasie.", code="conflict.version_mismatch")
    if "moment" in data and data["moment"] and data["moment"] != e.moment:
        e.position = _next_position(db, wedding_id, data["moment"])
    for k, v in data.items():
        if v is not None or k in ("artist", "note"):
            setattr(e, k, v)
    _record(db, wedding_id, e.id, "update", principal)
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise Conflict(
            "Utwór zmienił się w międzyczasie.", code="conflict.version_mismatch"
        ) from exc
    household = db.get(Household, e.household_id) if e.household_id else None
    return out(e, household.name if household else None)


def delete(db: Session, principal: Principal, wedding_id: UUID, entry_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    db.delete(_entry(db, wedding_id, entry_id))
    _record(db, wedding_id, entry_id, "delete", principal)
    db.commit()


def set_song_requests(db: Session, principal: Principal, wedding_id: UUID, on: bool) -> bool:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    info = db.get(GuestInfo, wedding_id)
    if info is None:
        info = GuestInfo(wedding_id=wedding_id)
        db.add(info)
    info.song_requests = on
    action = "song_requests_on" if on else "song_requests_off"
    _record(db, wedding_id, wedding_id, action, principal)
    db.commit()
    return on


# --- gość (link RSVP) -------------------------------------------------------------------------


def guest_suggestions(db: Session, household_id: UUID) -> list[dict[str, Any]]:
    """Propozycje gościa (bez statusu: gość nie widzi, co para odrzuciła)."""
    return [
        {"title": e.title, "artist": e.artist}
        for e in db.scalars(
            select(MusicEntry)
            .where(MusicEntry.household_id == household_id)
            .order_by(MusicEntry.created_at)
        )
    ]


def suggest(db: Session, wedding_id: UUID, household_id: UUID, data: dict[str, Any]) -> None:
    info = db.get(GuestInfo, wedding_id)
    if not (info and info.song_requests):
        raise NotFound("Para nie zbiera propozycji utworów.", code="rsvp.songs_disabled")
    count = db.scalar(
        select(func.count()).select_from(MusicEntry).where(MusicEntry.household_id == household_id)
    )
    if (count or 0) >= GUEST_LIMIT:
        raise Conflict(
            f"Można zaproponować najwyżej {GUEST_LIMIT} utwory.", code="rsvp.songs_limit"
        )
    e = MusicEntry(
        wedding_id=wedding_id,
        household_id=household_id,
        moment="must",
        status="suggested",
        position=_next_position(db, wedding_id, "must"),
        **data,
    )
    db.add(e)
    db.flush()
    _record(db, wedding_id, e.id, "suggest")
    db.commit()


# --- link DJ-a / zespołu ----------------------------------------------------------------------


def vendor_list(db: Session, wedding_id: UUID, category: str) -> list[dict[str, Any]]:
    """Zatwierdzone utwory dla DJ-a, zespołu lub muzyka (bez informacji, kto zaproponował)."""
    if category not in MUSIC_CATEGORIES:
        return []
    entries = db.scalars(
        select(MusicEntry).where(
            MusicEntry.wedding_id == wedding_id, MusicEntry.status == "approved"
        )
    )
    return [
        {"moment": e.moment, "title": e.title, "artist": e.artist, "note": e.note}
        for e in _sorted(list(entries))
    ]
