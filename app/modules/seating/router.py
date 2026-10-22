from typing import Any
from uuid import UUID

from fastapi import APIRouter, Response

from app.core.deps import CurrentPrincipal, DbSession, IfMatchVersion, etag
from app.modules.seating import service
from app.modules.seating.models import SeatingRule, SeatingTable
from app.modules.seating.schemas import (
    AssignmentsIn,
    AutoIn,
    AutoOut,
    AutoRunOut,
    ClearIn,
    PlanOut,
    RoomIn,
    RoomOut,
    RuleCreate,
    RuleOut,
    SeatIn,
    SeatNumbersIn,
    SeatNumbersOut,
    TableCreate,
    TableOut,
    TableUpdate,
)

router = APIRouter(tags=["plan stołów"])

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
W = "/weddings/{wedding_id}/seating"


def _table_out(t: SeatingTable) -> TableOut:
    return TableOut.model_validate(service.table_dict(t))


def _rule_out(r: SeatingRule) -> RuleOut:
    return RuleOut.model_validate(
        {
            "id": r.id,
            "kind": r.kind,
            "guest_a_id": r.guest_a_id,
            "guest_b_id": r.guest_b_id,
            "note": r.note,
        }
    )


@router.get(
    W,
    responses=_READ,
    summary="Plan stołów: stoły z gośćmi, goście bez miejsca, problemy (pojemność, reguły)",
)
def get_plan(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> PlanOut:
    return PlanOut.model_validate(service.plan(db, principal, wedding_id))


@router.post(
    f"{W}/auto",
    responses={**_WRITE, 429: {"description": "Limit automatycznych usadzeń"}},
    summary="Automatyczne usadzenie (rodziny razem, grupy, reguły; podgląd dry_run)",
)
def auto(wedding_id: UUID, body: AutoIn, principal: CurrentPrincipal, db: DbSession) -> AutoOut:
    return AutoOut.model_validate(
        service.auto(
            db,
            principal,
            wedding_id,
            basis=body.basis,
            keep_households=body.keep_households,
            kids_table=body.kids_table,
            kids_table_teens=body.kids_table_teens,
            time_limit=body.time_limit_seconds,
            dry_run=body.dry_run,
            near_groups=body.near_groups,
            near_target=body.near_target,
        )
    )


def _auto_run_out(run: Any) -> AutoRunOut:
    return AutoRunOut.model_validate(
        {
            "id": run.id,
            "status": run.status,
            "error_code": run.error_code,
            "error_message": run.error_message,
            "result": run.result,
        }
    )


@router.post(
    f"{W}/auto-runs",
    status_code=202,
    responses={**_WRITE, 429: {"description": "Limit automatycznych usadzeń"}},
    summary="Automatyczne usadzenie w tle (worker): zwraca przebieg do odpytywania",
)
def create_auto_run(
    wedding_id: UUID, body: AutoIn, principal: CurrentPrincipal, db: DbSession
) -> AutoRunOut:
    params = {
        "basis": body.basis,
        "keep_households": body.keep_households,
        "kids_table": body.kids_table,
        "kids_table_teens": body.kids_table_teens,
        "time_limit": body.time_limit_seconds,
        "near_groups": body.near_groups,
        "near_target": body.near_target,
    }
    return _auto_run_out(service.create_auto_run(db, principal, wedding_id, params))


@router.get(
    f"{W}/auto-runs/{{run_id}}",
    responses=_READ,
    summary="Stan przebiegu automatu i propozycja (do zapisu przez PUT …/assignments)",
)
def get_auto_run(
    wedding_id: UUID, run_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> AutoRunOut:
    return _auto_run_out(service.get_auto_run(db, principal, wedding_id, run_id))


@router.get(f"{W}/room", responses=_READ, summary="Układ sali: wymiary i elementy stałe")
def get_room(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> RoomOut:
    return RoomOut.model_validate(service.get_room(db, principal, wedding_id))


@router.put(
    f"{W}/room",
    responses={**_WRITE, 428: {"description": "Brak If-Match"}},
    summary="Zapis układu sali (wymiary, parkiet, scena, bar, wejście)",
)
def save_room(
    wedding_id: UUID,
    body: RoomIn,
    principal: CurrentPrincipal,
    db: DbSession,
    version: IfMatchVersion,
    response: Response,
) -> RoomOut:
    room = service.save_room(db, principal, wedding_id, body.model_dump(), version)
    response.headers["ETag"] = etag(room["version"])
    return RoomOut.model_validate(room)


@router.post(
    f"{W}/seat-numbers",
    responses=_WRITE,
    summary="Numery miejsc przy stołach (rodzina obok siebie, dzieci przy rodzicu)",
)
def seat_numbers(
    wedding_id: UUID, body: SeatNumbersIn, principal: CurrentPrincipal, db: DbSession
) -> SeatNumbersOut:
    return SeatNumbersOut.model_validate(
        service.seat_numbers(
            db,
            principal,
            wedding_id,
            table_id=body.table_id,
            keep_existing=body.keep_existing,
            dry_run=body.dry_run,
        )
    )


@router.put(
    f"{W}/assignments",
    status_code=204,
    responses=_WRITE,
    summary="Zapis wielu przypisań naraz (np. zaakceptowany podgląd automatu)",
)
def set_assignments(
    wedding_id: UUID, body: AssignmentsIn, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.set_assignments(
        db,
        principal,
        wedding_id,
        [a.model_dump() for a in body.assignments],
        replace_unlocked=body.replace_unlocked,
    )


@router.post(
    f"{W}/clear", responses=_WRITE, summary="Wyczyszczenie planu (domyślnie bez przypiętych)"
)
def clear(
    wedding_id: UUID, body: ClearIn, principal: CurrentPrincipal, db: DbSession
) -> dict[str, int]:
    return {"removed": service.clear(db, principal, wedding_id, include_locked=body.include_locked)}


@router.put(
    f"{W}/guests/{{guest_id}}",
    status_code=204,
    responses=_WRITE,
    summary="Ręczne posadzenie gościa (przypięte: automat go nie przesunie)",
)
def seat_guest(
    wedding_id: UUID, guest_id: UUID, body: SeatIn, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.seat_guest(db, principal, wedding_id, guest_id, body.table_id, body.seat_number)


@router.delete(
    f"{W}/guests/{{guest_id}}", status_code=204, responses=_WRITE, summary="Gość bez miejsca"
)
def unseat_guest(
    wedding_id: UUID, guest_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.unseat_guest(db, principal, wedding_id, guest_id)


# --- stoły ---------------------------------------------------------------------------------


@router.get(f"{W}/tables", responses=_READ, summary="Stoły")
def list_tables(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> list[TableOut]:
    return [_table_out(t) for t in service.list_tables(db, principal, wedding_id)]


@router.post(f"{W}/tables", status_code=201, responses=_WRITE, summary="Nowy stół")
def create_table(
    wedding_id: UUID, body: TableCreate, principal: CurrentPrincipal, db: DbSession
) -> TableOut:
    return _table_out(service.create_table(db, principal, wedding_id, body.model_dump()))


@router.get(f"{W}/tables/{{table_id}}", responses=_READ, summary="Stół (ETag)")
def get_table(
    wedding_id: UUID, table_id: UUID, principal: CurrentPrincipal, db: DbSession, response: Response
) -> TableOut:
    table = service.get_table(db, principal, wedding_id, table_id)
    response.headers["ETag"] = etag(table.version)
    return _table_out(table)


@router.patch(
    f"{W}/tables/{{table_id}}",
    responses={**_WRITE, 428: {"description": "Brak If-Match"}},
    summary="Edycja stołu (If-Match)",
)
def update_table(
    wedding_id: UUID,
    table_id: UUID,
    principal: CurrentPrincipal,
    body: TableUpdate,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> TableOut:
    table = service.update_table(
        db, principal, wedding_id, table_id, body.model_dump(exclude_unset=True), version
    )
    response.headers["ETag"] = etag(table.version)
    return _table_out(table)


@router.delete(
    f"{W}/tables/{{table_id}}",
    status_code=204,
    responses=_WRITE,
    summary="Usunięcie stołu (goście wracają do listy bez miejsca)",
)
def delete_table(
    wedding_id: UUID, table_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.delete_table(db, principal, wedding_id, table_id)


# --- reguły --------------------------------------------------------------------------------


@router.get(f"{W}/rules", responses=_READ, summary="Reguły „razem” i „osobno”")
def list_rules(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> list[RuleOut]:
    return [_rule_out(r) for r in service.list_rules(db, principal, wedding_id)]


@router.post(f"{W}/rules", status_code=201, responses=_WRITE, summary="Nowa reguła dla pary osób")
def create_rule(
    wedding_id: UUID, body: RuleCreate, principal: CurrentPrincipal, db: DbSession
) -> RuleOut:
    return _rule_out(service.create_rule(db, principal, wedding_id, body.model_dump()))


@router.delete(
    f"{W}/rules/{{rule_id}}", status_code=204, responses=_WRITE, summary="Usunięcie reguły"
)
def delete_rule(
    wedding_id: UUID, rule_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.delete_rule(db, principal, wedding_id, rule_id)
