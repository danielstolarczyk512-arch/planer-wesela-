from datetime import timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, Response
from sqlalchemy import select

from app.core.clock import local
from app.core.deps import CurrentPrincipal, DbSession, IfMatchVersion, etag
from app.core.net import ip_prefix
from app.modules.schedule import briefs, checklist, music, photos, prep, service
from app.modules.schedule.conflicts import Conflict
from app.modules.schedule.models import ScheduleItem
from app.modules.schedule.schemas import (
    AckIn,
    AckOut,
    BriefIn,
    BriefOut,
    BriefStatus,
    ChecklistIn,
    ChecklistOut,
    ChecklistUpdate,
    ConflictOut,
    DayLinkCreate,
    DayLinkCreated,
    DayLinkStatus,
    DoneIn,
    ItemCreate,
    ItemOut,
    ItemUpdate,
    MoveIn,
    MusicIn,
    MusicOut,
    MusicOverview,
    MusicUpdate,
    PhotoGroupIn,
    PhotoGroupUpdate,
    PhotoOverview,
    PrepOverview,
    PrepPersonIn,
    PrepPersonUpdate,
    PrepPlanIn,
    PublicDay,
    ShiftIn,
    ShiftOut,
    SongRequestsIn,
    TemplateIn,
    TemplateOut,
)
from app.modules.vendors.models import Vendor

router = APIRouter(tags=["harmonogram dnia"])
public_router = APIRouter(prefix="/day", tags=["harmonogram dnia (publiczny link)"])

Responses = dict[int | str, dict[str, Any]]
_READ: Responses = {
    401: {"description": "Brak uwierzytelnienia"},
    404: {"description": "Nie znaleziono lub brak dostępu"},
}
_WRITE: Responses = {
    **_READ,
    403: {"description": "Rola tylko do odczytu"},
    409: {"description": "Konflikt"},
    422: {"description": "Błąd walidacji"},
}
W = "/weddings/{wedding_id}/schedule"


def items_out(
    db: DbSession, items: list[ScheduleItem], found: list[Conflict] | None = None
) -> list[ItemOut]:
    deps = service.dependencies(db, [i.id for i in items])
    vendor_ids = {i.vendor_id for i in items if i.vendor_id}
    names = (
        {v.id: v.name for v in db.scalars(select(Vendor).where(Vendor.id.in_(vendor_ids)))}
        if vendor_ids
        else {}
    )
    by_item: dict[UUID, list[str]] = {}
    for c in found or []:
        for item_id in c.item_ids:
            by_item.setdefault(item_id, []).append(c.code)
    return [
        ItemOut.model_validate(
            {
                "id": i.id,
                "title": i.title,
                "starts_at": local(i.starts_at),
                "ends_at": local(i.starts_at + timedelta(minutes=i.duration_minutes)),
                "duration_minutes": i.duration_minutes,
                "event_id": i.event_id,
                "location": i.location,
                "responsible_user_id": i.responsible_user_id,
                "responsible_name": i.responsible_name,
                "vendor_id": i.vendor_id,
                "vendor_name": names.get(i.vendor_id) if i.vendor_id else None,
                "preparations": i.preparations,
                "plan_b": i.plan_b,
                "for_guests": i.for_guests,
                "buffer_before_minutes": i.buffer_before_minutes,
                "buffer_after_minutes": i.buffer_after_minutes,
                "notes": i.notes,
                "depends_on": deps[i.id],
                "conflicts": sorted(set(by_item.get(i.id, []))),
                "version": i.version,
            }
        )
        for i in items
    ]


def conflicts_out(found: list[Conflict]) -> list[ConflictOut]:
    return [
        ConflictOut.model_validate(
            {
                "code": c.code,
                "severity": c.severity,
                "item_ids": list(c.item_ids),
                "message": c.message,
            }
        )
        for c in found
    ]


def _one(
    db: DbSession, principal: CurrentPrincipal, wedding_id: UUID, item: ScheduleItem
) -> ItemOut:
    found = service.detect_conflicts(db, principal, wedding_id)
    return items_out(db, [item], found)[0]


@router.get(
    W,
    responses=_READ,
    summary="Program dnia (filtry: wydarzenie, usługodawca, np. plan dla zespołu)",
)
def list_items(
    wedding_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    event_id: UUID | None = None,
    vendor_id: UUID | None = None,
) -> list[ItemOut]:
    items, found = service.list_items(
        db, principal, wedding_id, event_id=event_id, vendor_id=vendor_id
    )
    return items_out(db, items, found)


@router.post(W, status_code=201, responses=_WRITE, summary="Nowy punkt programu")
def create_item(
    wedding_id: UUID, body: ItemCreate, principal: CurrentPrincipal, db: DbSession
) -> ItemOut:
    item = service.create_item(db, principal, wedding_id, body.model_dump())
    return _one(db, principal, wedding_id, item)


@router.get(
    f"{W}/conflicts",
    responses=_READ,
    summary="Konflikty: osoba/usługodawca w dwóch miejscach, kolejność, ramy wydarzeń",
)
def get_conflicts(
    wedding_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> list[ConflictOut]:
    return conflicts_out(service.detect_conflicts(db, principal, wedding_id))


@router.post(
    f"{W}/shift",
    responses=_WRITE,
    summary="Przesunięcie programu od wskazanego punktu o N minut (dry_run)",
)
def shift(wedding_id: UUID, body: ShiftIn, principal: CurrentPrincipal, db: DbSession) -> ShiftOut:
    changes, after = service.shift(
        db,
        principal,
        wedding_id,
        from_item_id=body.from_item_id,
        minutes=body.minutes,
        dry_run=body.dry_run,
    )
    return ShiftOut.model_validate(
        {"dry_run": body.dry_run, "changes": changes, "conflicts_after": conflicts_out(after)}
    )


@router.post(
    f"{W}/from-template",
    responses=_WRITE,
    summary="Typowy program polskiego wesela jako punkt startowy (dry_run)",
)
def from_template(
    wedding_id: UUID, body: TemplateIn, principal: CurrentPrincipal, db: DbSession
) -> TemplateOut:
    plan = service.apply_template(
        db,
        principal,
        wedding_id,
        day=body.day,
        ceremony_time=body.ceremony_time,
        dry_run=body.dry_run,
    )
    return TemplateOut.model_validate({"dry_run": body.dry_run, "items": plan})


@router.get(f"{W}/{{item_id}}", responses=_READ, summary="Punkt programu")
def get_item(
    wedding_id: UUID, item_id: UUID, principal: CurrentPrincipal, db: DbSession, response: Response
) -> ItemOut:
    item = service.get_item(db, principal, wedding_id, item_id)
    response.headers["ETag"] = etag(item.version)
    return _one(db, principal, wedding_id, item)


@router.patch(
    f"{W}/{{item_id}}",
    responses={**_WRITE, 428: {"description": "Brak If-Match"}},
    summary="Edycja punktu programu (If-Match)",
)
def update_item(
    wedding_id: UUID,
    item_id: UUID,
    principal: CurrentPrincipal,
    body: ItemUpdate,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> ItemOut:
    item = service.update_item(
        db, principal, wedding_id, item_id, body.model_dump(exclude_unset=True), version
    )
    response.headers["ETag"] = etag(item.version)
    return _one(db, principal, wedding_id, item)


@router.delete(
    f"{W}/{{item_id}}", status_code=204, responses=_WRITE, summary="Usunięcie punktu programu"
)
def delete_item(
    wedding_id: UUID, item_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.delete_item(db, principal, wedding_id, item_id)


@router.put(
    f"{W}/{{item_id}}/dependencies/{{depends_on_id}}",
    responses=_WRITE,
    summary="Punkt zaczyna się po zakończeniu innego",
)
def add_dependency(
    wedding_id: UUID, item_id: UUID, depends_on_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> ItemOut:
    item = service.add_dependency(db, principal, wedding_id, item_id, depends_on_id)
    return _one(db, principal, wedding_id, item)


@router.delete(
    f"{W}/{{item_id}}/dependencies/{{depends_on_id}}",
    status_code=204,
    responses=_WRITE,
    summary="Usunięcie zależności",
)
def remove_dependency(
    wedding_id: UUID, item_id: UUID, depends_on_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.remove_dependency(db, principal, wedding_id, item_id, depends_on_id)


# --- link z programem dla usługodawcy (Premium) ----------------------------------------------

V = "/weddings/{wedding_id}/vendors/{vendor_id}/day-link"


@router.get(V, responses=_READ, summary="Czy usługodawca ma aktywny link z programem dnia")
def day_link_status(
    wedding_id: UUID, vendor_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> DayLinkStatus:
    link = service.day_link_status(db, principal, wedding_id, vendor_id)
    return DayLinkStatus(
        active=link is not None,
        share_catering=link.share_catering if link else False,
        created_at=link.created_at if link else None,
        last_used_at=link.last_used_at if link else None,
    )


@router.post(
    V,
    status_code=201,
    responses=_WRITE,
    summary="Nowy link z programem dnia dla usługodawcy (poprzedni przestaje działać)",
)
def create_day_link(
    wedding_id: UUID,
    vendor_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    body: DayLinkCreate | None = None,
) -> DayLinkCreated:
    share = body.share_catering if body else False
    return DayLinkCreated(
        token=service.create_day_link(db, principal, wedding_id, vendor_id, share_catering=share)
    )


@router.delete(V, status_code=204, responses=_WRITE, summary="Wyłącz link usługodawcy")
def revoke_day_link(
    wedding_id: UUID, vendor_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.revoke_day_link(db, principal, wedding_id, vendor_id)


def _brief_out(b: Any) -> BriefOut:
    return BriefOut.model_validate(
        {
            **briefs.brief_out(b),
            "vendor_id": b.vendor_id,
            "version": b.version,
            "updated_at": b.updated_at,
        }
    )


@router.get(
    "/weddings/{wedding_id}/vendors/{vendor_id}/brief",
    responses=_READ,
    summary="Informacje dla usługodawcy (obowiązkowe, czego unikać, kto jest kim)",
)
def get_brief(
    wedding_id: UUID,
    vendor_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    response: Response,
) -> BriefOut:
    b = briefs.get_brief(db, principal, wedding_id, vendor_id)
    response.headers["ETag"] = etag(b.version)
    return _brief_out(b)


@router.put(
    "/weddings/{wedding_id}/vendors/{vendor_id}/brief",
    responses={**_WRITE, 428: {"description": "Brak If-Match"}},
    summary="Zapis informacji dla usługodawcy (If-Match); zmienia wersję jego linku",
)
def save_brief(
    wedding_id: UUID,
    vendor_id: UUID,
    body: BriefIn,
    principal: CurrentPrincipal,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> BriefOut:
    b = briefs.save_brief(db, principal, wedding_id, vendor_id, body.model_dump(), version)
    response.headers["ETag"] = etag(b.version)
    return _brief_out(b)


@router.get(
    "/weddings/{wedding_id}/vendor-briefs",
    responses=_READ,
    summary="Kto zna aktualny program: wersje i potwierdzenia usługodawców z linkiem",
)
def brief_statuses(
    wedding_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> list[BriefStatus]:
    return [BriefStatus.model_validate(r) for r in briefs.statuses(db, principal, wedding_id)]


@public_router.post(
    "/{token}/ack",
    responses={
        404: {"description": "Link nieprawidłowy lub wyłączony"},
        409: {"description": "Program zmienił się od otwarcia strony"},
        429: {},
    },
    summary="Usługodawca potwierdza przeczytanie wersji programu",
)
def acknowledge(token: str, body: AckIn, request: Request, db: DbSession) -> AckOut:
    version, at = briefs.acknowledge(db, token, ip_prefix(request), body.version)
    return AckOut(version=version, acknowledged_at=at)


@public_router.get(
    "/{token}",
    responses={404: {"description": "Link nieprawidłowy lub wyłączony"}, 429: {}},
    summary="Program dnia dla usługodawcy (bez logowania)",
)
def public_day(token: str, request: Request, db: DbSession, response: Response) -> PublicDay:
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex"
    return PublicDay.model_validate(service.public_day(db, token, ip_prefix(request)))


# --- co zabrać na dzień ślubu ---------------------------------------------------------------

C = "/weddings/{wedding_id}/day-checklist"


def _checklist_out(i: Any) -> ChecklistOut:
    return ChecklistOut.model_validate(i, from_attributes=True)


@router.get(C, responses=_READ, summary="Co zabrać na dzień ślubu (także koordynator dnia)")
def day_checklist(
    wedding_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> list[ChecklistOut]:
    return [_checklist_out(i) for i in checklist.list_items(db, principal, wedding_id)]


@router.post(C, status_code=201, responses=_WRITE, summary="Nowa rzecz do zabrania")
def create_checklist_item(
    wedding_id: UUID, body: ChecklistIn, principal: CurrentPrincipal, db: DbSession
) -> ChecklistOut:
    return _checklist_out(checklist.create(db, principal, wedding_id, body.model_dump()))


@router.post(
    f"{C}/typical",
    responses=_WRITE,
    summary="Typowa lista i koperty z płatności na dzień ślubu (bez duplikatów)",
)
def add_typical_checklist(
    wedding_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> list[ChecklistOut]:
    return [_checklist_out(i) for i in checklist.add_typical(db, principal, wedding_id)]


@router.patch(
    f"{C}/{{item_id}}",
    responses={**_WRITE, 428: {"description": "Brak If-Match"}},
    summary="Edycja pozycji (If-Match)",
)
def update_checklist_item(
    wedding_id: UUID,
    item_id: UUID,
    body: ChecklistUpdate,
    principal: CurrentPrincipal,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> ChecklistOut:
    i = checklist.update(
        db, principal, wedding_id, item_id, body.model_dump(exclude_unset=True), version
    )
    response.headers["ETag"] = etag(i.version)
    return _checklist_out(i)


@router.delete(f"{C}/{{item_id}}", status_code=204, responses=_WRITE, summary="Usunięcie pozycji")
def delete_checklist_item(
    wedding_id: UUID, item_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    checklist.delete(db, principal, wedding_id, item_id)


@router.put(
    f"{C}/{{item_id}}/done",
    responses=_WRITE,
    summary="Odhaczenie w dniu ślubu (także koordynator dnia)",
)
def set_checklist_done(
    wedding_id: UUID, item_id: UUID, body: DoneIn, principal: CurrentPrincipal, db: DbSession
) -> ChecklistOut:
    return _checklist_out(checklist.set_done(db, principal, wedding_id, item_id, body.done))


# --- muzyka ----------------------------------------------------------------------------------

M = "/weddings/{wedding_id}/music"


@router.get(M, responses=_READ, summary="Muzyka: utwory na momenty i propozycje gości")
def music_list(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> MusicOverview:
    return MusicOverview.model_validate(music.overview(db, principal, wedding_id))


@router.post(M, status_code=201, responses=_WRITE, summary="Nowy utwór (zatwierdzony)")
def music_create(
    wedding_id: UUID, body: MusicIn, principal: CurrentPrincipal, db: DbSession
) -> MusicOut:
    return MusicOut.model_validate(music.create(db, principal, wedding_id, body.model_dump()))


@router.put(
    f"{M}/song-requests", responses=_WRITE, summary="Czy goście mogą proponować utwory w RSVP"
)
def music_song_requests(
    wedding_id: UUID, body: SongRequestsIn, principal: CurrentPrincipal, db: DbSession
) -> SongRequestsIn:
    return SongRequestsIn(enabled=music.set_song_requests(db, principal, wedding_id, body.enabled))


@router.patch(
    f"{M}/{{entry_id}}",
    responses={**_WRITE, 428: {"description": "Brak If-Match"}},
    summary="Edycja utworu, zatwierdzenie lub odrzucenie propozycji (If-Match)",
)
def music_update(
    wedding_id: UUID,
    entry_id: UUID,
    body: MusicUpdate,
    principal: CurrentPrincipal,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> MusicOut:
    e = music.update(
        db, principal, wedding_id, entry_id, body.model_dump(exclude_unset=True), version
    )
    response.headers["ETag"] = etag(e["version"])
    return MusicOut.model_validate(e)


@router.delete(f"{M}/{{entry_id}}", status_code=204, responses=_WRITE, summary="Usunięcie utworu")
def music_delete(
    wedding_id: UUID, entry_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    music.delete(db, principal, wedding_id, entry_id)


# --- zdjęcia grupowe -------------------------------------------------------------------------

PG = "/weddings/{wedding_id}/photo-groups"


@router.get(PG, responses=_READ, summary="Zdjęcia grupowe (także koordynator dnia)")
def photo_groups(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> PhotoOverview:
    return PhotoOverview.model_validate(photos.overview(db, principal, wedding_id))


@router.post(PG, status_code=201, responses=_WRITE, summary="Nowa grupa do zdjęcia")
def photo_group_create(
    wedding_id: UUID, body: PhotoGroupIn, principal: CurrentPrincipal, db: DbSession
) -> PhotoOverview:
    photos.create(db, principal, wedding_id, body.model_dump())
    return PhotoOverview.model_validate(photos.overview(db, principal, wedding_id))


@router.post(f"{PG}/typical", responses=_WRITE, summary="Typowe grupy (bez osób, bez duplikatów)")
def photo_groups_typical(
    wedding_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> PhotoOverview:
    photos.add_typical(db, principal, wedding_id)
    return PhotoOverview.model_validate(photos.overview(db, principal, wedding_id))


@router.patch(
    f"{PG}/{{group_id}}",
    responses={**_WRITE, 428: {"description": "Brak If-Match"}},
    summary="Edycja grupy i jej składu (If-Match)",
)
def photo_group_update(
    wedding_id: UUID,
    group_id: UUID,
    body: PhotoGroupUpdate,
    principal: CurrentPrincipal,
    version: IfMatchVersion,
    db: DbSession,
) -> PhotoOverview:
    photos.update(db, principal, wedding_id, group_id, body.model_dump(exclude_unset=True), version)
    return PhotoOverview.model_validate(photos.overview(db, principal, wedding_id))


@router.post(f"{PG}/{{group_id}}/move", responses=_WRITE, summary="Przesunięcie w kolejności")
def photo_group_move(
    wedding_id: UUID, group_id: UUID, body: MoveIn, principal: CurrentPrincipal, db: DbSession
) -> PhotoOverview:
    photos.move(db, principal, wedding_id, group_id, body.direction == "up")
    return PhotoOverview.model_validate(photos.overview(db, principal, wedding_id))


@router.delete(f"{PG}/{{group_id}}", status_code=204, responses=_WRITE, summary="Usunięcie grupy")
def photo_group_delete(
    wedding_id: UUID, group_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    photos.delete(db, principal, wedding_id, group_id)


@router.put(
    f"{PG}/{{group_id}}/done",
    responses=_WRITE,
    summary="Odhaczenie zdjęcia w dniu ślubu (także koordynator dnia)",
)
def photo_group_done(
    wedding_id: UUID, group_id: UUID, body: DoneIn, principal: CurrentPrincipal, db: DbSession
) -> PhotoOverview:
    photos.set_done(db, principal, wedding_id, group_id, body.done)
    return PhotoOverview.model_validate(photos.overview(db, principal, wedding_id))


# --- przygotowania (fryzjer, makijaż) ----------------------------------------------------------

PR = "/weddings/{wedding_id}/prep"


@router.get(
    PR, responses=_READ, summary="Plan przygotowań: kto i o której u fryzjera i makijażystki"
)
def prep_plan(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> PrepOverview:
    return PrepOverview.model_validate(prep.overview(db, principal, wedding_id))


@router.put(
    PR,
    responses={**_WRITE, 428: {"description": "Brak If-Match (0 dla nowego planu)"}},
    summary="Godzina „gotowi” i liczba osób obsługujących (If-Match)",
)
def save_prep_plan(
    wedding_id: UUID,
    body: PrepPlanIn,
    principal: CurrentPrincipal,
    version: IfMatchVersion,
    db: DbSession,
) -> PrepOverview:
    prep.save_plan(db, principal, wedding_id, body.model_dump(), version)
    return PrepOverview.model_validate(prep.overview(db, principal, wedding_id))


@router.post(f"{PR}/people", status_code=201, responses=_WRITE, summary="Nowa osoba na fotel")
def add_prep_person(
    wedding_id: UUID, body: PrepPersonIn, principal: CurrentPrincipal, db: DbSession
) -> PrepOverview:
    prep.add_person(db, principal, wedding_id, body.model_dump())
    return PrepOverview.model_validate(prep.overview(db, principal, wedding_id))


@router.patch(
    f"{PR}/people/{{person_id}}",
    responses={**_WRITE, 428: {"description": "Brak If-Match"}},
    summary="Edycja osoby (If-Match)",
)
def update_prep_person(
    wedding_id: UUID,
    person_id: UUID,
    body: PrepPersonUpdate,
    principal: CurrentPrincipal,
    version: IfMatchVersion,
    db: DbSession,
) -> PrepOverview:
    prep.update_person(
        db, principal, wedding_id, person_id, body.model_dump(exclude_unset=True), version
    )
    return PrepOverview.model_validate(prep.overview(db, principal, wedding_id))


@router.post(f"{PR}/people/{{person_id}}/move", responses=_WRITE, summary="Przesunięcie w kolejce")
def move_prep_person(
    wedding_id: UUID, person_id: UUID, body: MoveIn, principal: CurrentPrincipal, db: DbSession
) -> PrepOverview:
    prep.move_person(db, principal, wedding_id, person_id, body.direction == "up")
    return PrepOverview.model_validate(prep.overview(db, principal, wedding_id))


@router.delete(
    f"{PR}/people/{{person_id}}", status_code=204, responses=_WRITE, summary="Usunięcie osoby"
)
def delete_prep_person(
    wedding_id: UUID, person_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    prep.delete_person(db, principal, wedding_id, person_id)
