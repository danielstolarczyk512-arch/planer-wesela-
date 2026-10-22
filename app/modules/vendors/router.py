from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.core.deps import CurrentPrincipal, DbSession, IfMatchVersion, etag
from app.modules.vendors import service
from app.modules.vendors.models import CATEGORIES, Vendor, VendorChecklistItem
from app.modules.vendors.schemas import (
    CategoryInfo,
    ChecklistItemCreate,
    ChecklistItemOut,
    ChecklistItemUpdate,
    ChecklistKind,
    ChecklistStandardIn,
    VendorCategory,
    VendorCreate,
    VendorOut,
    VendorStatus,
    VendorUpdate,
)

router = APIRouter(tags=["usługodawcy"])

Responses = dict[int | str, dict[str, Any]]
_READ: Responses = {
    401: {"description": "Brak uwierzytelnienia"},
    404: {"description": "Nie znaleziono lub brak dostępu"},
}
_WRITE: Responses = {
    **_READ,
    403: {"description": "Rola tylko do odczytu"},
    422: {"description": "Błąd walidacji"},
}
_PATCH: Responses = {
    **_WRITE,
    409: {"description": "Konflikt wersji"},
    428: {"description": "Brak If-Match"},
}
W = "/weddings/{wedding_id}"


def vendor_out(db: DbSession, v: Vendor, with_duplicates: bool = False) -> VendorOut:
    return VendorOut.model_validate(
        {
            "id": v.id,
            "name": v.name,
            "category": v.category,
            "category_label": CATEGORIES[v.category][0],
            "website_url": v.website_url,
            "email": v.email,
            "phone": v.phone,
            "city": v.city,
            "nip": v.nip,
            "status": v.status,
            "notes": v.notes,
            "crew_meals": v.crew_meals,
            "version": v.version,
            "updated_at": v.updated_at,
            "possible_duplicates": service.duplicates(db, v) if with_duplicates else [],
        }
    )


@router.get("/vendor-categories", summary="Kategorie usługodawców")
def vendor_categories() -> list[CategoryInfo]:
    return [
        CategoryInfo(slug=k, label=label, budget_category=budget)
        for k, (label, budget) in CATEGORIES.items()
    ]


@router.get(
    f"{W}/vendors",
    responses=_READ,
    summary="Moi usługodawcy (filtry: kategoria, status, wyszukiwanie)",
)
def list_vendors(
    wedding_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    category: VendorCategory | None = None,
    status: VendorStatus | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> list[VendorOut]:
    return [
        vendor_out(db, v)
        for v in service.list_vendors(
            db, principal, wedding_id, category=category, status=status, q=q
        )
    ]


@router.post(
    f"{W}/vendors",
    status_code=201,
    responses=_WRITE,
    summary="Dodanie usługodawcy (odpowiedź wskazuje możliwe duplikaty)",
)
def create_vendor(
    wedding_id: UUID, body: VendorCreate, principal: CurrentPrincipal, db: DbSession
) -> VendorOut:
    v = service.create_vendor(db, principal, wedding_id, body.model_dump())
    return vendor_out(db, v, with_duplicates=True)


@router.get(f"{W}/vendors/{{vendor_id}}", responses=_READ, summary="Usługodawca")
def get_vendor(
    wedding_id: UUID,
    vendor_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    response: Response,
) -> VendorOut:
    v = service.get_vendor(db, principal, wedding_id, vendor_id)
    response.headers["ETag"] = etag(v.version)
    return vendor_out(db, v, with_duplicates=True)


@router.patch(
    f"{W}/vendors/{{vendor_id}}", responses=_PATCH, summary="Edycja usługodawcy (If-Match)"
)
def update_vendor(
    wedding_id: UUID,
    vendor_id: UUID,
    principal: CurrentPrincipal,
    body: VendorUpdate,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> VendorOut:
    v = service.update_vendor(
        db, principal, wedding_id, vendor_id, body.model_dump(exclude_unset=True), version
    )
    response.headers["ETag"] = etag(v.version)
    return vendor_out(db, v, with_duplicates=True)


@router.delete(
    f"{W}/vendors/{{vendor_id}}",
    status_code=204,
    responses=_WRITE,
    summary="Usunięcie usługodawcy (wraz z jego ofertami)",
)
def delete_vendor(
    wedding_id: UUID, vendor_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.delete_vendor(db, principal, wedding_id, vendor_id)


def item_out(item: VendorChecklistItem) -> ChecklistItemOut:
    return ChecklistItemOut.model_validate(item, from_attributes=True)


@router.get(
    f"{W}/vendor-checklist",
    responses=_READ,
    summary="Pytania do usługodawców i listy kontrolne umów (filtry: usługodawca, rodzaj)",
)
def list_checklist(
    wedding_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    vendor_id: UUID | None = None,
    kind: ChecklistKind | None = None,
) -> list[ChecklistItemOut]:
    items = service.list_checklist(db, principal, wedding_id, vendor_id=vendor_id, kind=kind)
    return [item_out(i) for i in items]


@router.post(
    f"{W}/vendors/{{vendor_id}}/checklist/standard",
    responses=_WRITE,
    summary="Dodaj standardowe pytania lub listę kontrolną umowy dla kategorii usługodawcy",
)
def add_standard_checklist(
    wedding_id: UUID,
    vendor_id: UUID,
    body: ChecklistStandardIn,
    principal: CurrentPrincipal,
    db: DbSession,
) -> list[ChecklistItemOut]:
    items = service.add_standard_checklist(db, principal, wedding_id, vendor_id, body.kind)
    return [item_out(i) for i in items]


@router.post(
    f"{W}/vendors/{{vendor_id}}/checklist",
    status_code=201,
    responses=_WRITE,
    summary="Własne pytanie lub punkt umowy",
)
def create_checklist_item(
    wedding_id: UUID,
    vendor_id: UUID,
    body: ChecklistItemCreate,
    principal: CurrentPrincipal,
    db: DbSession,
) -> ChecklistItemOut:
    return item_out(
        service.create_checklist_item(db, principal, wedding_id, vendor_id, body.model_dump())
    )


@router.patch(
    f"{W}/vendor-checklist/{{item_id}}",
    responses=_PATCH,
    summary="Odpowiedź lub status punktu (If-Match)",
)
def update_checklist_item(
    wedding_id: UUID,
    item_id: UUID,
    principal: CurrentPrincipal,
    body: ChecklistItemUpdate,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> ChecklistItemOut:
    item = service.update_checklist_item(
        db, principal, wedding_id, item_id, body.model_dump(exclude_unset=True), version
    )
    response.headers["ETag"] = etag(item.version)
    return item_out(item)


@router.delete(
    f"{W}/vendor-checklist/{{item_id}}",
    status_code=204,
    responses=_WRITE,
    summary="Usuń punkt listy",
)
def delete_checklist_item(
    wedding_id: UUID, item_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.delete_checklist_item(db, principal, wedding_id, item_id)
