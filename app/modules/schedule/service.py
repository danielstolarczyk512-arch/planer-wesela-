"""Harmonogram dnia ślubu: punkty programu, zależności, konflikty, przesunięcia, szablon."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core import clock, ratelimit
from app.core.db import utcnow
from app.core.errors import Conflict, NotFound, Unprocessable
from app.core.security import hash_token, new_token
from app.modules.audit import service as audit
from app.modules.identity.service import Principal
from app.modules.schedule import conflicts as engine
from app.modules.schedule import templates
from app.modules.schedule.models import ScheduleDependency, ScheduleItem, VendorDayLink
from app.modules.vendors import service as vendors
from app.modules.vendors.models import Vendor
from app.modules.workspace.models import Event, Wedding, WeddingMember
from app.modules.workspace.permissions import Action, authorize


def _conflict() -> Conflict:
    return Conflict("Punkt programu zmienił się w międzyczasie.", code="conflict.version_mismatch")


def _record(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    entity_id: UUID,
    action: str,
    changes: dict[str, Any] | None = None,
) -> None:
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="schedule_item",
        entity_id=entity_id,
        wedding_id=wedding_id,
        action=action,
        changes=changes,
    )


def _get(db: Session, wedding_id: UUID, item_id: UUID) -> ScheduleItem:
    item = db.get(ScheduleItem, item_id)
    if item is None or item.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono punktu programu.", code="schedule.not_found")
    return item


def _check_refs(db: Session, wedding_id: UUID, data: dict[str, Any]) -> None:
    if data.get("vendor_id"):
        vendors.get_in_wedding(db, wedding_id, data["vendor_id"])
    if data.get("event_id"):
        event = db.get(Event, data["event_id"])
        if event is None or event.wedding_id != wedding_id:
            raise NotFound("Nie znaleziono wydarzenia.", code="event.not_found")
    if (
        data.get("responsible_user_id")
        and db.get(WeddingMember, (wedding_id, data["responsible_user_id"])) is None
    ):
        raise Unprocessable(
            "Osoba odpowiedzialna musi być członkiem wesela (lub wpisz responsible_name).",
            code="schedule.invalid_responsible",
        )


def dependencies(db: Session, item_ids: list[UUID]) -> dict[UUID, list[UUID]]:
    out: dict[UUID, list[UUID]] = defaultdict(list)
    if item_ids:
        for d in db.scalars(
            select(ScheduleDependency).where(ScheduleDependency.item_id.in_(item_ids))
        ):
            out[d.item_id].append(d.depends_on_item_id)
    return out


def items_of(db: Session, wedding_id: UUID) -> list[ScheduleItem]:
    return list(
        db.scalars(
            select(ScheduleItem)
            .where(ScheduleItem.wedding_id == wedding_id)
            .order_by(ScheduleItem.starts_at, ScheduleItem.created_at)
        )
    )


def engine_items(
    db: Session, items: list[ScheduleItem], starts_override: dict[UUID, datetime] | None = None
) -> list[engine.Item]:
    deps = dependencies(db, [i.id for i in items])
    vendor_ids = {i.vendor_id for i in items if i.vendor_id}
    booked = (
        {
            v.id: v.status == "booked"
            for v in db.scalars(select(Vendor).where(Vendor.id.in_(vendor_ids)))
        }
        if vendor_ids
        else {}
    )
    event_ids = {i.event_id for i in items if i.event_id}
    windows = (
        {
            e.id: (e.starts_at, e.ends_at)
            for e in db.scalars(select(Event).where(Event.id.in_(event_ids)))
        }
        if event_ids
        else {}
    )
    overrides = starts_override or {}
    return [
        engine.Item(
            id=i.id,
            title=i.title,
            starts_at=overrides.get(i.id, i.starts_at),
            duration_minutes=i.duration_minutes,
            buffer_before_minutes=i.buffer_before_minutes,
            buffer_after_minutes=i.buffer_after_minutes,
            vendor_id=i.vendor_id,
            vendor_booked=booked.get(i.vendor_id, True) if i.vendor_id else True,
            person=str(i.responsible_user_id)
            if i.responsible_user_id
            else (" ".join(i.responsible_name.lower().split()) if i.responsible_name else None),
            event_window=windows.get(i.event_id) if i.event_id else None,
            depends_on=tuple(deps[i.id]),
        )
        for i in items
    ]


# --- odczyt -----------------------------------------------------------------------------


def list_items(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    *,
    event_id: UUID | None,
    vendor_id: UUID | None,
) -> tuple[list[ScheduleItem], list[engine.Conflict]]:
    authorize(db, principal.user.id, wedding_id, Action.DAY_READ)
    all_items = items_of(db, wedding_id)
    found = engine.detect(engine_items(db, all_items))
    shown = [
        i
        for i in all_items
        if (event_id is None or i.event_id == event_id)
        and (vendor_id is None or i.vendor_id == vendor_id)
    ]
    return shown, found


def detect_conflicts(db: Session, principal: Principal, wedding_id: UUID) -> list[engine.Conflict]:
    authorize(db, principal.user.id, wedding_id, Action.DAY_READ)
    return engine.detect(engine_items(db, items_of(db, wedding_id)))


def get_item(db: Session, principal: Principal, wedding_id: UUID, item_id: UUID) -> ScheduleItem:
    authorize(db, principal.user.id, wedding_id, Action.DAY_READ)
    return _get(db, wedding_id, item_id)


# --- zapis ---------------------------------------------------------------------------------


def create_item(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]
) -> ScheduleItem:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    _check_refs(db, wedding_id, data)
    item = ScheduleItem(wedding_id=wedding_id, **data)
    db.add(item)
    db.flush()
    _record(db, principal, wedding_id, item.id, "create")
    db.commit()
    return item


def update_item(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    item_id: UUID,
    data: dict[str, Any],
    version: int,
) -> ScheduleItem:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    item = _get(db, wedding_id, item_id)
    if item.version != version:
        raise _conflict()
    _check_refs(db, wedding_id, data)
    before = {k: getattr(item, k) for k in data}
    for k, v in data.items():
        setattr(item, k, v)
    _record(db, principal, wedding_id, item.id, "update", audit.diff(before, data))
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise _conflict() from exc
    return item


def delete_item(db: Session, principal: Principal, wedding_id: UUID, item_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    item = _get(db, wedding_id, item_id)
    db.delete(item)
    _record(db, principal, wedding_id, item_id, "delete")
    db.commit()


def _creates_cycle(db: Session, item_id: UUID, depends_on: UUID) -> bool:
    stack, seen = [depends_on], set()
    while stack:
        current = stack.pop()
        if current == item_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(
            db.scalars(
                select(ScheduleDependency.depends_on_item_id).where(
                    ScheduleDependency.item_id == current
                )
            )
        )
    return False


def add_dependency(
    db: Session, principal: Principal, wedding_id: UUID, item_id: UUID, depends_on_id: UUID
) -> ScheduleItem:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    item = _get(db, wedding_id, item_id)
    _get(db, wedding_id, depends_on_id)
    if db.get(ScheduleDependency, (item_id, depends_on_id)) is None:
        if item_id == depends_on_id or _creates_cycle(db, item_id, depends_on_id):
            raise Unprocessable("Ta zależność utworzyłaby cykl.", code="schedule.dependency_cycle")
        db.add(ScheduleDependency(item_id=item_id, depends_on_item_id=depends_on_id))
        db.commit()
    return item


def remove_dependency(
    db: Session, principal: Principal, wedding_id: UUID, item_id: UUID, depends_on_id: UUID
) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    _get(db, wedding_id, item_id)
    dep = db.get(ScheduleDependency, (item_id, depends_on_id))
    if dep is None:
        raise NotFound("Nie znaleziono zależności.", code="schedule.dependency_not_found")
    db.delete(dep)
    db.commit()


def shift(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    *,
    from_item_id: UUID,
    minutes: int,
    dry_run: bool,
) -> tuple[list[dict[str, Any]], list[engine.Conflict]]:
    """Przesuwa wskazany punkt i wszystkie późniejsze (np. ceremonia się opóźniła)."""
    authorize(db, principal.user.id, wedding_id, Action.DAY_RUN)
    anchor = _get(db, wedding_id, from_item_id)
    items = items_of(db, wedding_id)
    new_starts = engine.shifted(engine_items(db, items), anchor.starts_at, minutes)
    changes = [
        {
            "item_id": i.id,
            "title": i.title,
            "old_starts_at": clock.local(i.starts_at),
            "new_starts_at": clock.local(new_starts[i.id]),
        }
        for i in items
        if i.id in new_starts
    ]
    after = engine.detect(engine_items(db, items, new_starts))
    if not dry_run:
        for i in items:
            if i.id in new_starts:
                i.starts_at = new_starts[i.id]
        _record(
            db,
            principal,
            wedding_id,
            from_item_id,
            "shift",
            {"minutes": [None, minutes], "items": [None, len(changes)]},
        )
        try:
            db.commit()
        except StaleDataError as exc:
            db.rollback()
            raise _conflict() from exc
    return changes, after


def apply_template(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    *,
    day: Any,
    ceremony_time: Any,
    dry_run: bool,
) -> list[dict[str, Any]]:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    wedding = db.get_one(Wedding, wedding_id)
    day = day or wedding.wedding_date
    if day is None:
        raise Unprocessable(
            "Podaj datę dnia ślubu (day) albo ustaw datę ślubu.", code="schedule.date_required"
        )
    if items_of(db, wedding_id):
        raise Conflict(
            "Harmonogram nie jest pusty. Szablon można wstawić tylko do pustego.",
            code="schedule.not_empty",
        )
    ceremony_at = datetime.combine(day, ceremony_time, tzinfo=clock.WARSAW)
    events = {
        e.kind: e.id
        for e in db.scalars(
            select(Event).where(Event.wedding_id == wedding_id).order_by(Event.created_at)
        )
    }
    steps = templates.steps(wedding.ceremony_type)
    plan = [
        {
            "code": s.code,
            "title": s.title,
            "starts_at": ceremony_at + timedelta(minutes=s.offset),
            "duration_minutes": s.duration,
            "buffer_before_minutes": s.buffer_before,
            "buffer_after_minutes": s.buffer_after,
            "preparations": s.preparations,
            "event_id": events.get(s.event_kind) if s.event_kind else None,
        }
        for s in steps
    ]
    if dry_run:
        return plan
    created = {
        p["code"]: ScheduleItem(
            wedding_id=wedding_id, **{k: v for k, v in p.items() if k != "code"}
        )
        for p in plan
    }
    db.add_all(created.values())
    db.flush()
    for s in steps:
        for dep in s.depends_on:
            db.add(
                ScheduleDependency(item_id=created[s.code].id, depends_on_item_id=created[dep].id)
            )
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="schedule_item",
        entity_id=wedding_id,
        wedding_id=wedding_id,
        action="apply_template",
        changes={"template": [None, templates.TEMPLATE_VERSION]},
    )
    db.commit()
    return plan


# --- link z programem dnia dla usługodawcy -------------------------------------------------


def _active_link(db: Session, vendor_id: UUID) -> VendorDayLink | None:
    return db.scalars(
        select(VendorDayLink).where(
            VendorDayLink.vendor_id == vendor_id, VendorDayLink.revoked_at.is_(None)
        )
    ).first()


def _revoke_links(db: Session, vendor_id: UUID) -> None:
    db.execute(
        update(VendorDayLink)
        .where(VendorDayLink.vendor_id == vendor_id, VendorDayLink.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def day_link_status(
    db: Session, principal: Principal, wedding_id: UUID, vendor_id: UUID
) -> VendorDayLink | None:
    authorize(db, principal.user.id, wedding_id, Action.DAY_READ)
    vendors.get_in_wedding(db, wedding_id, vendor_id)
    return _active_link(db, vendor_id)


CATERING_CATEGORIES = ("venue", "catering")


def create_day_link(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    vendor_id: UUID,
    *,
    share_catering: bool = False,
) -> str:
    """Nowy link (poprzedni przestaje działać). Token widoczny tylko raz."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    vendor = vendors.get_in_wedding(db, wedding_id, vendor_id)
    if share_catering and vendor.category not in CATERING_CATEGORIES:
        raise Unprocessable(
            "Listę diet i plan stołów można udostępnić tylko sali lub cateringowi.",
            code="day_link.catering_not_allowed",
        )
    _revoke_links(db, vendor_id)
    token, token_hash = new_token()
    db.add(
        VendorDayLink(
            wedding_id=wedding_id,
            vendor_id=vendor_id,
            token_hash=token_hash,
            share_catering=share_catering,
        )
    )
    _record(
        db,
        principal,
        wedding_id,
        vendor_id,
        "day_link_create",
        {"share_catering": [None, share_catering]},
    )
    db.commit()
    return token


def revoke_day_link(db: Session, principal: Principal, wedding_id: UUID, vendor_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    vendors.get_in_wedding(db, wedding_id, vendor_id)
    _revoke_links(db, vendor_id)
    _record(db, principal, wedding_id, vendor_id, "day_link_revoke")
    db.commit()


def public_events(db: Session, wedding_id: UUID) -> list[dict[str, Any]]:
    events = db.scalars(
        select(Event)
        .where(Event.wedding_id == wedding_id, Event.starts_at.is_not(None))
        .order_by(Event.starts_at)
    )
    return [
        {
            "name": e.name,
            "starts_at": clock.local(e.starts_at),
            "ends_at": clock.local(e.ends_at),
            "address": e.address,
        }
        for e in events
    ]


def public_items(items: list[ScheduleItem], vendor_id: UUID) -> list[dict[str, Any]]:
    return [
        {
            "title": i.title,
            "starts_at": clock.local(i.starts_at),
            "ends_at": clock.local(i.starts_at + timedelta(minutes=i.duration_minutes)),
            "location": i.location,
            "mine": i.vendor_id == vendor_id,
            # Szczegóły tylko przy punktach tego usługodawcy.
            "preparations": i.preparations if i.vendor_id == vendor_id else None,
            "plan_b": i.plan_b if i.vendor_id == vendor_id else None,
            "notes": i.notes if i.vendor_id == vendor_id else None,
        }
        for i in items
    ]


def link_by_token(db: Session, token: str, ip: str) -> VendorDayLink:
    ratelimit.hit(db, ratelimit.key_for("day:ip", ip), 120, timedelta(minutes=10))
    link = db.scalars(
        select(VendorDayLink).where(VendorDayLink.token_hash == hash_token(token))
    ).first()
    if link is None or link.revoked_at is not None:
        raise NotFound("Link nieprawidłowy lub wyłączony.", code="day_link.not_found")
    return link


def public_day(db: Session, token: str, ip: str) -> dict[str, Any]:
    from app.modules.schedule import briefs  # informacje i wersje korzystają z tego modułu

    link = link_by_token(db, token, ip)
    link.last_used_at = utcnow()
    wedding = db.get_one(Wedding, link.wedding_id)
    vendor = db.get_one(Vendor, link.vendor_id)
    items = items_of(db, wedding.id)
    changed = max((i.updated_at for i in items), default=None)
    catering = None
    if vendor.category in CATERING_CATEGORIES:
        # Import lokalny: plan stołów zależy od gości, harmonogram tylko z niego czyta.
        from app.modules.seating.service import catering_summary

        catering = catering_summary(db, wedding.id, with_names=link.share_catering)
    content = briefs.content(db, wedding.id, vendor.id, items)
    brief = briefs.sync_version(db, vendor, content)
    from app.modules.logistics.service import vendor_runs  # transport zależy od gości

    runs = vendor_runs(db, wedding.id, vendor.id)
    db.commit()
    return {
        "transport": runs,
        "catering": catering,
        "wedding_name": wedding.name,
        "wedding_date": wedding.wedding_date,
        "vendor_name": vendor.name,
        "vendor_category": vendor.category,
        "updated_at": changed,
        "events": content["events"],
        "items": content["items"],
        "brief": content["brief"],
        "music": content.get("music", []),
        "photo_groups": content.get("photo_groups", []),
        "prep": content.get("prep", []),
        "version": brief.content_version,
        "acknowledged_version": brief.ack_version,
        "acknowledged_at": brief.ack_at,
        "up_to_date": brief.ack_hash is not None and brief.ack_hash == brief.content_hash,
    }
