from typing import Any
from uuid import UUID

from fastapi import APIRouter, Response

from app.core.deps import CurrentPrincipal, DbSession, IfMatchVersion, etag
from app.modules.logistics import service
from app.modules.logistics.schemas import (
    DayRun,
    GuestsIn,
    LodgingRoomCreate,
    LodgingRoomUpdate,
    LogisticsOverview,
    RunCreate,
    RunUpdate,
)

router = APIRouter(tags=["transport i noclegi"])

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
_PATCH: Responses = {**_WRITE, 428: {"description": "Brak If-Match"}}
W = "/weddings/{wedding_id}"


def _overview(db: DbSession, principal: CurrentPrincipal, wedding_id: UUID) -> LogisticsOverview:
    return LogisticsOverview.model_validate(service.overview(db, principal, wedding_id))


@router.get(f"{W}/logistics", responses=_READ, summary="Transport i noclegi: kursy, pokoje, braki")
def logistics(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> LogisticsOverview:
    return _overview(db, principal, wedding_id)


@router.post(f"{W}/transport-runs", status_code=201, responses=_WRITE, summary="Nowy kurs")
def create_run(
    wedding_id: UUID, body: RunCreate, principal: CurrentPrincipal, db: DbSession
) -> LogisticsOverview:
    service.create_run(db, principal, wedding_id, body.model_dump())
    return _overview(db, principal, wedding_id)


@router.patch(f"{W}/transport-runs/{{run_id}}", responses=_PATCH, summary="Edycja kursu (If-Match)")
def update_run(
    wedding_id: UUID,
    run_id: UUID,
    body: RunUpdate,
    principal: CurrentPrincipal,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> LogisticsOverview:
    r = service.update_run(
        db, principal, wedding_id, run_id, body.model_dump(exclude_unset=True), version
    )
    response.headers["ETag"] = etag(r.version)
    return _overview(db, principal, wedding_id)


@router.delete(
    f"{W}/transport-runs/{{run_id}}", status_code=204, responses=_WRITE, summary="Usunięcie kursu"
)
def delete_run(wedding_id: UUID, run_id: UUID, principal: CurrentPrincipal, db: DbSession) -> None:
    service.delete_run(db, principal, wedding_id, run_id)


@router.put(
    f"{W}/transport-runs/{{run_id}}/guests",
    responses=_WRITE,
    summary="Pasażerowie kursu (zastępuje listę)",
)
def set_passengers(
    wedding_id: UUID, run_id: UUID, body: GuestsIn, principal: CurrentPrincipal, db: DbSession
) -> LogisticsOverview:
    service.set_passengers(db, principal, wedding_id, run_id, body.guest_ids)
    return _overview(db, principal, wedding_id)


@router.post(f"{W}/lodging-rooms", status_code=201, responses=_WRITE, summary="Nowy pokój")
def create_room(
    wedding_id: UUID, body: LodgingRoomCreate, principal: CurrentPrincipal, db: DbSession
) -> LogisticsOverview:
    service.create_room(db, principal, wedding_id, body.model_dump())
    return _overview(db, principal, wedding_id)


@router.patch(
    f"{W}/lodging-rooms/{{room_id}}", responses=_PATCH, summary="Edycja pokoju (If-Match)"
)
def update_room(
    wedding_id: UUID,
    room_id: UUID,
    body: LodgingRoomUpdate,
    principal: CurrentPrincipal,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> LogisticsOverview:
    r = service.update_room(
        db, principal, wedding_id, room_id, body.model_dump(exclude_unset=True), version
    )
    response.headers["ETag"] = etag(r.version)
    return _overview(db, principal, wedding_id)


@router.delete(
    f"{W}/lodging-rooms/{{room_id}}", status_code=204, responses=_WRITE, summary="Usunięcie pokoju"
)
def delete_room(
    wedding_id: UUID, room_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.delete_room(db, principal, wedding_id, room_id)


@router.put(
    f"{W}/lodging-rooms/{{room_id}}/guests",
    responses=_WRITE,
    summary="Goście w pokoju (zastępuje listę; gość z innego pokoju zostaje przeniesiony)",
)
def set_occupants(
    wedding_id: UUID, room_id: UUID, body: GuestsIn, principal: CurrentPrincipal, db: DbSession
) -> LogisticsOverview:
    service.set_occupants(db, principal, wedding_id, room_id, body.guest_ids)
    return _overview(db, principal, wedding_id)


@router.get(
    f"{W}/lodging/rooming.csv",
    responses=_READ,
    response_class=Response,
    summary="Lista pokoi dla hotelu (CSV, średnik, UTF-8 z BOM)",
)
def rooming_csv(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> Response:
    data = service.rooming_csv(db, principal, wedding_id)
    return Response(
        content=data.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="lista-pokoi.csv"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    f"{W}/day-transport",
    responses=_READ,
    summary="Kursy na dzień ślubu: godziny i liczby osób (także koordynator dnia)",
)
def day_transport(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> list[DayRun]:
    return [DayRun.model_validate(r) for r in service.day_runs(db, principal, wedding_id)]
