"""Dane demonstracyjne (wyłącznie fikcyjne) dla środowiska deweloperskiego.

Konto demo: demo@example.com, hasło z WP_SEED_PASSWORD albo domyślne poniżej.
Skrypt odmawia działania przy WP_ENV=prod.
"""

import os
import sys
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_sessionmaker, utcnow
from app.core.security import hash_password
from app.modules.identity.models import Consent, User
from app.modules.workspace.models import Event, Wedding, WeddingMember

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = os.environ.get("WP_SEED_PASSWORD", "Demo-Wesele-2027!")  # gitleaks:allow


HOUSEHOLDS = [
    # (nazwa, strona, osoby, odpowiedź na przyjęcie dla kolejnych osób, poprawiny)
    (
        "Państwo Kowalscy",
        "bride",
        ["Joanna Kowalska", "Piotr Kowalski", "Zosia Kowalska"],
        ["attending", "attending", "attending"],
        ["attending", "attending", "declined"],
    ),
    (
        "Agnieszka Nowak z osobą towarzyszącą",
        "groom",
        ["Agnieszka Nowak", "Tomasz Wiśniewski"],
        ["pending", "pending"],
        ["pending", "pending"],
    ),
    ("Marta Zielińska", "bride", ["Marta Zielińska"], ["attending"], ["maybe"]),
    ("Ciocia Halina", "groom", ["Halina Lewandowska"], ["maybe"], ["pending"]),
    ("Wujek Zenek", "groom", ["Zenon Wójcik"], ["declined"], ["declined"]),
]

ITEMS = [
    # (kategoria zawiera, nazwa, kwota, status, płatności: (rodzaj, kwota, dni od dziś, zapłacona))
    (
        "Sala",
        "Sala i menu",
        "37200.00",
        "confirmed",
        [("deposit_zadatek", "5000.00", -60, True), ("installment", "15000.00", 20, False)],
    ),
    (
        "Fotograf",
        "Fotograf",
        "5000.00",
        "confirmed",
        [("deposit_zadatek", "1500.00", -30, True), ("final", "3500.00", 45, False)],
    ),
    ("Muzyka", "DJ", "4500.00", "confirmed", [("advance_zaliczka", "2000.00", 12, False)]),
    ("Dekoracje", "Dekoracje i kwiaty", "4800.00", "planned", []),
]


def demo_content() -> None:
    """Fikcyjna zawartość wesela demo: zadania, budżet z płatnościami, goście z odpowiedziami."""
    from datetime import timedelta

    import app.models  # noqa: F401  # rejestracja wszystkich modeli (klucze obce)
    from app.core import clock
    from app.modules.budget import service as budget
    from app.modules.budget.models import BudgetCategory, BudgetItem, Payment
    from app.modules.guests.models import Guest, GuestEventAttendance, Household
    from app.modules.planner import service as planner
    from app.modules.planner.models import Task

    with get_sessionmaker()() as db:
        user = db.scalars(select(User).where(User.email == DEMO_EMAIL)).one()
        wedding = db.scalars(
            select(Wedding)
            .join(WeddingMember, WeddingMember.wedding_id == Wedding.id)
            .where(WeddingMember.user_id == user.id)
        ).first()
        if wedding is None:
            sys.exit("Brak wesela demo: uruchom najpierw `python -m scripts.seed`.")
        if not db.scalars(select(Task.id).where(Task.wedding_id == wedding.id)).first():
            planner.generate_for_wedding(db, wedding)
        if not db.scalars(
            select(BudgetCategory.id).where(BudgetCategory.wedding_id == wedding.id)
        ).first():
            budget.create_default_categories(db, wedding)
        db.flush()
        today = clock.today()
        if not db.scalars(select(BudgetItem.id).where(BudgetItem.wedding_id == wedding.id)).first():
            cats = list(
                db.scalars(select(BudgetCategory).where(BudgetCategory.wedding_id == wedding.id))
            )
            for hint, name, amount, status, payments in ITEMS:
                cat = next((c for c in cats if hint.lower() in c.name.lower()), cats[0])
                item = BudgetItem(
                    wedding_id=wedding.id,
                    category_id=cat.id,
                    name=name,
                    planned_amount=Decimal(amount),
                    confirmed_amount=Decimal(amount) if status == "confirmed" else None,
                    status=status,
                )
                db.add(item)
                db.flush()
                for kind, value, days, paid in payments:
                    due = today + timedelta(days=days)
                    db.add(
                        Payment(
                            wedding_id=wedding.id,
                            budget_item_id=item.id,
                            kind=kind,
                            amount=Decimal(value),
                            due_date=due,
                            paid_on=due if paid else None,
                            status="paid" if paid else "scheduled",
                        )
                    )
        if not db.scalars(select(Household.id).where(Household.wedding_id == wedding.id)).first():
            events = {
                e.kind: e.id
                for e in db.scalars(select(Event).where(Event.wedding_id == wedding.id))
            }
            for name, side, people, reception, after in HOUSEHOLDS:
                h = Household(wedding_id=wedding.id, name=name, side=side, invitation_status="sent")
                db.add(h)
                db.flush()
                for person, r, a in zip(people, reception, after, strict=True):
                    first, *last = person.split()
                    g = Guest(
                        wedding_id=wedding.id,
                        household_id=h.id,
                        first_name=first,
                        last_name=" ".join(last) or None,
                        age_group="child" if first == "Zosia" else "adult",
                    )
                    db.add(g)
                    db.flush()
                    for kind, status in (("reception", r), ("after_party", a)):
                        if kind in events and status != "pending":
                            db.add(
                                GuestEventAttendance(
                                    guest_id=g.id, event_id=events[kind], status=status
                                )
                            )
        db.commit()
    print("Zawartość wesela demo gotowa (dane fikcyjne).")


def load_users(count: int) -> None:
    """Konta do testów obciążeniowych: loadtest-N@example.com (zweryfikowane, bez wesel)."""
    settings = get_settings()
    password_hash = hash_password(DEMO_PASSWORD)
    with get_sessionmaker()() as db:
        existing = set(db.scalars(select(User.email).where(User.email.like("loadtest-%"))))
        for i in range(count):
            email = f"loadtest-{i}@example.com"
            if email in existing:
                continue
            user = User(
                email=email,
                password_hash=password_hash,
                display_name=f"Test obciążeniowy {i}",
                email_verified_at=utcnow(),
            )
            db.add(user)
            db.flush()
            db.add(Consent(user_id=user.id, type="terms", document_version=settings.terms_version))
            db.add(
                Consent(user_id=user.id, type="privacy", document_version=settings.privacy_version)
            )
        db.commit()
    print(f"Konta testów obciążeniowych: {count}.")


def main() -> None:
    settings = get_settings()
    if settings.env == "prod":
        sys.exit("Seed jest zablokowany w środowisku produkcyjnym.")
    if sys.argv[1:2] == ["--content"]:
        demo_content()
        return
    if sys.argv[1:2] == ["--load-users"]:
        load_users(int(sys.argv[2]) if len(sys.argv) > 2 else 50)
        return
    with get_sessionmaker()() as db:
        if db.scalars(select(User).where(User.email == DEMO_EMAIL)).first():
            print("Dane demo już istnieją: bez zmian.")
            return
        user = User(
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            display_name="Konto demo",
            email_verified_at=utcnow(),
        )
        db.add(user)
        db.flush()
        db.add(Consent(user_id=user.id, type="terms", document_version=settings.terms_version))
        db.add(Consent(user_id=user.id, type="privacy", document_version=settings.privacy_version))
        wedding = Wedding(
            name="Wesele demo",
            planned_month=datetime(2027, 8, 1, tzinfo=UTC).date(),
            ceremony_type="concordat",
            city="Kraków",
            region="małopolskie",
            guest_count_planned=110,
            total_budget=Decimal("65000.00"),
            colors=["szałwia", "złoto"],
            priorities=["muzyka", "fotograf"],
        )
        db.add(wedding)
        db.flush()
        db.add(WeddingMember(wedding_id=wedding.id, user_id=user.id, role="owner"))
        db.add_all(
            [
                Event(wedding_id=wedding.id, kind="ceremony", name="Ślub w kościele"),
                Event(wedding_id=wedding.id, kind="reception", name="Przyjęcie weselne"),
                Event(wedding_id=wedding.id, kind="after_party", name="Poprawiny"),
            ]
        )
        db.commit()
        print(f"Utworzono konto {DEMO_EMAIL} i wesele demo.")


if __name__ == "__main__":
    main()
