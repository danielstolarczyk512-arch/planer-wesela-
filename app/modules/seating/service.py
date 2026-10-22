"""Plan stołów: stoły, przypisania gości, reguły „razem/osobno”, automatyczne usadzenie."""

import math
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core import ratelimit
from app.core.db import utcnow
from app.core.errors import Conflict, NotFound, Unprocessable
from app.core.ids import uuid7
from app.jobs.queue import enqueue
from app.modules.audit import service as audit
from app.modules.guests import service as guests_service
from app.modules.guests.models import Guest, Household
from app.modules.identity.service import Principal
from app.modules.seating import engine
from app.modules.seating.models import (
    SeatAssignment,
    SeatingAutoRun,
    SeatingRoom,
    SeatingRule,
    SeatingTable,
)
from app.modules.workspace.models import Event
from app.modules.workspace.permissions import Action, authorize

log = structlog.get_logger()

MAX_TABLES = 100
MAX_RULES = 300
AUTO_LIMIT_PER_HOUR = 30


def _record(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    entity_type: str,
    entity_id: UUID,
    action: str,
    changes: dict[str, Any] | None = None,
) -> None:
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type=entity_type,
        entity_id=entity_id,
        wedding_id=wedding_id,
        action=action,
        changes=changes,
    )


def _version_conflict() -> Conflict:
    return Conflict("Stół zmienił się w międzyczasie.", code="conflict.version_mismatch")


def _table(db: Session, wedding_id: UUID, table_id: UUID) -> SeatingTable:
    t = db.get(SeatingTable, table_id)
    if t is None or t.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono stołu.", code="seating.table_not_found")
    return t


def _guest(db: Session, wedding_id: UUID, guest_id: UUID) -> Guest:
    g = db.get(Guest, guest_id)
    if g is None or g.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono gościa.", code="guest.not_found")
    return g


def tables_of(db: Session, wedding_id: UUID) -> list[SeatingTable]:
    return list(
        db.scalars(
            select(SeatingTable)
            .where(SeatingTable.wedding_id == wedding_id)
            .order_by(SeatingTable.sort_order, SeatingTable.name, SeatingTable.id)
        )
    )


def assignments_of(db: Session, wedding_id: UUID) -> list[SeatAssignment]:
    return list(db.scalars(select(SeatAssignment).where(SeatAssignment.wedding_id == wedding_id)))


def rules_of(db: Session, wedding_id: UUID) -> list[SeatingRule]:
    return list(
        db.scalars(
            select(SeatingRule)
            .where(SeatingRule.wedding_id == wedding_id)
            .order_by(SeatingRule.created_at, SeatingRule.id)
        )
    )


def guest_name(g: Guest) -> str:
    return f"{g.first_name} {g.last_name or ''}".strip()


def _status(db: Session, wedding_id: UUID, guest_ids: list[UUID]) -> dict[UUID, str]:
    """attending / declined / pending wg przyjęcia (bez przyjęcia: wg wszystkich wydarzeń)."""
    reception = set(
        db.scalars(
            select(Event.id).where(Event.wedding_id == wedding_id, Event.kind == "reception")
        )
    )
    att = guests_service.attendance_map(db, guest_ids)
    out: dict[UUID, str] = {}
    for gid in guest_ids:
        statuses = [s for e, s in att[gid].items() if not reception or e in reception]
        if "attending" in statuses:
            out[gid] = "attending"
        elif statuses and all(s == "declined" for s in statuses):
            out[gid] = "declined"
        else:
            out[gid] = "pending"
    return out


class _Snapshot:
    """Wszystko, czego potrzebują plan, kontrola i automat — jednym zestawem zapytań."""

    def __init__(self, db: Session, wedding_id: UUID) -> None:
        rows = db.execute(
            select(Guest, Household)
            .join(Household, Household.id == Guest.household_id)
            .where(Guest.wedding_id == wedding_id)
            .order_by(Household.name, Guest.first_name, Guest.id)
        ).all()
        self.guests = {g.id: g for g, _ in rows}
        self.households = {h.id: h for _, h in rows}
        self.status = _status(db, wedding_id, list(self.guests))
        self.tables = tables_of(db, wedding_id)
        self.assignments = {a.guest_id: a for a in assignments_of(db, wedding_id)}
        self.rules = rules_of(db, wedding_id)

    def g(self, guest: Guest) -> engine.G:
        h = self.households[guest.household_id]
        return engine.G(
            id=guest.id,
            household_id=guest.household_id,
            age_group=guest.age_group,
            group=h.group_label,
            side=h.side,
            attending=self.status[guest.id] != "declined",
            name=guest_name(guest),
        )

    def t(self) -> list[engine.T]:
        return [engine.T(t.id, t.kind, t.capacity, t.name) for t in self.tables]

    def r(self) -> list[engine.Rule]:
        return [engine.Rule(r.kind, r.guest_a_id, r.guest_b_id) for r in self.rules]

    def to_seat(self, basis: str = "not_declined") -> list[Guest]:
        wanted = {"attending"} if basis == "attending" else {"attending", "pending"}
        return [
            g
            for g in self.guests.values()
            if self.status[g.id] in wanted and g.age_group != "infant"
        ]

    def issues(self, assignment: dict[UUID, UUID]) -> list[engine.Issue]:
        involved = [self.g(g) for g in self.guests.values() if g.id in assignment]
        return engine.check(involved, self.t(), self.r(), assignment)


# --- plan ---------------------------------------------------------------------------------


def plan(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    s = _Snapshot(db, wedding_id)
    by_table: dict[UUID, list[SeatAssignment]] = defaultdict(list)
    for a in s.assignments.values():
        by_table[a.table_id].append(a)

    def seated(a: SeatAssignment) -> dict[str, Any]:
        g = s.guests[a.guest_id]
        return {
            "guest_id": g.id,
            "name": guest_name(g),
            "household_id": g.household_id,
            "age_group": g.age_group,
            "seat_number": a.seat_number,
            "locked": a.locked,
        }

    tables = []
    for t in s.tables:
        rows = sorted(
            by_table[t.id],
            key=lambda a: (
                a.seat_number is None,
                a.seat_number or 0,
                s.households[s.guests[a.guest_id].household_id].name,
                guest_name(s.guests[a.guest_id]),
            ),
        )
        tables.append(
            {
                **table_dict(t),
                "guests": [seated(a) for a in rows],
                "free_seats": t.capacity - len(rows),
            }
        )
    unassigned = [
        {
            "guest_id": g.id,
            "name": guest_name(g),
            "household_id": g.household_id,
            "age_group": g.age_group,
        }
        for g in s.to_seat()
        if g.id not in s.assignments
    ]
    assignment = {gid: a.table_id for gid, a in s.assignments.items()}
    return {
        "room": room_dict(db.get(SeatingRoom, wedding_id)),
        "tables": tables,
        "unassigned": unassigned,
        "issues": [issue_dict(i) for i in s.issues(assignment)],
        "stats": {
            "tables": len(s.tables),
            "seats": sum(t.capacity for t in s.tables),
            "seated": len(s.assignments),
            "to_seat": len(unassigned),
        },
    }


def _ages(guests: list[Guest]) -> dict[str, int]:
    c = Counter(g.age_group for g in guests)
    return {
        "adults": c["adult"],
        "teens": c["teen"],
        "children": c["child"],
        "infants": c["infant"],
    }


def _diets(guests: list[Guest]) -> list[dict[str, Any]]:
    c = Counter(g.dietary_preference for g in guests if g.dietary_preference != "standard")
    return [{"diet": d, "count": n} for d, n in sorted(c.items(), key=lambda x: (-x[1], x[0]))]


def catering_summary(db: Session, wedding_id: UUID, *, with_names: bool) -> dict[str, Any]:
    """Liczby dla sali i kuchni (link usługodawcy). Bez zgody pary — bez imion i uwag.

    Potwierdzeni = obecni na przyjęciu; bez odpowiedzi osobno. Przy stołach: goście posadzeni,
    którzy nie odmówili. Uwagi dietetyczne (dane o zdrowiu) tylko przy ``with_names``.
    """
    s = _Snapshot(db, wedding_id)
    attending = [g for g in s.guests.values() if s.status[g.id] == "attending"]
    pending = sum(1 for g in s.guests.values() if s.status[g.id] == "pending")
    by_table: dict[UUID, list[Guest]] = defaultdict(list)
    for a in s.assignments.values():
        g = s.guests[a.guest_id]
        if s.status[g.id] != "declined":
            by_table[a.table_id].append(g)
    tables = []
    for t in s.tables:
        seated = sorted(by_table[t.id], key=guest_name)
        if not seated:
            continue
        tables.append(
            {
                "name": t.name,
                "count": _ages(seated),
                "diets": _diets(seated),
                "guests": [
                    {
                        "name": guest_name(g),
                        "age_group": g.age_group,
                        "diet": g.dietary_preference,
                        "diet_note": guests_service.dietary_note(g),
                    }
                    for g in seated
                ]
                if with_names
                else None,
            }
        )
    # Import lokalny: oferty zależą od gości (wycena), a tu potrzebna tylko suma posiłków.
    from app.modules.offers.service import crew_meals

    return {
        "attending": _ages(attending),
        "pending": pending,
        "diets": _diets(attending),
        "crew_meals": crew_meals(db, wedding_id),
        "tables": tables,
        "details_shared": with_names,
    }


def table_dict(t: SeatingTable) -> dict[str, Any]:
    return {
        "id": t.id,
        "name": t.name,
        "kind": t.kind,
        "shape": t.shape,
        "capacity": t.capacity,
        "sort_order": t.sort_order,
        "notes": t.notes,
        "pos_x": float(t.pos_x) if t.pos_x is not None else None,
        "pos_y": float(t.pos_y) if t.pos_y is not None else None,
        "rotation": t.rotation,
        "version": t.version,
    }


DEFAULT_ROOM = {"width_m": 20.0, "length_m": 12.0, "items": [], "version": 0}


def room_dict(room: SeatingRoom | None) -> dict[str, Any]:
    if room is None:
        return dict(DEFAULT_ROOM)
    return {
        "width_m": float(room.width_m),
        "length_m": float(room.length_m),
        "items": room.items,
        "version": room.version,
    }


def get_room(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return room_dict(db.get(SeatingRoom, wedding_id))


def save_room(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any], version: int
) -> dict[str, Any]:
    """Wymiary sali i elementy stałe. Wersja 0 = pierwszy zapis (If-Match: "0")."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    room = db.get(SeatingRoom, wedding_id)
    if (room.version if room else 0) != version:
        raise _version_conflict()
    if room is None:
        room = SeatingRoom(wedding_id=wedding_id)
        db.add(room)
    room.width_m = Decimal(str(data["width_m"]))
    room.length_m = Decimal(str(data["length_m"]))
    room.items = data["items"]
    _record(db, principal, wedding_id, "seating_room", wedding_id, "update")
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise _version_conflict() from exc
    return room_dict(room)


def table_ranks(
    tables: list[SeatingTable], room: SeatingRoom | None, target: str
) -> dict[UUID, int] | None:
    """Ranga odległości stołów od celu (0 = najbliżej). None, gdy brak pozycji celu.

    Cel: środek stołu pary młodej albo parkietu z planu sali. Stoły bez pozycji — najdalej.
    """
    point: tuple[float, float] | None = None
    if target == "head":
        head = next((t for t in tables if t.kind == "head" and t.pos_x is not None), None)
        if head is not None and head.pos_y is not None:
            point = (float(head.pos_x or 0), float(head.pos_y))
    else:
        floor = next((i for i in (room.items if room else []) if i["kind"] == "dance_floor"), None)
        if floor is not None:
            point = (float(floor["x"]), float(floor["y"]))
    if point is None:
        return None
    placed = [t for t in tables if t.kind != "head" and t.pos_x is not None and t.pos_y is not None]
    if not placed:
        return None
    by_distance = sorted(
        placed,
        key=lambda t: (math.dist(point, (float(t.pos_x or 0), float(t.pos_y or 0))), t.name),
    )
    ranks = {t.id: r for r, t in enumerate(by_distance)}
    for t in tables:
        if t.id not in ranks:
            ranks[t.id] = len(by_distance)
    return ranks


def issue_dict(i: engine.Issue) -> dict[str, Any]:
    return {
        "code": i.code,
        "severity": i.severity,
        "guest_ids": list(i.guest_ids),
        "table_ids": list(i.table_ids),
        "message": i.message,
    }


# --- stoły ---------------------------------------------------------------------------------


def list_tables(db: Session, principal: Principal, wedding_id: UUID) -> list[SeatingTable]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return tables_of(db, wedding_id)


def get_table(db: Session, principal: Principal, wedding_id: UUID, table_id: UUID) -> SeatingTable:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return _table(db, wedding_id, table_id)


def create_table(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]
) -> SeatingTable:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    count = db.scalar(
        select(func.count()).select_from(SeatingTable).where(SeatingTable.wedding_id == wedding_id)
    )
    if (count or 0) >= MAX_TABLES:
        raise Conflict(f"Limit {MAX_TABLES} stołów na wesele.", code="seating.too_many_tables")
    table = SeatingTable(wedding_id=wedding_id, **data)
    db.add(table)
    db.flush()
    _record(db, principal, wedding_id, "seating_table", table.id, "create")
    db.commit()
    return table


def update_table(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    table_id: UUID,
    data: dict[str, Any],
    version: int,
) -> SeatingTable:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    table = _table(db, wedding_id, table_id)
    if table.version != version:
        raise _version_conflict()
    before = {k: getattr(table, k) for k in data}
    for k, v in data.items():
        setattr(table, k, v)
    _record(
        db, principal, wedding_id, "seating_table", table.id, "update", audit.diff(before, data)
    )
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise _version_conflict() from exc
    return table


def delete_table(db: Session, principal: Principal, wedding_id: UUID, table_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    table = _table(db, wedding_id, table_id)
    db.delete(table)  # przypisania przy stole usuwa kaskada: goście wracają do „bez miejsca”
    _record(db, principal, wedding_id, "seating_table", table_id, "delete")
    db.commit()


# --- przypisania ---------------------------------------------------------------------------


def seat_guest(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    guest_id: UUID,
    table_id: UUID,
    seat_number: int | None,
) -> None:
    """Ręczne posadzenie: przypięte (`locked`), automat go nie przesunie."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    _guest(db, wedding_id, guest_id)
    table = _table(db, wedding_id, table_id)
    if seat_number is not None and seat_number > table.capacity:
        raise Unprocessable(
            f"Stół „{table.name}” ma {table.capacity} miejsc.", code="seating.invalid_seat"
        )
    a = db.get(SeatAssignment, guest_id)
    if a is None:
        a = SeatAssignment(guest_id=guest_id, wedding_id=wedding_id)
        db.add(a)
    a.table_id, a.seat_number, a.locked = table_id, seat_number, True
    _record(
        db, principal, wedding_id, "guest", guest_id, "seat", {"table_id": [None, str(table_id)]}
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("To miejsce jest już zajęte.", code="seating.seat_taken") from exc


def unseat_guest(db: Session, principal: Principal, wedding_id: UUID, guest_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    _guest(db, wedding_id, guest_id)
    a = db.get(SeatAssignment, guest_id)
    if a is not None:
        db.delete(a)
        _record(db, principal, wedding_id, "guest", guest_id, "unseat")
        db.commit()


def set_assignments(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    items: list[dict[str, Any]],
    *,
    replace_unlocked: bool,
) -> None:
    """Zapis wielu przypisań naraz (np. dokładnie ten wariant, który pokazał podgląd automatu)."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    guest_ids = {i["guest_id"] for i in items}
    if len(guest_ids) != len(items):
        raise Unprocessable("Gość powtarza się na liście.", code="seating.duplicate_guest")
    known_guests = set(
        db.scalars(select(Guest.id).where(Guest.wedding_id == wedding_id, Guest.id.in_(guest_ids)))
    )
    known_tables = {t.id for t in tables_of(db, wedding_id)}
    if known_guests != guest_ids:
        raise NotFound("Nie znaleziono gościa.", code="guest.not_found")
    if any(i["table_id"] not in known_tables for i in items):
        raise NotFound("Nie znaleziono stołu.", code="seating.table_not_found")
    if replace_unlocked:
        db.execute(
            delete(SeatAssignment).where(
                SeatAssignment.wedding_id == wedding_id, SeatAssignment.locked.is_(False)
            )
        )
    existing = {a.guest_id: a for a in assignments_of(db, wedding_id)}
    for i in items:
        a = existing.get(i["guest_id"])
        if a is None:
            a = SeatAssignment(guest_id=i["guest_id"], wedding_id=wedding_id, seat_number=None)
            db.add(a)
        elif a.table_id != i["table_id"]:
            a.seat_number = None  # numer miejsca dotyczył poprzedniego stołu
        a.table_id, a.locked = i["table_id"], i["locked"]
    _record(
        db,
        principal,
        wedding_id,
        "wedding",
        wedding_id,
        "seating_assign",
        {"count": [None, len(items)], "replace_unlocked": [None, replace_unlocked]},
    )
    db.commit()


def clear(db: Session, principal: Principal, wedding_id: UUID, *, include_locked: bool) -> int:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    stmt = delete(SeatAssignment).where(SeatAssignment.wedding_id == wedding_id)
    if not include_locked:
        stmt = stmt.where(SeatAssignment.locked.is_(False))
    removed = int(getattr(db.execute(stmt), "rowcount", 0) or 0)
    _record(
        db,
        principal,
        wedding_id,
        "wedding",
        wedding_id,
        "seating_clear",
        {"removed": [None, removed]},
    )
    db.commit()
    return removed


# --- reguły --------------------------------------------------------------------------------


def list_rules(db: Session, principal: Principal, wedding_id: UUID) -> list[SeatingRule]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return rules_of(db, wedding_id)


def create_rule(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]
) -> SeatingRule:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    a, b = data["guest_a_id"], data["guest_b_id"]
    if a == b:
        raise Unprocessable("Reguła dotyczy dwóch różnych osób.", code="seating.same_guest")
    _guest(db, wedding_id, a)
    _guest(db, wedding_id, b)
    count = db.scalar(
        select(func.count()).select_from(SeatingRule).where(SeatingRule.wedding_id == wedding_id)
    )
    if (count or 0) >= MAX_RULES:
        raise Conflict(f"Limit {MAX_RULES} reguł na wesele.", code="seating.too_many_rules")
    a, b = sorted([a, b])
    rule = SeatingRule(
        wedding_id=wedding_id, kind=data["kind"], guest_a_id=a, guest_b_id=b, note=data.get("note")
    )
    db.add(rule)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict(
            "Dla tej pary osób istnieje już reguła.", code="seating.rule_exists"
        ) from exc
    _record(
        db, principal, wedding_id, "seating_rule", rule.id, "create", {"kind": [None, rule.kind]}
    )
    db.commit()
    return rule


def delete_rule(db: Session, principal: Principal, wedding_id: UUID, rule_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    rule = db.get(SeatingRule, rule_id)
    if rule is None or rule.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono reguły.", code="seating.rule_not_found")
    db.delete(rule)
    _record(db, principal, wedding_id, "seating_rule", rule_id, "delete")
    db.commit()


# --- automat -------------------------------------------------------------------------------


def auto(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    *,
    basis: str,
    keep_households: bool,
    kids_table: bool,
    time_limit: int,
    dry_run: bool,
    kids_table_teens: bool = False,
    near_groups: list[str] | None = None,
    near_target: str = "head",
) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    _auto_rate_limit(db, wedding_id)
    params = {
        "basis": basis,
        "keep_households": keep_households,
        "kids_table": kids_table,
        "kids_table_teens": kids_table_teens,
        "time_limit": time_limit,
        "near_groups": near_groups or [],
        "near_target": near_target,
    }
    try:
        out, result, locked = _compute_auto(db, wedding_id, params)
    except engine.SeatingError as exc:
        raise Unprocessable(exc.message, code=exc.code) from exc
    if not dry_run:
        db.execute(
            delete(SeatAssignment).where(
                SeatAssignment.wedding_id == wedding_id, SeatAssignment.locked.is_(False)
            )
        )
        db.add_all(
            SeatAssignment(guest_id=gid, wedding_id=wedding_id, table_id=tid, locked=False)
            for gid, tid in result.assignment.items()
            if gid not in locked
        )
        _record(
            db,
            principal,
            wedding_id,
            "wedding",
            wedding_id,
            "seating_auto",
            {"seated": [None, len(result.assignment)], "status": [None, result.status]},
        )
        db.commit()
    return {"dry_run": dry_run, **out}


def _auto_rate_limit(db: Session, wedding_id: UUID) -> None:
    # Solver zużywa CPU przez kilka sekund: limit chroni serwer przed nadużyciem.
    ratelimit.hit(
        db,
        ratelimit.key_for("seating_auto", str(wedding_id)),
        AUTO_LIMIT_PER_HOUR,
        timedelta(hours=1),
    )
    db.commit()


def _compute_auto(
    db: Session, wedding_id: UUID, params: dict[str, Any]
) -> tuple[dict[str, Any], engine.Result, dict[UUID, UUID]]:
    """Czyste liczenie propozycji (bez uprawnień, limitów i zapisu) — w żądaniu albo w workerze."""
    s = _Snapshot(db, wedding_id)
    if not any(t.kind != "head" for t in s.tables):
        raise engine.SeatingError("seating.no_tables", "Najpierw dodaj stoły.")
    locked = {gid: a.table_id for gid, a in s.assignments.items() if a.locked}
    guests = {g.id: g for g in s.to_seat(params["basis"])}
    guests |= {gid: s.guests[gid] for gid in locked}
    near = frozenset(" ".join(g.lower().split()) for g in params["near_groups"] if g.strip())
    room = db.get(SeatingRoom, wedding_id)
    ranks = table_ranks(s.tables, room, params["near_target"]) if near else None
    result = engine.solve(
        [s.g(g) for g in guests.values()],
        s.t(),
        s.r(),
        locked,
        keep_households=params["keep_households"],
        kids_table=params["kids_table"],
        kids_table_teens=params["kids_table_teens"],
        time_limit=params["time_limit"],
        table_rank=ranks,
        near_groups=near,
    )
    out = {
        "status": result.status,
        "assignments": [
            {"guest_id": str(gid), "table_id": str(tid), "locked": gid in locked}
            for gid, tid in sorted(result.assignment.items(), key=lambda kv: str(kv[0]))
        ],
        "issues": [
            {
                **d,
                "guest_ids": [str(x) for x in d["guest_ids"]],
                "table_ids": [str(x) for x in d["table_ids"]],
            }
            for d in (issue_dict(i) for i in s.issues(result.assignment))
        ],
        "split_households": [str(h) for h in result.split_households],
        "near_applied": bool(near and ranks),
    }
    return out, result, locked


AUTO_JOB = "seating_auto"


def create_auto_run(
    db: Session, principal: Principal, wedding_id: UUID, params: dict[str, Any]
) -> SeatingAutoRun:
    """Propozycja usadzenia liczona w workerze; GUI odpytuje stan przebiegu."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    _auto_rate_limit(db, wedding_id)
    run = SeatingAutoRun(
        id=uuid7(), wedding_id=wedding_id, requested_by=principal.user.id, params=params
    )
    db.add(run)
    db.flush()
    enqueue(db, AUTO_JOB, {"run_id": str(run.id)}, wedding_id=wedding_id, max_attempts=1)
    db.commit()
    return run


def get_auto_run(
    db: Session, principal: Principal, wedding_id: UUID, run_id: UUID
) -> SeatingAutoRun:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    run = db.get(SeatingAutoRun, run_id)
    if run is None or run.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono przebiegu automatu.", code="seating.auto_run_not_found")
    return run


def run_auto_job(db: Session, payload: dict[str, Any]) -> None:
    """Zadanie workera. Błąd solvera kończy przebieg jako „failed” (bez ponawiania — CPU)."""
    run = db.get(SeatingAutoRun, UUID(payload["run_id"]))
    if run is None or run.status not in ("queued", "running"):
        return
    run.status = "running"
    db.commit()
    try:
        out, _result, _locked = _compute_auto(db, run.wedding_id, run.params)
    except engine.SeatingError as exc:
        run.status, run.error_code, run.error_message = "failed", exc.code, exc.message[:300]
    except Exception:  # nieprzewidziany błąd solvera: przebieg kończy się czytelnym błędem
        log.exception("seating_auto_failed", run_id=str(payload["run_id"]))
        db.rollback()  # błąd bazy zostawia sesję w stanie błędu — status zapisujemy od nowa
        run.status, run.error_code = "failed", "seating.auto_error"
        run.error_message = "Nie udało się ułożyć planu. Spróbujcie ponownie."
    else:
        run.status, run.result = "done", out
    run.finished_at = utcnow()
    db.commit()


def seat_numbers(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    *,
    table_id: UUID | None,
    keep_existing: bool,
    dry_run: bool,
) -> dict[str, Any]:
    """Numery miejsc przy stołach: rodzina obok siebie, para razem, dzieci przy rodzicu."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    s = _Snapshot(db, wedding_id)
    tables = [t for t in s.tables if table_id is None or t.id == table_id]
    if table_id is not None and not tables:
        raise NotFound("Nie znaleziono stołu.", code="seating.table_not_found")
    by_table: dict[UUID, list[SeatAssignment]] = defaultdict(list)
    for a in s.assignments.values():
        by_table[a.table_id].append(a)
    result: list[dict[str, Any]] = []
    changes: dict[UUID, int] = {}
    for t in tables:
        rows = by_table[t.id]
        if not rows:
            continue
        existing = (
            {a.guest_id: a.seat_number for a in rows if a.seat_number is not None}
            if keep_existing
            else {}
        )
        try:
            numbers = engine.number_seats(
                [s.g(s.guests[a.guest_id]) for a in rows], t.capacity, existing
            )
        except engine.SeatingError as exc:
            raise Unprocessable(f"{t.name}: {exc.message}", code=exc.code) from exc
        changes |= numbers
        result += [
            {"guest_id": gid, "table_id": t.id, "seat_number": n}
            for gid, n in sorted(numbers.items(), key=lambda kv: kv[1])
        ]
    if not dry_run and changes:
        assignments = [s.assignments[gid] for gid in changes]
        # Najpierw zwalniamy numery (unikalny indeks stół+miejsce), potem wpisujemy nowe.
        for a in assignments:
            a.seat_number = None
        db.flush()
        for a in assignments:
            a.seat_number = changes[a.guest_id]
        _record(
            db,
            principal,
            wedding_id,
            "wedding",
            wedding_id,
            "seat_numbers",
            {"seats": [None, len(changes)]},
        )
        db.commit()
    return {"dry_run": dry_run, "seats": result}


AUTO_RUN_RETENTION = timedelta(days=7)


def purge_auto_runs(db: Session) -> int:
    """Utrzymanie: przebiegi automatu to tylko podglądy — usuwamy po tygodniu."""
    result = db.execute(
        delete(SeatingAutoRun).where(SeatingAutoRun.created_at < utcnow() - AUTO_RUN_RETENTION)
    )
    db.commit()
    return int(getattr(result, "rowcount", 0) or 0)
