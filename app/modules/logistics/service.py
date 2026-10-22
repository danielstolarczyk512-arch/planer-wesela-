"""Transport i noclegi gości: kursy z miejscami, pokoje, kto jeszcze bez przydziału.

Przewoźnik i hotel dostają dziś listy z Excela, które dezaktualizują się po pierwszej zmianie RSVP.
Tu przydział jest przy gościach, więc liczby i lista pokoi są zawsze aktualne.
"""

from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core import clock
from app.core.errors import Conflict, NotFound, Unprocessable
from app.core.spreadsheet import csv_safe, to_csv
from app.modules.audit import service as audit
from app.modules.guests.models import Guest, GuestEventAttendance
from app.modules.identity.service import Principal
from app.modules.logistics.models import LodgingRoom, RoomGuest, TransportRun, TransportSeat
from app.modules.workspace.permissions import Action, authorize


def _conflict() -> Conflict:
    return Conflict(
        "Dane zmieniły się w międzyczasie. Pobierz aktualną wersję.",
        code="conflict.version_mismatch",
    )


def _record(
    db: Session, principal: Principal, wedding_id: UUID, entity: str, entity_id: UUID, action: str
) -> None:
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type=entity,
        entity_id=entity_id,
        wedding_id=wedding_id,
        action=action,
    )


def _commit(db: Session) -> None:
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise _conflict() from exc


def _guest_name(g: Guest) -> str:
    return f"{g.first_name} {g.last_name}".strip() if g.last_name else g.first_name


def _declined(db: Session, wedding_id: UUID) -> set[UUID]:
    """Goście, którzy odmówili na wszystkich wydarzeniach, na które odpowiadali."""
    rows = db.execute(
        select(GuestEventAttendance.guest_id, GuestEventAttendance.status)
        .join(Guest, Guest.id == GuestEventAttendance.guest_id)
        .where(Guest.wedding_id == wedding_id)
    )
    statuses: dict[UUID, set[str]] = defaultdict(set)
    for guest_id, status in rows:
        statuses[guest_id].add(status)
    return {g for g, s in statuses.items() if s == {"declined"}}


def _check_guests(db: Session, wedding_id: UUID, ids: list[UUID]) -> None:
    found = db.scalar(
        select(func.count())
        .select_from(Guest)
        .where(Guest.wedding_id == wedding_id, Guest.id.in_(ids))
    )
    if found != len(set(ids)):
        raise NotFound("Nie znaleziono części gości.", code="guest.not_found")


# --- kursy -----------------------------------------------------------------------------------


def get_run(db: Session, wedding_id: UUID, run_id: UUID) -> TransportRun:
    r = db.get(TransportRun, run_id)
    if r is None or r.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono kursu.", code="transport_run.not_found")
    return r


def _check_vendor(db: Session, wedding_id: UUID, vendor_id: UUID | None) -> None:
    if vendor_id is not None:
        from app.modules.vendors import service as vendors

        vendors.get_in_wedding(db, wedding_id, vendor_id)


def create_run(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]
) -> TransportRun:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    _check_vendor(db, wedding_id, data.get("vendor_id"))
    r = TransportRun(wedding_id=wedding_id, **data)
    db.add(r)
    db.flush()
    _record(db, principal, wedding_id, "transport_run", r.id, "create")
    db.commit()
    return r


def update_run(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    run_id: UUID,
    data: dict[str, Any],
    version: int,
) -> TransportRun:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    r = get_run(db, wedding_id, run_id)
    if r.version != version:
        raise _conflict()
    if "vendor_id" in data:
        _check_vendor(db, wedding_id, data["vendor_id"])
    for k, v in data.items():
        if v is not None or k in ("vendor_id", "departs_at", "from_place", "to_place", "notes"):
            # show_to_guests: NOT_NULL w schemacie, więc None oznacza „bez zmiany”.
            setattr(r, k, v)
    _record(db, principal, wedding_id, "transport_run", r.id, "update")
    _commit(db)
    return r


def delete_run(db: Session, principal: Principal, wedding_id: UUID, run_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    db.delete(get_run(db, wedding_id, run_id))
    _record(db, principal, wedding_id, "transport_run", run_id, "delete")
    db.commit()


def set_passengers(
    db: Session, principal: Principal, wedding_id: UUID, run_id: UUID, guest_ids: list[UUID]
) -> None:
    """Lista pasażerów kursu (zastępuje poprzednią). Przepełnienie jest dozwolone, ale widoczne."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    get_run(db, wedding_id, run_id)
    _check_guests(db, wedding_id, guest_ids)
    db.execute(delete(TransportSeat).where(TransportSeat.run_id == run_id))
    db.add_all(TransportSeat(run_id=run_id, guest_id=g) for g in dict.fromkeys(guest_ids))
    _record(db, principal, wedding_id, "transport_run", run_id, "passengers")
    db.commit()


# --- pokoje ----------------------------------------------------------------------------------


def get_room(db: Session, wedding_id: UUID, room_id: UUID) -> LodgingRoom:
    r = db.get(LodgingRoom, room_id)
    if r is None or r.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono pokoju.", code="lodging_room.not_found")
    return r


def _check_nights(data: dict[str, Any], room: LodgingRoom | None = None) -> None:
    check_in = data.get("check_in", room.check_in if room else None)
    check_out = data.get("check_out", room.check_out if room else None)
    if check_in and check_out and check_out <= check_in:
        raise Unprocessable("Wymeldowanie musi być po zameldowaniu.", code="lodging_room.nights")


def create_room(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]
) -> LodgingRoom:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    _check_nights(data)
    r = LodgingRoom(wedding_id=wedding_id, **data)
    db.add(r)
    db.flush()
    _record(db, principal, wedding_id, "lodging_room", r.id, "create")
    db.commit()
    return r


def update_room(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    room_id: UUID,
    data: dict[str, Any],
    version: int,
) -> LodgingRoom:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    r = get_room(db, wedding_id, room_id)
    if r.version != version:
        raise _conflict()
    _check_nights(data, r)
    for k, v in data.items():
        if v is not None or k in ("check_in", "check_out", "paid_by", "notes"):
            setattr(r, k, v)
    _record(db, principal, wedding_id, "lodging_room", r.id, "update")
    _commit(db)
    return r


def delete_room(db: Session, principal: Principal, wedding_id: UUID, room_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    db.delete(get_room(db, wedding_id, room_id))
    _record(db, principal, wedding_id, "lodging_room", room_id, "delete")
    db.commit()


def set_occupants(
    db: Session, principal: Principal, wedding_id: UUID, room_id: UUID, guest_ids: list[UUID]
) -> None:
    """Goście w pokoju (zastępuje listę). Gość z innego pokoju zostaje przeniesiony."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    room = get_room(db, wedding_id, room_id)
    ids = list(dict.fromkeys(guest_ids))
    if len(ids) > room.beds:
        raise Unprocessable(
            f"W pokoju jest {room.beds} miejsc, a wybrano {len(ids)} osób.",
            code="lodging_room.too_many",
        )
    _check_guests(db, wedding_id, ids)
    db.execute(
        delete(RoomGuest).where((RoomGuest.room_id == room_id) | RoomGuest.guest_id.in_(ids))
    )
    db.add_all(RoomGuest(room_id=room_id, guest_id=g) for g in ids)
    _record(db, principal, wedding_id, "lodging_room", room_id, "occupants")
    db.commit()


# --- przegląd i lista pokoi dla hotelu ---------------------------------------------------------


def overview(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    from app.modules.schedule.models import ScheduleItem  # program dnia: tylko odczyt

    guests = {g.id: g for g in db.scalars(select(Guest).where(Guest.wedding_id == wedding_id))}
    declined = _declined(db, wedding_id)
    runs = list(
        db.scalars(
            select(TransportRun)
            .where(TransportRun.wedding_id == wedding_id)
            .order_by(TransportRun.departs_at.asc().nulls_last(), TransportRun.created_at)
        )
    )
    seats: dict[UUID, list[UUID]] = defaultdict(list)
    for s in db.scalars(
        select(TransportSeat).where(TransportSeat.run_id.in_([r.id for r in runs]))
    ):
        seats[s.run_id].append(s.guest_id)
    guest_items = list(
        db.scalars(
            select(ScheduleItem)
            .where(ScheduleItem.wedding_id == wedding_id, ScheduleItem.for_guests.is_(True))
            .order_by(ScheduleItem.starts_at)
        )
    )
    rooms = list(
        db.scalars(
            select(LodgingRoom)
            .where(LodgingRoom.wedding_id == wedding_id)
            .order_by(LodgingRoom.place, LodgingRoom.name)
        )
    )
    occupants: dict[UUID, list[UUID]] = defaultdict(list)
    for o in db.scalars(select(RoomGuest).where(RoomGuest.room_id.in_([r.id for r in rooms]))):
        occupants[o.room_id].append(o.guest_id)

    def people(ids: list[UUID]) -> list[dict[str, Any]]:
        return sorted(
            (
                {"guest_id": g, "name": _guest_name(guests[g]), "declined": g in declined}
                for g in ids
            ),
            key=lambda p: p["name"],
        )

    on_run = {g for ids in seats.values() for g in ids}
    in_room = {g for ids in occupants.values() for g in ids}
    out_runs = []
    for r in runs:
        taken = len(seats[r.id])
        # Kurs powrotny przed punktami programu dla gości: kto nim jedzie, ten je ominie.
        missed = (
            [
                {"title": i.title, "starts_at": clock.local(i.starts_at)}
                for i in guest_items
                if r.departs_at and i.starts_at > r.departs_at
            ]
            if r.kind == "back"
            else []
        )
        out_runs.append(
            {
                "id": r.id,
                "name": r.name,
                "kind": r.kind,
                "vendor_id": r.vendor_id,
                "departs_at": clock.local(r.departs_at),
                "from_place": r.from_place,
                "to_place": r.to_place,
                "capacity": r.capacity,
                "notes": r.notes,
                "show_to_guests": r.show_to_guests,
                "version": r.version,
                "passengers": people(seats[r.id]),
                "taken": taken,
                "over": max(taken - r.capacity, 0),
                "missed_items": missed,
            }
        )
    return {
        "runs": out_runs,
        "rooms": [
            {
                "id": r.id,
                "place": r.place,
                "name": r.name,
                "beds": r.beds,
                "check_in": r.check_in,
                "check_out": r.check_out,
                "nights": (r.check_out - r.check_in).days if r.check_in and r.check_out else None,
                "paid_by": r.paid_by,
                "notes": r.notes,
                "version": r.version,
                "occupants": people(occupants[r.id]),
                "free": r.beds - len(occupants[r.id]),
            }
            for r in rooms
        ],
        "transport_missing": people(
            [
                g.id
                for g in guests.values()
                if g.needs_transport and g.id not in on_run and g.id not in declined
            ]
        ),
        "lodging_missing": people(
            [
                g.id
                for g in guests.values()
                if g.needs_accommodation and g.id not in in_room and g.id not in declined
            ]
        ),
    }


def rooming_csv(db: Session, principal: Principal, wedding_id: UUID) -> str:
    """Lista pokoi dla hotelu: obiekt, pokój, noce, osoby. Bez diet i kwot."""
    data = overview(db, principal, wedding_id)
    header = [
        "Obiekt",
        "Pokój",
        "Miejsca",
        "Zameldowanie",
        "Wymeldowanie",
        "Noce",
        "Osoby",
        "Płaci",
    ]
    rows: list[list[str]] = []
    for r in data["rooms"]:
        rows.append(
            [
                csv_safe(r["place"]),
                csv_safe(r["name"]),
                str(r["beds"]),
                r["check_in"].isoformat() if r["check_in"] else "",
                r["check_out"].isoformat() if r["check_out"] else "",
                str(r["nights"] or ""),
                csv_safe(", ".join(p["name"] for p in r["occupants"])),
                csv_safe(r["paid_by"] or ""),
            ]
        )
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="lodging_room",
        entity_id=wedding_id,
        wedding_id=wedding_id,
        action="export_rooming",
    )
    db.commit()
    return to_csv(header, rows)


def vendor_runs(db: Session, wedding_id: UUID, vendor_id: UUID) -> list[dict[str, Any]]:
    """Kursy przewoźnika na jego linku z programem dnia: godziny i liczba osób, bez nazwisk."""
    runs = list(
        db.scalars(
            select(TransportRun)
            .where(TransportRun.wedding_id == wedding_id, TransportRun.vendor_id == vendor_id)
            .order_by(TransportRun.departs_at.asc().nulls_last())
        )
    )
    counts = dict(
        db.execute(
            select(TransportSeat.run_id, func.count())
            .where(TransportSeat.run_id.in_([r.id for r in runs]))
            .group_by(TransportSeat.run_id)
        ).all()
    )
    return [
        {
            "name": r.name,
            "departs_at": clock.local(r.departs_at),
            "from_place": r.from_place,
            "to_place": r.to_place,
            "passengers": counts.get(r.id, 0),
            "capacity": r.capacity,
        }
        for r in runs
    ]


# --- kursy w formularzu RSVP --------------------------------------------------------------


def _shown_runs(db: Session, wedding_id: UUID) -> list[TransportRun]:
    return list(
        db.scalars(
            select(TransportRun)
            .where(TransportRun.wedding_id == wedding_id, TransportRun.show_to_guests.is_(True))
            .order_by(TransportRun.departs_at.asc().nulls_last(), TransportRun.created_at)
        )
    )


def _taken(db: Session, run_ids: list[UUID]) -> dict[UUID, int]:
    return dict(
        db.execute(
            select(TransportSeat.run_id, func.count())
            .where(TransportSeat.run_id.in_(run_ids))
            .group_by(TransportSeat.run_id)
        ).all()
    )


def guest_runs(
    db: Session, wedding_id: UUID, guest_ids: list[UUID]
) -> tuple[list[dict[str, Any]], dict[UUID, list[UUID]]]:
    """Kursy pokazane gościom (z wolnymi miejscami) i kursy wybrane przez osoby z zaproszenia."""
    runs = _shown_runs(db, wedding_id)
    ids = [r.id for r in runs]
    taken = _taken(db, ids)
    chosen: dict[UUID, list[UUID]] = defaultdict(list)
    if ids and guest_ids:
        for s in db.scalars(
            select(TransportSeat).where(
                TransportSeat.run_id.in_(ids), TransportSeat.guest_id.in_(guest_ids)
            )
        ):
            chosen[s.guest_id].append(s.run_id)
    return (
        [
            {
                "id": r.id,
                "name": r.name,
                "kind": r.kind,
                "departs_at": clock.local(r.departs_at),
                "from_place": r.from_place,
                "to_place": r.to_place,
                "free": max(r.capacity - taken.get(r.id, 0), 0),
            }
            for r in runs
        ],
        chosen,
    )


def set_guest_runs(db: Session, wedding_id: UUID, guest_id: UUID, run_ids: list[UUID]) -> None:
    """Wybór gościa w RSVP: zastępuje jego miejsca tylko na kursach pokazanych gościom.

    Kursy ukryte (przydzielone przez parę) zostają bez zmian. Pełny kurs: 409.
    """
    runs = {r.id: r for r in _shown_runs(db, wedding_id)}
    wanted = list(dict.fromkeys(run_ids))
    if any(r not in runs for r in wanted):
        raise Unprocessable("Wybrany kurs jest niedostępny.", code="rsvp.invalid_target")
    current = set(
        db.scalars(
            select(TransportSeat.run_id).where(
                TransportSeat.guest_id == guest_id, TransportSeat.run_id.in_(list(runs))
            )
        )
    )
    # Blokada wierszy kursów: dwie rodziny zapisujące się naraz na ostatnie miejsce czekają
    # na siebie, więc druga zobaczy zajęte miejsce (409) zamiast przepełnić kurs.
    if wanted:
        db.execute(
            select(TransportRun.id).where(TransportRun.id.in_(sorted(wanted))).with_for_update()
        ).all()
    taken = _taken(db, wanted)
    for r in wanted:
        if r not in current and taken.get(r, 0) >= runs[r].capacity:
            raise Conflict(
                f"Na kursie „{runs[r].name}” nie ma już wolnych miejsc. "
                "Wybierz inny albo napisz do pary.",
                code="rsvp.transport_full",
            )
    db.execute(
        delete(TransportSeat).where(
            TransportSeat.guest_id == guest_id,
            TransportSeat.run_id.in_([r for r in current if r not in wanted]),
        )
    )
    db.add_all(TransportSeat(run_id=r, guest_id=guest_id) for r in wanted if r not in current)


def day_runs(db: Session, principal: Principal, wedding_id: UUID) -> list[dict[str, Any]]:
    """Kursy na ekranie Dzień (też koordynator): godziny, trasy, liczby osób — bez nazwisk."""
    authorize(db, principal.user.id, wedding_id, Action.DAY_READ)
    runs = list(
        db.scalars(
            select(TransportRun)
            .where(TransportRun.wedding_id == wedding_id)
            .order_by(TransportRun.departs_at.asc().nulls_last(), TransportRun.created_at)
        )
    )
    taken = _taken(db, [r.id for r in runs])
    return [
        {
            "id": r.id,
            "name": r.name,
            "kind": r.kind,
            "departs_at": clock.local(r.departs_at),
            "from_place": r.from_place,
            "to_place": r.to_place,
            "passengers": taken.get(r.id, 0),
            "capacity": r.capacity,
        }
        for r in runs
    ]
