"""Informacje dla usługodawców i potwierdzanie wersji programu („kto zna aktualny program”).

Wersja to kolejny numer treści linku usługodawcy: program dnia, wydarzenia i informacje
dla niego. Numer rośnie przy pierwszym odczycie po zmianie (link, lista statusów), więc
kilka zmian między odczytami daje jedną nową wersję. Liczby dla kuchni są poza wersją.
"""

import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import Conflict
from app.modules.audit import service as audit
from app.modules.identity.service import Principal
from app.modules.schedule import service as schedule
from app.modules.schedule.models import ScheduleItem, VendorBrief, VendorDayLink
from app.modules.vendors import service as vendors
from app.modules.vendors.models import Vendor
from app.modules.workspace.permissions import Action, authorize

BRIEF_FIELDS = ("must", "avoid", "people", "notes", "contact")


def _get_or_create(db: Session, vendor: Vendor) -> VendorBrief:
    brief = db.get(VendorBrief, vendor.id)
    if brief is None:
        brief = VendorBrief(
            vendor_id=vendor.id, wedding_id=vendor.wedding_id, must=[], avoid=[], people=[]
        )
        db.add(brief)
        db.flush()
    return brief


def brief_out(brief: VendorBrief | None) -> dict[str, Any]:
    if brief is None:
        return {"must": [], "avoid": [], "people": [], "notes": None, "contact": None}
    return {k: getattr(brief, k) for k in BRIEF_FIELDS}


def content(
    db: Session, wedding_id: UUID, vendor_id: UUID, items: list[ScheduleItem] | None = None
) -> dict[str, Any]:
    """Treść linku usługodawcy, od której liczona jest wersja."""
    from app.modules.schedule import music, photos, prep

    items = schedule.items_of(db, wedding_id) if items is None else items
    category = db.get_one(Vendor, vendor_id).category
    data: dict[str, Any] = {
        "events": schedule.public_events(db, wedding_id),
        "items": schedule.public_items(items, vendor_id),
        "brief": brief_out(db.get(VendorBrief, vendor_id)),
    }
    # Klucze tylko, gdy jest treść: u pozostałych usługodawców wersja się nie zmienia.
    if songs := music.vendor_list(db, wedding_id, category):
        data["music"] = songs
    if groups := photos.vendor_list(db, wedding_id, category):
        data["photo_groups"] = groups
    if slots := prep.vendor_list(db, wedding_id, category):
        data["prep"] = slots
    return data


def _hash(data: dict[str, Any]) -> str:
    raw = json.dumps(data, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def sync_version(db: Session, vendor: Vendor, data: dict[str, Any]) -> VendorBrief:
    """Numer wersji dla bieżącej treści (nowy numer, gdy treść się zmieniła)."""
    brief = _get_or_create(db, vendor)
    digest = _hash(data)
    if brief.content_hash != digest:
        brief.content_hash = digest
        brief.content_version += 1
        db.flush()
    return brief


def get_brief(db: Session, principal: Principal, wedding_id: UUID, vendor_id: UUID) -> VendorBrief:
    authorize(db, principal.user.id, wedding_id, Action.DAY_READ)
    vendor = vendors.get_in_wedding(db, wedding_id, vendor_id)
    brief = _get_or_create(db, vendor)
    db.commit()
    return brief


def save_brief(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    vendor_id: UUID,
    data: dict[str, Any],
    version: int,
) -> VendorBrief:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    vendor = vendors.get_in_wedding(db, wedding_id, vendor_id)
    brief = _get_or_create(db, vendor)
    db.refresh(brief, with_for_update=True)  # dwa równoczesne zapisy: drugi dostanie 409
    if brief.version != version:
        raise Conflict(
            "Informacje zmieniły się w międzyczasie. Pobierz aktualną wersję.",
            code="conflict.version_mismatch",
        )
    for k in BRIEF_FIELDS:
        setattr(brief, k, data[k])
    brief.version += 1
    # Bez treści do audytu (mogą być imiona członków rodziny): tylko nazwy pól.
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="vendor_brief",
        entity_id=vendor_id,
        wedding_id=wedding_id,
        action="update",
        changes={"fields": list(BRIEF_FIELDS)},
    )
    db.commit()
    return brief


def statuses(db: Session, principal: Principal, wedding_id: UUID) -> list[dict[str, Any]]:
    """Usługodawcy z aktywnym linkiem: aktualna wersja i czy ją potwierdzili."""
    authorize(db, principal.user.id, wedding_id, Action.DAY_READ)
    rows = list(
        db.execute(
            select(VendorDayLink, Vendor)
            .join(Vendor, Vendor.id == VendorDayLink.vendor_id)
            .where(VendorDayLink.wedding_id == wedding_id, VendorDayLink.revoked_at.is_(None))
            .order_by(Vendor.name)
        )
    )
    items = schedule.items_of(db, wedding_id)
    out = []
    for link, vendor in rows:
        brief = sync_version(db, vendor, content(db, wedding_id, vendor.id, items))
        out.append(
            {
                "vendor_id": vendor.id,
                "vendor_name": vendor.name,
                "category": vendor.category,
                "version": brief.content_version,
                "acknowledged_version": brief.ack_version,
                "acknowledged_at": brief.ack_at,
                "up_to_date": brief.ack_hash is not None and brief.ack_hash == brief.content_hash,
                "last_opened_at": link.last_used_at,
            }
        )
    db.commit()
    return out


def acknowledge(db: Session, token: str, ip: str, version: int) -> tuple[int, datetime]:
    """Usługodawca potwierdza przeczytanie wersji, którą widzi. Starsza wersja: 409."""
    link = schedule.link_by_token(db, token, ip)
    vendor = db.get_one(Vendor, link.vendor_id)
    brief = sync_version(db, vendor, content(db, link.wedding_id, vendor.id))
    if version != brief.content_version:
        db.commit()  # zapisujemy nowy numer wersji, żeby strona mogła go pokazać
        raise Conflict(
            "Program zmienił się, odkąd strona została otwarta. Odśwież i przeczytaj zmiany.",
            code="day_link.version_changed",
        )
    now = utcnow()
    brief.ack_hash, brief.ack_version, brief.ack_at = brief.content_hash, version, now
    link.last_used_at = utcnow()
    audit.record(
        db,
        actor_type="guest",
        actor_id=None,
        entity_type="vendor_brief",
        entity_id=vendor.id,
        wedding_id=link.wedding_id,
        action="acknowledge",
        changes={"version": version},
    )
    db.commit()
    return version, now
