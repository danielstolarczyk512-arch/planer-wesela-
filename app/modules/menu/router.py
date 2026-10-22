from typing import Any
from uuid import UUID

from fastapi import APIRouter

from app.core.deps import CurrentPrincipal, DbSession, IfMatchVersion
from app.modules.menu import service
from app.modules.menu.schemas import DishIn, DishUpdate, MenuOverview, ShowIn

router = APIRouter(tags=["menu"])

Responses = dict[int | str, dict[str, Any]]
_READ: Responses = {
    401: {"description": "Brak uwierzytelnienia"},
    404: {"description": "Nie znaleziono lub brak dostępu"},
}
_WRITE: Responses = {
    **_READ,
    403: {"description": "Rola nie pozwala na zapis"},
    422: {"description": "Błąd walidacji"},
}
M = "/weddings/{wedding_id}/menu"


@router.get(M, responses=_READ, summary="Menu z alergenami i ostrzeżeniami o dietach gości")
def menu(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> MenuOverview:
    return MenuOverview.model_validate(service.overview(db, principal, wedding_id))


@router.post(M, status_code=201, responses=_WRITE, summary="Nowe danie")
def create_dish(
    wedding_id: UUID, body: DishIn, principal: CurrentPrincipal, db: DbSession
) -> MenuOverview:
    service.create(db, principal, wedding_id, body.model_dump())
    return MenuOverview.model_validate(service.overview(db, principal, wedding_id))


@router.put(f"{M}/show", responses=_WRITE, summary="Czy pokazać menu na stronie gościa")
def show_menu(wedding_id: UUID, body: ShowIn, principal: CurrentPrincipal, db: DbSession) -> ShowIn:
    return ShowIn(enabled=service.set_show_to_guests(db, principal, wedding_id, body.enabled))


@router.patch(
    f"{M}/{{dish_id}}",
    responses={
        **_WRITE,
        409: {"description": "Konflikt wersji"},
        428: {"description": "Brak If-Match"},
    },
    summary="Edycja dania (If-Match)",
)
def update_dish(
    wedding_id: UUID,
    dish_id: UUID,
    body: DishUpdate,
    principal: CurrentPrincipal,
    version: IfMatchVersion,
    db: DbSession,
) -> MenuOverview:
    service.update(db, principal, wedding_id, dish_id, body.model_dump(exclude_unset=True), version)
    return MenuOverview.model_validate(service.overview(db, principal, wedding_id))


@router.delete(f"{M}/{{dish_id}}", status_code=204, responses=_WRITE, summary="Usunięcie dania")
def delete_dish(
    wedding_id: UUID, dish_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.delete(db, principal, wedding_id, dish_id)
