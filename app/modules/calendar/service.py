"""Kalendarz wesela: zadania, płatności i wydarzenia w jednym widoku oraz prywatny plik ICS.

Plik ICS trafia do zewnętrznego kalendarza wybranego przez osobę (np. Google, Apple), więc
zawiera minimum danych: tytuły zadań i wydarzeń, rodzaj płatności i nazwę wydatku —
bez kwot, danych gości ani notatek.
"""

from collections import Counter
from datetime import date, timedelta
from typing import Any
from uuid import UUID, uuid5

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import clock, ratelimit
from app.core.db import utcnow
from app.core.errors import NotFound
from app.core.security import hash_token, new_token
from app.modules.audit import service as audit
from app.modules.budget import service as budget
from app.modules.budget.models import Payment
from app.modules.calendar.models import CalendarFeedToken
from app.modules.identity.service import Principal
from app.modules.planner import service as planner
from app.modules.planner.models import Task
from app.modules.workspace.models import Event, Wedding, WeddingMember
from app.modules.workspace.permissions import ROLE_ACTIONS, Action, authorize

PAYMENT_LABEL = {
    "deposit_zadatek": "Zadatek",
    "advance_zaliczka": "Zaliczka",
    "installment": "Rata",
    "final": "Dopłata",
    "other": "Płatność",
}
MAX_RANGE_DAYS = 800
CRLF = chr(13) + chr(10)  # koniec linii wymagany przez RFC 5545


def _entries(db: Session, wedding: Wedding, start: date, end: date) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    tasks = db.scalars(
        select(Task).where(
            Task.wedding_id == wedding.id,
            Task.parent_task_id.is_(None),
            Task.status != "skipped",
            Task.due_date.between(start, end),
        )
    )
    for t in tasks:
        out.append(
            {
                "kind": "task",
                "date": t.due_date,
                "time": None,
                "title": t.title,
                "ref_id": t.id,
                "done": t.status == "done",
                "overdue": planner.is_overdue(t),
            }
        )
    payments = list(
        db.scalars(
            select(Payment).where(
                Payment.wedding_id == wedding.id,
                Payment.status.in_(("scheduled", "paid")),
                Payment.due_date.between(start, end),
            )
        )
    )
    names = budget.item_names(db, {p.budget_item_id for p in payments})
    for p in payments:
        label = PAYMENT_LABEL.get(p.kind, "Płatność")
        out.append(
            {
                "kind": "payment",
                "date": p.due_date,
                "time": None,
                "title": f"{label}: {names.get(p.budget_item_id, '')}",
                "ref_id": p.id,
                "done": p.status == "paid",
                "overdue": budget.is_payment_overdue(p),
            }
        )
    for e in db.scalars(
        select(Event).where(Event.wedding_id == wedding.id, Event.starts_at.is_not(None))
    ):
        starts = clock.local(e.starts_at)
        if starts is not None and start <= starts.date() <= end:
            out.append(
                {
                    "kind": "event",
                    "date": starts.date(),
                    "time": starts.strftime("%H:%M"),
                    "title": e.name,
                    "ref_id": e.id,
                    "done": False,
                    "overdue": False,
                }
            )
    if wedding.wedding_date and start <= wedding.wedding_date <= end:
        out.append(
            {
                "kind": "wedding",
                "date": wedding.wedding_date,
                "time": None,
                "title": "Dzień ślubu",
                "ref_id": wedding.id,
                "done": False,
                "overdue": False,
            }
        )
    out += _reminders(db, wedding, start, end)
    order = {"wedding": 0, "event": 1, "payment": 2, "reminder": 3, "task": 4}
    out.sort(key=lambda x: (x["date"], x["time"] or "", order[x["kind"]], x["title"]))
    return out


def _reminder(
    day: date, title: str, ref_id: UUID, link: str, *, done: bool = False
) -> dict[str, Any]:
    return {
        "kind": "reminder",
        "date": day,
        "time": None,
        "title": title,
        "ref_id": ref_id,
        "done": done,
        "overdue": not done and day < clock.today(),
        "link": link,
    }


def _reminders(db: Session, wedding: Wedding, start: date, end: date) -> list[dict[str, Any]]:
    """Terminy z nowych modułów: dokumenty, aneksy cen, oddanie zdjęć, objazdy z zaproszeniami.

    W pliku ICS tylko tytuły i liczby — bez nazwisk gości (objazd: liczba zaproszeń).
    """
    # Importy lokalne: kalendarz tylko czyta te moduły.
    from app.modules.aftercare.models import Deliverable
    from app.modules.budget.models import BudgetItem
    from app.modules.guests.models import Household
    from app.modules.planner import documents

    out: list[dict[str, Any]] = []

    def within(day: date | None) -> bool:
        return day is not None and start <= day <= end

    for d in documents.summary_for(db, wedding.id)["items"]:
        if d["status"] in ("ok", "done", "expires", "no_date"):
            continue
        if within(d["earliest"]):
            ref = uuid5(wedding.id, f"doc-earliest-{d['code']}")
            out.append(_reminder(d["earliest"], f"Od dziś: {d['title']}", ref, "formalnosci"))
        if within(d["latest"]):
            ref = uuid5(wedding.id, f"doc-latest-{d['code']}")
            out.append(_reminder(d["latest"], f"Najpóźniej: {d['title']}", ref, "formalnosci"))
    for item in db.scalars(
        select(BudgetItem).where(
            BudgetItem.wedding_id == wedding.id,
            BudgetItem.indexation != "none",
            BudgetItem.price_review_on.between(start, end),
        )
    ):
        if item.price_review_on:
            out.append(
                _reminder(
                    item.price_review_on,
                    f"Aneks lub potwierdzenie ceny: {item.name}",
                    item.id,
                    "budzet",
                )
            )
    for d in db.scalars(
        select(Deliverable).where(
            Deliverable.wedding_id == wedding.id, Deliverable.due_on.between(start, end)
        )
    ):
        if d.due_on:
            out.append(
                _reminder(
                    d.due_on,
                    f"Termin oddania: {d.title}",
                    d.id,
                    "po-weselu",
                    done=d.received_on is not None,
                )
            )
    rounds = Counter(
        h.delivery_planned_on
        for h in db.scalars(
            select(Household).where(
                Household.wedding_id == wedding.id,
                Household.delivery_planned_on.between(start, end),
                Household.invitation_status != "delivered",
            )
        )
    )
    for day, count in rounds.items():
        if day:
            ref = uuid5(wedding.id, f"delivery-{day.isoformat()}")
            out.append(_reminder(day, f"Objazd z zaproszeniami ({count})", ref, "zaproszenia"))
    return out


def calendar(
    db: Session, principal: Principal, wedding_id: UUID, start: date, end: date
) -> list[dict[str, Any]]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    end = min(end, start + timedelta(days=MAX_RANGE_DAYS))
    return _entries(db, db.get_one(Wedding, wedding_id), start, end)


# --- prywatny adres kalendarza (ICS) ----------------------------------------------------------


def _active(db: Session, wedding_id: UUID, user_id: UUID) -> CalendarFeedToken | None:
    return db.scalars(
        select(CalendarFeedToken).where(
            CalendarFeedToken.wedding_id == wedding_id,
            CalendarFeedToken.user_id == user_id,
            CalendarFeedToken.revoked_at.is_(None),
        )
    ).first()


def feed_status(db: Session, principal: Principal, wedding_id: UUID) -> CalendarFeedToken | None:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return _active(db, wedding_id, principal.user.id)


def _revoke(db: Session, wedding_id: UUID, user_id: UUID) -> None:
    db.execute(
        update(CalendarFeedToken)
        .where(
            CalendarFeedToken.wedding_id == wedding_id,
            CalendarFeedToken.user_id == user_id,
            CalendarFeedToken.revoked_at.is_(None),
        )
        .values(revoked_at=utcnow())
    )


def create_feed(db: Session, principal: Principal, wedding_id: UUID) -> str:
    """Nowy prywatny adres (poprzedni przestaje działać). Token widoczny tylko raz."""
    authorize(db, principal.user.id, wedding_id, Action.READ)
    _revoke(db, wedding_id, principal.user.id)
    token, token_hash = new_token()
    db.add(
        CalendarFeedToken(wedding_id=wedding_id, user_id=principal.user.id, token_hash=token_hash)
    )
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="calendar_feed",
        entity_id=wedding_id,
        wedding_id=wedding_id,
        action="create",
    )
    db.commit()
    return token


def revoke_feed(db: Session, principal: Principal, wedding_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    _revoke(db, wedding_id, principal.user.id)
    db.commit()


def feed_ics(db: Session, token: str, ip: str) -> str:
    ratelimit.hit(db, ratelimit.key_for("ics:ip", ip), 120, timedelta(minutes=10))
    feed = db.scalars(
        select(CalendarFeedToken).where(CalendarFeedToken.token_hash == hash_token(token))
    ).first()
    member = db.get(WeddingMember, (feed.wedding_id, feed.user_id)) if feed else None
    if (
        feed is None
        or feed.revoked_at is not None
        or member is None
        or Action.READ not in ROLE_ACTIONS[member.role]
    ):
        raise NotFound("Nieprawidłowy lub wyłączony adres kalendarza.", code="calendar.not_found")
    feed.last_used_at = utcnow()
    wedding = db.get_one(Wedding, feed.wedding_id)
    today = clock.today()
    entries = _entries(
        db, wedding, today - timedelta(days=60), today + timedelta(days=MAX_RANGE_DAYS)
    )
    db.commit()
    return to_ics(wedding.name, entries)


# --- format iCalendar (RFC 5545), bez zewnętrznych bibliotek ---------------------------------


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """Linie dłuższe niż 75 bajtów zawijane wg RFC 5545 (bez dzielenia znaków UTF-8)."""
    out: list[str] = []
    current = ""
    for ch in line:
        if len((current + ch).encode()) > (75 if not out else 74):
            out.append(current)
            current = ch
        else:
            current += ch
    out.append(current)
    return (CRLF + " ").join(out)


CATEGORY = {
    "task": "Zadanie",
    "payment": "Płatność",
    "event": "Wesele",
    "wedding": "Wesele",
    "reminder": "Przypomnienie",
}


def to_ics(calendar_name: str, entries: list[dict[str, Any]]) -> str:
    """Wpisy całodniowe (godzina wydarzenia w tytule): bez stref czasowych w pliku."""
    stamp = utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Nasz dzien//Planer wesela//PL",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{_escape(calendar_name)}",
    ]
    for e in entries:
        day: date = e["date"]
        title = f"{e['time']} {e['title']}" if e["time"] else e["title"]
        if e["done"]:
            title = f"✓ {title}"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{e['kind']}-{e['ref_id']}@nasz-dzien",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}",
            f"SUMMARY:{_escape(title)}",
            f"CATEGORIES:{CATEGORY[e['kind']]}",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return CRLF.join(_fold(line) for line in lines) + CRLF
