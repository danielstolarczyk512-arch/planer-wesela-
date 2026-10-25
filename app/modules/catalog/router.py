from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.db import utcnow
from app.core.deps import CurrentPrincipal, DbSession
from app.core.errors import NotFound
from app.modules.catalog import service
from app.modules.catalog.schemas import (
    AdminVendorOut,
    CatalogPage,
    CatalogVendorOut,
    MergeBody,
    ResolveBody,
    ReviewOut,
    StatusBody,
    TagsBody,
    to_out,
)
from app.modules.identity.service import Principal

router = APIRouter(tags=["katalog firm"])
admin_router = APIRouter(prefix="/admin/catalog", tags=["katalog firm: administrator"])

Responses = dict[int | str, dict[str, Any]]
_READ: Responses = {
    401: {"description": "Brak uwierzytelnienia"},
    404: {"description": "Nie znaleziono"},
}


def require_admin(principal: CurrentPrincipal) -> Principal:
    """Panel badacza tylko dla `global_role=admin`; inni dostają 404 (nie ujawniamy panelu)."""
    if principal.user.global_role != "admin":
        raise NotFound("Nie znaleziono zasobu.", code="not_found")
    return principal


Admin = Annotated[Principal, Depends(require_admin)]


@router.get(
    "/catalog/vendors", responses=_READ, summary="Katalog firm (opublikowane, publiczne dane)"
)
def list_vendors(
    principal: CurrentPrincipal,
    db: DbSession,
    category: str | None = None,
    city: str | None = Query(default=None, max_length=120),
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=20, ge=1, le=service.MAX_PAGE),
    offset: int = Query(default=0, ge=0, le=10_000),
) -> CatalogPage:
    cards, total = service.list_published(
        db, category=category, city=city, q=q, limit=limit, offset=offset
    )
    now = utcnow()
    return CatalogPage(items=[to_out(c, now) for c in cards], total=total)


@router.get("/catalog/vendors/{vendor_id}", responses=_READ, summary="Firma z katalogu")
def get_vendor(vendor_id: UUID, principal: CurrentPrincipal, db: DbSession) -> CatalogVendorOut:
    return to_out(service.get_published(db, vendor_id), utcnow())


@admin_router.get("/vendors", summary="Wszystkie firmy katalogu (także niepublikowane)")
def admin_vendors(
    admin: Admin,
    db: DbSession,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AdminVendorOut]:
    return [AdminVendorOut.model_validate(v) for v in service.list_all(db, status, limit, offset)]


@admin_router.put("/vendors/{vendor_id}/status", summary="Zmiana statusu publikacji")
def admin_set_status(
    vendor_id: UUID, body: StatusBody, admin: Admin, db: DbSession
) -> AdminVendorOut:
    return AdminVendorOut.model_validate(
        service.set_status(db, admin.user.id, vendor_id, body.status)
    )


@admin_router.put("/vendors/{vendor_id}/tags", summary="Tagi stylu potwierdzone przez człowieka")
def admin_set_tags(vendor_id: UUID, body: TagsBody, admin: Admin, db: DbSession) -> AdminVendorOut:
    return AdminVendorOut.model_validate(service.set_tags(db, admin.user.id, vendor_id, body.tags))


@admin_router.post("/vendors/{vendor_id}/merge", summary="Scal firmę (odwracalne)")
def admin_merge(vendor_id: UUID, body: MergeBody, admin: Admin, db: DbSession) -> AdminVendorOut:
    return AdminVendorOut.model_validate(service.merge(db, admin.user.id, vendor_id, body.into))


@admin_router.post("/vendors/{vendor_id}/unmerge", summary="Cofnij scalenie")
def admin_unmerge(vendor_id: UUID, admin: Admin, db: DbSession) -> AdminVendorOut:
    return AdminVendorOut.model_validate(service.unmerge(db, admin.user.id, vendor_id))


@admin_router.get("/review", summary="Kolejka weryfikacji")
def admin_review(
    admin: Admin,
    db: DbSession,
    state: str = Query(default="open", pattern="^(open|resolved)$"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ReviewOut]:
    return [ReviewOut.model_validate(r) for r in service.list_reviews(db, state, limit)]


@admin_router.post("/review/{review_id}/resolve", summary="Zamknij wpis weryfikacji")
def admin_resolve(review_id: UUID, body: ResolveBody, admin: Admin, db: DbSession) -> ReviewOut:
    return ReviewOut.model_validate(
        service.resolve_review(
            db, admin.user.id, review_id, body.resolution, body.confirm_package_id
        )
    )
