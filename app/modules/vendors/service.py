"""Moi usługodawcy: prywatna lista firm wesela, normalizacja danych i wykrywanie duplikatów."""

import re
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.errors import Conflict, NotFound, Unprocessable
from app.modules.audit import service as audit
from app.modules.identity.service import Principal
from app.modules.vendors import checklists
from app.modules.vendors.models import Vendor, VendorChecklistItem
from app.modules.workspace.permissions import Action, authorize

NAME_SIMILARITY = 0.45
_NIP_WEIGHTS = (6, 5, 7, 2, 3, 4, 5, 6, 7)


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("0048"):
        digits = digits[4:]
    elif digits.startswith("48") and len(digits) == 11:
        digits = digits[2:]
    return digits or None


def website_domain(url: str | None) -> str | None:
    if not url:
        return None
    host = (urlparse(url).hostname or "").lower()
    return host.removeprefix("www.") or None


def nip_valid(nip: str) -> bool:
    digits = [int(d) for d in nip]
    return sum(w * d for w, d in zip(_NIP_WEIGHTS, digits[:9], strict=True)) % 11 == digits[9]


def _conflict() -> Conflict:
    return Conflict(
        "Dane zmieniły się w międzyczasie. Pobierz aktualną wersję.",
        code="conflict.version_mismatch",
    )


def _get(db: Session, wedding_id: UUID, vendor_id: UUID) -> Vendor:
    v = db.get(Vendor, vendor_id)
    if v is None or v.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono usługodawcy.", code="vendor.not_found")
    return v


def get_in_wedding(db: Session, wedding_id: UUID, vendor_id: UUID) -> Vendor:
    """Dla innych modułów (oferty, dokumenty): sprawdza przynależność do wesela."""
    return _get(db, wedding_id, vendor_id)


def _apply(vendor: Vendor, data: dict[str, Any]) -> None:
    if data.get("nip") and not nip_valid(data["nip"]):
        raise Unprocessable("Nieprawidłowy NIP (suma kontrolna).", code="vendor.invalid_nip")
    nullable = ("website_url", "email", "phone", "city", "nip", "notes", "crew_meals")
    for key, value in data.items():
        if value is None and key not in nullable:
            continue
        if key == "name":
            value = normalize_name(value)
        if key == "website_url":
            value = str(value) if value else None
            vendor.website_domain = website_domain(value)
        if key == "phone":
            vendor.phone_normalized = normalize_phone(value)
        setattr(vendor, key, value)


def duplicates(db: Session, vendor: Vendor) -> list[dict[str, Any]]:
    conditions = [func.similarity(Vendor.name, vendor.name) > NAME_SIMILARITY]
    if vendor.website_domain:
        conditions.append(Vendor.website_domain == vendor.website_domain)
    if vendor.phone_normalized:
        conditions.append(Vendor.phone_normalized == vendor.phone_normalized)
    if vendor.email:
        conditions.append(Vendor.email == vendor.email)
    if vendor.nip:
        conditions.append(Vendor.nip == vendor.nip)
    candidates = db.scalars(
        select(Vendor).where(
            Vendor.wedding_id == vendor.wedding_id, Vendor.id != vendor.id, or_(*conditions)
        )
    )
    result = []
    for c in candidates:
        reasons = []
        if vendor.website_domain and c.website_domain == vendor.website_domain:
            reasons.append("ta sama strona www")
        if vendor.phone_normalized and c.phone_normalized == vendor.phone_normalized:
            reasons.append("ten sam telefon")
        if vendor.email and c.email == vendor.email:
            reasons.append("ten sam e-mail")
        if vendor.nip and c.nip == vendor.nip:
            reasons.append("ten sam NIP")
        if not reasons:
            reasons.append("podobna nazwa")
        result.append({"id": c.id, "name": c.name, "reasons": reasons})
    return result


def list_vendors(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    *,
    category: str | None,
    status: str | None,
    q: str | None,
) -> list[Vendor]:
    authorize(db, principal.user.id, wedding_id, Action.DAY_READ)
    stmt = select(Vendor).where(Vendor.wedding_id == wedding_id)
    if category:
        stmt = stmt.where(Vendor.category == category)
    if status:
        stmt = stmt.where(Vendor.status == status)
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(
            or_(
                Vendor.name.ilike(f"%{escaped}%", escape="\\"),
                func.similarity(Vendor.name, q) > 0.3,
            )
        )
    return list(db.scalars(stmt.order_by(Vendor.category, Vendor.name)))


def create_vendor(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]
) -> Vendor:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    vendor = Vendor(wedding_id=wedding_id)
    _apply(vendor, data)
    db.add(vendor)
    db.flush()
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="vendor",
        entity_id=vendor.id,
        wedding_id=wedding_id,
        action="create",
    )
    db.commit()
    return vendor


def get_vendor(db: Session, principal: Principal, wedding_id: UUID, vendor_id: UUID) -> Vendor:
    authorize(db, principal.user.id, wedding_id, Action.DAY_READ)
    return _get(db, wedding_id, vendor_id)


def update_vendor(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    vendor_id: UUID,
    data: dict[str, Any],
    version: int,
) -> Vendor:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    vendor = _get(db, wedding_id, vendor_id)
    if vendor.version != version:
        raise _conflict()
    before = {k: getattr(vendor, k) for k in data}
    try:
        _apply(vendor, data)
    except Unprocessable:
        db.rollback()
        raise
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="vendor",
        entity_id=vendor.id,
        wedding_id=wedding_id,
        action="update",
        changes=audit.diff(before, {k: getattr(vendor, k) for k in data}),
    )
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise _conflict() from exc
    return vendor


def set_status(db: Session, vendor: Vendor, status: str) -> None:
    vendor.status = status


def delete_vendor(db: Session, principal: Principal, wedding_id: UUID, vendor_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    vendor = _get(db, wedding_id, vendor_id)
    db.delete(vendor)
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="vendor",
        entity_id=vendor_id,
        wedding_id=wedding_id,
        action="delete",
    )
    db.commit()


# --- pytania do usługodawcy i lista kontrolna umowy --------------------------------------------


def list_checklist(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    *,
    vendor_id: UUID | None,
    kind: str | None,
) -> list[VendorChecklistItem]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    stmt = select(VendorChecklistItem).where(VendorChecklistItem.wedding_id == wedding_id)
    if vendor_id:
        _get(db, wedding_id, vendor_id)
        stmt = stmt.where(VendorChecklistItem.vendor_id == vendor_id)
    if kind:
        stmt = stmt.where(VendorChecklistItem.kind == kind)
    return list(
        db.scalars(stmt.order_by(VendorChecklistItem.sort_order, VendorChecklistItem.created_at))
    )


def _next_order(db: Session, vendor_id: UUID, kind: str) -> int:
    current = db.scalar(
        select(func.max(VendorChecklistItem.sort_order)).where(
            VendorChecklistItem.vendor_id == vendor_id, VendorChecklistItem.kind == kind
        )
    )
    return (current or 0) + 1


def add_standard_checklist(
    db: Session, principal: Principal, wedding_id: UUID, vendor_id: UUID, kind: str
) -> list[VendorChecklistItem]:
    """Dodaje standardowe pytania lub punkty umowy dla kategorii usługodawcy (bez duplikatów)."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    vendor = _get(db, wedding_id, vendor_id)
    have = set(
        db.scalars(
            select(VendorChecklistItem.code).where(
                VendorChecklistItem.vendor_id == vendor_id, VendorChecklistItem.kind == kind
            )
        )
    )
    order = _next_order(db, vendor_id, kind)
    for i, t in enumerate(
        c for c in checklists.standard(kind, vendor.category) if c.code not in have
    ):
        db.add(
            VendorChecklistItem(
                wedding_id=wedding_id,
                vendor_id=vendor_id,
                kind=kind,
                code=t.code,
                text=t.text,
                sort_order=order + i,
            )
        )
    db.commit()
    return list_checklist(db, principal, wedding_id, vendor_id=vendor_id, kind=kind)


def create_checklist_item(
    db: Session, principal: Principal, wedding_id: UUID, vendor_id: UUID, data: dict[str, Any]
) -> VendorChecklistItem:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    _get(db, wedding_id, vendor_id)
    item = VendorChecklistItem(
        wedding_id=wedding_id,
        vendor_id=vendor_id,
        kind=data["kind"],
        text=data["text"].strip(),
        sort_order=_next_order(db, vendor_id, data["kind"]),
    )
    db.add(item)
    db.commit()
    return item


def _get_item(db: Session, wedding_id: UUID, item_id: UUID) -> VendorChecklistItem:
    item = db.get(VendorChecklistItem, item_id)
    if item is None or item.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono pozycji listy.", code="vendor.checklist_not_found")
    return item


def update_checklist_item(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    item_id: UUID,
    data: dict[str, Any],
    version: int,
) -> VendorChecklistItem:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    item = _get_item(db, wedding_id, item_id)
    if item.version != version:
        raise _conflict()
    if data.get("text") is not None:
        item.text = data["text"].strip()
    if data.get("status") is not None:
        item.status = data["status"]
    if "answer" in data:
        item.answer = (data["answer"] or "").strip() or None
    # Odpowiedź na pytanie oznacza je jako załatwione (bez dodatkowego kliknięcia).
    if item.kind == "question" and "status" not in data:
        item.status = "ok" if item.answer else "open"
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise _conflict() from exc
    return item


def delete_checklist_item(
    db: Session, principal: Principal, wedding_id: UUID, item_id: UUID
) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    db.delete(_get_item(db, wedding_id, item_id))
    db.commit()
