"""Przypomnienia: jedno zbiorcze podsumowanie e-mail zamiast wielu pojedynczych wiadomości."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core import clock, mail_templates
from app.core.config import get_settings
from app.core.email import queue_mail
from app.modules.budget.models import BudgetItem, Payment
from app.modules.budget.service import PAYMENT_KIND_LABELS
from app.modules.guests.models import Guest, GuestEventAttendance, Household
from app.modules.identity.models import User
from app.modules.identity.service import Principal
from app.modules.notifications.models import DigestLog, NotificationPreference
from app.modules.planner.models import Task
from app.modules.workspace.models import Wedding, WeddingMember

HORIZON_DAYS = 7
SEND_FROM_HOUR = 8  # nie wysyłamy w nocy (czas polski)


def get_preference(db: Session, principal: Principal) -> str:
    pref = db.get(NotificationPreference, principal.user.id)
    return str(pref.digest) if pref else "daily"


def set_preference(db: Session, principal: Principal, digest: str) -> str:
    pref = db.get(NotificationPreference, principal.user.id)
    if pref is None:
        db.add(NotificationPreference(user_id=principal.user.id, digest=digest))
    else:
        pref.digest = digest
    db.commit()
    return digest


def date_pl(d: date) -> str:
    """Data w zapisie polskim: 10.01.2027."""
    return d.strftime("%d.%m.%Y")


def money_pl(amount: Decimal) -> str:
    """Kwota w zapisie polskim: 12 500,00 zł."""
    return f"{amount:,.2f}".replace(",", " ").replace(".", ",") + " zł"


def digest_items(db: Session, wedding_id: UUID) -> dict[str, list[str]]:
    """Treść podsumowania: zaległe i nadchodzące zadania, płatności i terminy RSVP."""
    today = clock.today()
    horizon = today + timedelta(days=HORIZON_DAYS)
    tasks = db.scalars(
        select(Task)
        .where(
            Task.wedding_id == wedding_id,
            Task.status.in_(("todo", "in_progress")),
            Task.due_date.is_not(None),
            Task.due_date <= horizon,
        )
        .order_by(Task.due_date)
    )
    payments = db.execute(
        select(Payment, BudgetItem.name)
        .join(BudgetItem, BudgetItem.id == Payment.budget_item_id)
        .where(
            Payment.wedding_id == wedding_id,
            Payment.status == "scheduled",
            Payment.due_date.is_not(None),
            Payment.due_date <= horizon,
        )
        .order_by(Payment.due_date)
    )
    answered = select(GuestEventAttendance.guest_id).where(GuestEventAttendance.status != "pending")
    pending = (
        select(func.count())
        .select_from(Guest)
        .where(Guest.household_id == Household.id, ~Guest.id.in_(answered))
        .correlate(Household)
        .scalar_subquery()
    )
    rsvp = db.execute(
        select(Household.name, Household.rsvp_deadline, pending).where(
            Household.wedding_id == wedding_id,
            Household.rsvp_deadline.is_not(None),
            Household.rsvp_deadline >= today,
            Household.rsvp_deadline <= horizon,
        )
    )

    def when(d: date | None) -> str:
        if d is None:  # zapytania filtrują puste terminy; obrona typów
            return "bez terminu"
        return f"PO TERMINIE {date_pl(d)}" if d < today else date_pl(d)

    # Dokumenty do ślubu: tylko to, co wymaga działania (po terminie albo straci ważność).
    from app.modules.planner import documents  # podsumowanie czyta stan licznika dokumentów

    docs = documents.attention(db, wedding_id)
    from app.modules.budget import indexation  # terminy aneksów (waloryzacja cen)

    prices = indexation.reviews_due(db, wedding_id, horizon)
    from app.modules.aftercare.service import overdue_lines  # zdjęcia, film po terminie
    from app.modules.guests.forecast import digest_lines  # termin dla sali, minimum, RSVP

    return {
        "attendance": digest_lines(db, wedding_id),
        "deliverables": overdue_lines(db, wedding_id),
        "documents": docs,
        "prices": [
            f"{when(i.price_review_on)}: {i.name} — termin aneksu lub potwierdzenia ceny"
            for i in prices
        ],
        "tasks": [f"{when(t.due_date)}: {t.title}" for t in tasks],
        "payments": [
            f"{when(p.due_date)}: {name} ({PAYMENT_KIND_LABELS.get(p.kind, p.kind)}) "
            f"{money_pl(p.amount)}"
            for p, name in payments
        ],
        "rsvp": [
            f"{date_pl(deadline)}: {name} (bez odpowiedzi: {n})" for name, deadline, n in rsvp if n
        ],
    }


def _render(wedding: Wedding, items: dict[str, list[str]], subject: str) -> mail_templates.Email:
    return mail_templates.build(
        subject,
        heading=f"Podsumowanie przygotowań: {wedding.name}",
        paragraphs=["Co przed Wami w najbliższych dniach:"],
        sections=[
            mail_templates.Section("Zadania", items["tasks"]),
            mail_templates.Section("Płatności", items["payments"]),
            mail_templates.Section("Potwierdzenia obecności", items["rsvp"]),
            mail_templates.Section("Frekwencja i sala", items["attendance"]),
            mail_templates.Section("Dokumenty do ślubu", items["documents"]),
            mail_templates.Section("Ceny w umowach", items["prices"]),
            mail_templates.Section("Od usługodawców po weselu", items["deliverables"]),
        ],
        action=("Otwórz plan wesela", f"{get_settings().public_app_url}/w/{wedding.id}"),
    )


def sponsor_items(db: Session, funder_id: UUID) -> list[str]:
    """Podsumowanie sponsora: tylko jego płatności do zrobienia w najbliższych dniach."""
    today = clock.today()
    horizon = today + timedelta(days=HORIZON_DAYS)
    rows = db.execute(
        select(Payment, BudgetItem.name)
        .join(BudgetItem, BudgetItem.id == Payment.budget_item_id)
        .where(
            Payment.funder_id == funder_id,
            Payment.status == "scheduled",
            Payment.due_date.is_not(None),
            Payment.due_date <= horizon,
        )
        .order_by(Payment.due_date)
    )
    out = []
    for p, name in rows:
        if p.due_date is None:  # zapytanie filtruje puste terminy; obrona typów
            continue
        when = f"PO TERMINIE {date_pl(p.due_date)}" if p.due_date < today else date_pl(p.due_date)
        kind = PAYMENT_KIND_LABELS.get(p.kind, p.kind)
        out.append(f"{when}: {name} ({kind}) {money_pl(p.amount)}")
    return out


def _render_sponsor(wedding: Wedding, items: list[str], subject: str) -> mail_templates.Email:
    return mail_templates.build(
        subject,
        heading=f"Wasz wkład w wesele: {wedding.name}",
        paragraphs=["Płatności przypisane Wam przez parę młodą w najbliższych dniach:"],
        sections=[mail_templates.Section("Płatności przed Wami", items)],
        action=("Zobacz swój wkład", f"{get_settings().public_app_url}/w/{wedding.id}/wklad"),
    )


def send_digests(db: Session, now: datetime | None = None) -> int:
    """Zadanie okresowe workera. Idempotentne dzięki digest_log (PK user+wedding+dzień)."""
    local_now = (now or datetime.now(clock.WARSAW)).astimezone(clock.WARSAW)
    if local_now.hour < SEND_FROM_HOUR:
        return 0
    today = local_now.date()
    rows = db.execute(
        select(
            User,
            Wedding,
            func.coalesce(NotificationPreference.digest, "daily"),
            WeddingMember.role,
            WeddingMember.funder_id,
        )
        .join(WeddingMember, WeddingMember.user_id == User.id)
        .join(Wedding, Wedding.id == WeddingMember.wedding_id)
        .outerjoin(NotificationPreference, NotificationPreference.user_id == User.id)
        .where(
            User.status == "active",
            User.email_verified_at.is_not(None),
            Wedding.status == "planning",
            # Koordynator dnia: bez podsumowania; sponsor: własne (tylko jego płatności).
            WeddingMember.role != "coordinator",
        )
    ).all()
    sent = 0
    for user, wedding, mode, role, funder_id in rows:
        if mode == "off":
            continue
        since = today - timedelta(days=6 if mode == "weekly" else 0)
        already = db.scalar(
            select(func.count())
            .select_from(DigestLog)
            .where(
                DigestLog.user_id == user.id,
                DigestLog.wedding_id == wedding.id,
                DigestLog.sent_on >= since,
            )
        )
        if already:
            continue
        sponsor = role == "sponsor"
        if sponsor and funder_id is None:
            continue
        lines = sponsor_items(db, funder_id) if sponsor and funder_id else []
        items = {} if sponsor else digest_items(db, wedding.id)
        if not (lines if sponsor else any(items.values())):
            continue
        claimed = db.execute(
            insert(DigestLog)
            .values(user_id=user.id, wedding_id=wedding.id, sent_on=today)
            .on_conflict_do_nothing()
        )
        if not getattr(claimed, "rowcount", 0):
            continue
        mail = (
            _render_sponsor(wedding, lines, f"Wesele: Wasze płatności ({today:%d.%m})")
            if sponsor
            else _render(wedding, items, f"Wesele: co przed Wami ({today:%d.%m})")
        )
        queue_mail(db, user.email, mail)
        sent += 1
    db.commit()
    return sent
