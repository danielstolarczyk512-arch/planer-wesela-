from typing import Any
from uuid import UUID

from fastapi import APIRouter, Response

from app.core.deps import CurrentPrincipal, DbSession, IfMatchVersion, etag
from app.core.schemas import Money
from app.modules.aftercare import service
from app.modules.aftercare.schemas import (
    AfterWedding,
    CheckIn,
    DeliverableCreate,
    DeliverableUpdate,
)

router = APIRouter(tags=["po weselu"])

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
W = "/weddings/{wedding_id}"


def _out(db: DbSession, principal: CurrentPrincipal, wedding_id: UUID) -> AfterWedding:
    o = service.overview(db, principal, wedding_id)
    o["open_payments"] = [{**p, "amount": Money(amount=p["amount"])} for p in o["open_payments"]]
    return AfterWedding.model_validate(o)


@router.get(
    f"{W}/after-wedding",
    responses=_READ,
    summary="Po weselu: dopłaty, co mają oddać usługodawcy, zmiana nazwiska, podziękowania",
)
def after_wedding(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> AfterWedding:
    return _out(db, principal, wedding_id)


@router.post(
    f"{W}/deliverables",
    status_code=201,
    responses=_WRITE,
    summary="Nowa rzecz do odebrania od usługodawcy (np. zdjęcia, film)",
)
def create_deliverable(
    wedding_id: UUID, body: DeliverableCreate, principal: CurrentPrincipal, db: DbSession
) -> AfterWedding:
    service.create_deliverable(db, principal, wedding_id, body.model_dump())
    return _out(db, principal, wedding_id)


@router.patch(
    f"{W}/deliverables/{{deliverable_id}}",
    responses={**_WRITE, 428: {"description": "Brak If-Match"}},
    summary="Edycja lub „odebrane” (If-Match)",
)
def update_deliverable(
    wedding_id: UUID,
    deliverable_id: UUID,
    body: DeliverableUpdate,
    principal: CurrentPrincipal,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> AfterWedding:
    d = service.update_deliverable(
        db, principal, wedding_id, deliverable_id, body.model_dump(exclude_unset=True), version
    )
    response.headers["ETag"] = etag(d.version)
    return _out(db, principal, wedding_id)


@router.delete(
    f"{W}/deliverables/{{deliverable_id}}",
    status_code=204,
    responses=_WRITE,
    summary="Usunięcie pozycji",
)
def delete_deliverable(
    wedding_id: UUID, deliverable_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.delete_deliverable(db, principal, wedding_id, deliverable_id)


@router.put(
    f"{W}/after-checks/{{code}}",
    responses=_WRITE,
    summary="Odhaczenie pozycji listy zmiany nazwiska",
)
def set_check(
    wedding_id: UUID, code: str, body: CheckIn, principal: CurrentPrincipal, db: DbSession
) -> AfterWedding:
    service.set_check(db, principal, wedding_id, code, body.done)
    return _out(db, principal, wedding_id)
