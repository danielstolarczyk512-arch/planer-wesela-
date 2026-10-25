"""Odczyt katalogu dla par (tylko opublikowane, publiczne pola) i obsługa administratora."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import Conflict, NotFound, Unprocessable
from app.modules.audit import service as audit
from app.modules.catalog.ingest import evaluate_publication, vendor_group
from app.modules.catalog.models import (
    CatalogVendor,
    PublicPackage,
    ReviewItem,
    VendorFact,
    VendorSource,
)
from app.modules.vendors.models import CATEGORIES

MAX_PAGE = 50


@dataclass
class VendorCard:
    vendor: CatalogVendor
    facts: list[VendorFact]
    packages: list[PublicPackage]
    sources: list[VendorSource]


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _cards(db: Session, vendors: list[CatalogVendor]) -> list[VendorCard]:
    if not vendors:
        return []
    groups = {v.id: vendor_group(db, v.id) for v in vendors}
    all_ids = {i for ids in groups.values() for i in ids}
    facts = db.scalars(
        select(VendorFact)
        .where(VendorFact.catalog_vendor_id.in_(all_ids), VendorFact.is_current.is_(True))
        .order_by(VendorFact.observed_at.desc())
    ).all()
    packages = db.scalars(
        select(PublicPackage)
        .where(PublicPackage.catalog_vendor_id.in_(all_ids), PublicPackage.is_current.is_(True))
        .order_by(PublicPackage.kind, PublicPackage.price_from)
    ).all()
    sources = db.scalars(
        select(VendorSource).where(VendorSource.catalog_vendor_id.in_(all_ids))
    ).all()
    return [
        VendorCard(
            vendor=v,
            facts=[f for f in facts if f.catalog_vendor_id in groups[v.id]],
            packages=[p for p in packages if p.catalog_vendor_id in groups[v.id]],
            sources=[s for s in sources if s.catalog_vendor_id in groups[v.id]],
        )
        for v in vendors
    ]


def list_published(
    db: Session,
    *,
    category: str | None,
    city: str | None,
    q: str | None,
    limit: int,
    offset: int,
) -> tuple[list[VendorCard], int]:
    query = select(CatalogVendor).where(
        CatalogVendor.publication_status == "published", CatalogVendor.merged_into_id.is_(None)
    )
    if category:
        if category not in CATEGORIES:
            raise Unprocessable("Nieznana kategoria.", code="catalog.bad_category")
        query = query.where(CatalogVendor.category == category)
    if city:
        pattern = f"%{_escape_like(city.strip())}%"
        query = query.where(
            or_(
                CatalogVendor.city.ilike(pattern, escape="\\"),
                CatalogVendor.service_area.ilike(pattern, escape="\\"),
            )
        )
    if q:
        query = query.where(CatalogVendor.name.ilike(f"%{_escape_like(q.strip())}%", escape="\\"))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    vendors = list(
        db.scalars(
            query.order_by(CatalogVendor.name, CatalogVendor.id)
            .limit(min(limit, MAX_PAGE))
            .offset(offset)
        )
    )
    return _cards(db, vendors), total


def get_published(db: Session, vendor_id: UUID) -> VendorCard:
    vendor = db.get(CatalogVendor, vendor_id)
    if vendor is None or vendor.publication_status != "published" or vendor.merged_into_id:
        raise NotFound("Nie znaleziono firmy w katalogu.", code="catalog.vendor_not_found")
    return _cards(db, [vendor])[0]


def freshness(card: VendorCard, now: datetime) -> tuple[str, datetime | None]:
    """'fresh' | 'stale' | 'unknown' — najświeższy dowód wśród aktualnych faktów i pakietów."""
    dates = [f.observed_at for f in card.facts] + [p.observed_at for p in card.packages]
    if not dates:
        return "unknown", None
    newest = max(dates)
    valid = [p.valid_until for p in card.packages if p.valid_until] or [
        f.valid_until for f in card.facts if f.valid_until
    ]
    if valid and max(valid) < now:
        return "stale", newest
    return "fresh", newest


# --- administrator --------------------------------------------------------------------------


def list_all(db: Session, status: str | None, limit: int, offset: int) -> list[CatalogVendor]:
    query = select(CatalogVendor).order_by(CatalogVendor.created_at.desc())
    if status:
        query = query.where(CatalogVendor.publication_status == status)
    return list(db.scalars(query.limit(min(limit, 200)).offset(offset)))


def set_status(db: Session, admin_id: UUID, vendor_id: UUID, status: str) -> CatalogVendor:
    vendor = db.get(CatalogVendor, vendor_id)
    if vendor is None:
        raise NotFound("Nie znaleziono firmy.", code="catalog.vendor_not_found")
    if status not in ("published", "hidden", "draft", "needs_review"):
        raise Unprocessable("Nieznany status.", code="catalog.bad_status")
    before = vendor.publication_status
    vendor.publication_status = status
    audit.record(
        db,
        actor_type="admin",
        actor_id=admin_id,
        entity_type="catalog_vendor",
        entity_id=vendor.id,
        action="set_status",
        changes={"from": before, "to": status},
    )
    db.commit()
    return vendor


def set_tags(db: Session, admin_id: UUID, vendor_id: UUID, tags: list[str]) -> CatalogVendor:
    """Tagi stylu potwierdza człowiek; dopasowanie opiera się tylko na nich (nie na obrazach)."""
    vendor = db.get(CatalogVendor, vendor_id)
    if vendor is None:
        raise NotFound("Nie znaleziono firmy.", code="catalog.vendor_not_found")
    clean = list(dict.fromkeys(t.strip().lower()[:40] for t in tags if t.strip()))
    vendor.tags = clean
    audit.record(
        db,
        actor_type="admin",
        actor_id=admin_id,
        entity_type="catalog_vendor",
        entity_id=vendor.id,
        action="set_tags",
        changes={"tags": clean},
    )
    db.commit()
    return vendor


def merge(db: Session, admin_id: UUID, vendor_id: UUID, target_id: UUID) -> CatalogVendor:
    """Scalenie odwracalne: dane zostają przy firmie, katalog agreguje je pod docelową."""
    if vendor_id == target_id:
        raise Unprocessable("Nie można scalić firmy z samą sobą.", code="catalog.merge_self")
    vendor, target = db.get(CatalogVendor, vendor_id), db.get(CatalogVendor, target_id)
    if vendor is None or target is None:
        raise NotFound("Nie znaleziono firmy.", code="catalog.vendor_not_found")
    if target.merged_into_id is not None or vendor.merged_into_id is not None:
        raise Conflict("Jedna z firm jest już scalona.", code="catalog.already_merged")
    if db.scalar(
        select(func.count())
        .select_from(CatalogVendor)
        .where(CatalogVendor.merged_into_id == vendor.id)
    ):
        raise Conflict(
            "Do tej firmy są scalone inne — najpierw cofnij te scalenia.",
            code="catalog.has_children",
        )
    vendor.merged_into_id = target.id
    _close_merge_reviews(db, vendor, f"Scalono z {target.id} przez administratora.")
    audit.record(
        db,
        actor_type="admin",
        actor_id=admin_id,
        entity_type="catalog_vendor",
        entity_id=vendor.id,
        action="merge",
        changes={"into": str(target.id)},
    )
    db.flush()
    evaluate_publication(db, target)
    db.commit()
    return target


def unmerge(db: Session, admin_id: UUID, vendor_id: UUID) -> CatalogVendor:
    vendor = db.get(CatalogVendor, vendor_id)
    if vendor is None:
        raise NotFound("Nie znaleziono firmy.", code="catalog.vendor_not_found")
    if vendor.merged_into_id is None:
        raise Conflict("Ta firma nie jest scalona.", code="catalog.not_merged")
    into = vendor.merged_into_id
    vendor.merged_into_id = None
    db.flush()
    evaluate_publication(db, vendor)
    audit.record(
        db,
        actor_type="admin",
        actor_id=admin_id,
        entity_type="catalog_vendor",
        entity_id=vendor.id,
        action="unmerge",
        changes={"was_into": str(into)},
    )
    db.commit()
    return vendor


def _close_merge_reviews(db: Session, vendor: CatalogVendor, resolution: str) -> None:
    for item in db.scalars(
        select(ReviewItem).where(
            ReviewItem.catalog_vendor_id == vendor.id,
            ReviewItem.kind == "ambiguous_merge",
            ReviewItem.state == "open",
        )
    ):
        item.state, item.resolution, item.resolved_at = "resolved", resolution[:300], utcnow()


def list_reviews(db: Session, state: str, limit: int) -> list[ReviewItem]:
    return list(
        db.scalars(
            select(ReviewItem)
            .where(ReviewItem.state == state)
            .order_by(ReviewItem.created_at.desc())
            .limit(min(limit, 200))
        )
    )


def resolve_review(
    db: Session, admin_id: UUID, review_id: UUID, resolution: str, confirm_package_id: UUID | None
) -> ReviewItem:
    """Zamknięcie wpisu. Przy konflikcie cen administrator wskazuje pakiet, który jest właściwy."""
    item = db.get(ReviewItem, review_id)
    if item is None:
        raise NotFound("Nie znaleziono wpisu.", code="catalog.review_not_found")
    if item.state != "open":
        raise Conflict("Wpis jest już zamknięty.", code="catalog.review_closed")
    if item.kind == "conflict" and confirm_package_id is not None:
        ids = {UUID(x) for x in item.details.get("package_ids", [])}
        if confirm_package_id not in ids:
            raise Unprocessable("Pakiet nie należy do tego konfliktu.", code="catalog.bad_package")
        for p in db.scalars(select(PublicPackage).where(PublicPackage.id.in_(ids))):
            if p.id == confirm_package_id:
                p.verification = "confirmed"
            elif p.is_current:
                p.is_current, p.superseded_at, p.supersede_reason = False, utcnow(), "admin_choice"
    item.state, item.resolution = "resolved", resolution[:300]
    item.resolved_by, item.resolved_at = admin_id, utcnow()
    audit.record(
        db,
        actor_type="admin",
        actor_id=admin_id,
        entity_type="catalog_review",
        entity_id=item.id,
        action="resolve",
        changes={"kind": item.kind},
    )
    db.commit()
    return item


def stats(db: Session) -> dict[str, Any]:
    by_status = dict(
        db.execute(
            select(CatalogVendor.publication_status, func.count())
            .where(CatalogVendor.merged_into_id.is_(None))
            .group_by(CatalogVendor.publication_status)
        ).all()
    )
    return {
        "vendors_by_status": by_status,
        "open_reviews": db.scalar(
            select(func.count()).select_from(ReviewItem).where(ReviewItem.state == "open")
        )
        or 0,
        "now": utcnow().isoformat(),
    }
