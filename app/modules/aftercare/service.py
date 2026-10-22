"""Po weselu: rozliczenie, co mają oddać usługodawcy, zmiana nazwiska, podziękowania.

Po weselu inne aplikacje „się kończą”, a zostaje sporo spraw: dopłaty, termin oddania zdjęć
i filmu z umowy (fotografowie się spóźniają), zmiana nazwiska w dokumentach i instytucjach.
Terminy urzędowe podajemy tylko tam, gdzie wskazuje je gov.pl (źródło przy pozycji).
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core import clock
from app.core.errors import Conflict, NotFound
from app.modules.aftercare.models import AfterCheck, Deliverable
from app.modules.audit import service as audit
from app.modules.identity.service import Principal
from app.modules.workspace.models import Wedding
from app.modules.workspace.permissions import Action, authorize

GOV_ID = "https://www.gov.pl/web/gov/uzyskaj-dowod-osobisty"
GOV_LICENCE = "https://www.gov.pl/web/gov/wymien-prawo-jazdy"


@dataclass(frozen=True)
class NameChangeItem:
    code: str
    title: str
    hint: str
    source: str | None = None
    # Orientacyjny termin: tyle dni po ślubie (zmiana w PESEL następuje zwykle wkrótce po ślubie).
    days_after: int | None = None


NAME_CHANGE: tuple[NameChangeItem, ...] = (
    NameChangeItem(
        "id_card",
        "Dowód osobisty",
        "Wniosek złóżcie jak najszybciej: dowód z nieaktualnym nazwiskiem zostanie unieważniony "
        "po 120 dniach od zarejestrowania zmiany w rejestrze PESEL.",
        GOV_ID,
        days_after=120,
    ),
    NameChangeItem(
        "driving_licence",
        "Prawo jazdy",
        "Po zmianie nazwiska prawo jazdy trzeba wymienić — termin i szczegóły "
        "sprawdźcie w urzędzie.",
        GOV_LICENCE,
    ),
    NameChangeItem(
        "passport",
        "Paszport",
        "Sprawdźcie na gov.pl, czy i kiedy trzeba wymienić paszport z poprzednim nazwiskiem.",
    ),
    NameChangeItem("bank", "Bank i karty płatnicze", "Zgłoście nowe nazwisko w każdym banku."),
    NameChangeItem(
        "employer", "Pracodawca lub uczelnia", "Kadry potrzebują nowych danych do umowy i PIT."
    ),
    NameChangeItem(
        "insurance", "Ubezpieczenia (polisy)", "Zgłoście zmianę ubezpieczycielom (np. OC, życie)."
    ),
    NameChangeItem(
        "contracts",
        "Umowy i rachunki",
        "Telefon, internet, prąd, gaz, najem — zgłoście nowe nazwisko u dostawców.",
    ),
    NameChangeItem(
        "accounts", "Konta i inne", "Np. przychodnia, programy lojalnościowe, adres e-mail."
    ),
)
BY_CODE = {i.code: i for i in NAME_CHANGE}


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


def deliverable_status(d: Deliverable, today: date) -> str:
    if d.received_on:
        return "received"
    if d.due_on and today > d.due_on:
        return "overdue"
    return "waiting"


def overview(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    from app.modules.budget.models import BudgetItem, Payment  # tylko odczyt płatności
    from app.modules.guests.models import Household
    from app.modules.vendors.models import Vendor

    wedding = db.get_one(Wedding, wedding_id)
    today = clock.today()
    day = wedding.wedding_date
    payments = db.execute(
        select(Payment, BudgetItem.name)
        .join(BudgetItem, BudgetItem.id == Payment.budget_item_id)
        .where(Payment.wedding_id == wedding_id, Payment.status == "scheduled")
        .order_by(Payment.due_date.asc().nulls_last())
    ).all()
    vendor_names = dict(
        db.execute(select(Vendor.id, Vendor.name).where(Vendor.wedding_id == wedding_id)).all()
    )
    deliverables = list(
        db.scalars(
            select(Deliverable)
            .where(Deliverable.wedding_id == wedding_id)
            .order_by(Deliverable.due_on.asc().nulls_last(), Deliverable.created_at)
        )
    )
    checks = {
        c.code: c.done_on
        for c in db.scalars(select(AfterCheck).where(AfterCheck.wedding_id == wedding_id))
    }
    gifts = db.execute(
        select(
            func.count().filter(Household.gift_note.is_not(None)),
            func.count().filter(Household.gift_note.is_not(None), Household.thanked.is_(True)),
            func.count().filter(Household.thanked.is_(True)),
        ).where(Household.wedding_id == wedding_id)
    ).one()
    return {
        "wedding_day": day,
        "after_wedding": day is not None and today > day,
        "open_payments": [
            {
                "id": p.id,
                "item_name": name,
                "amount": p.amount,
                "due_date": p.due_date,
                "overdue": p.due_date is not None and p.due_date < today,
            }
            for p, name in payments
        ],
        "deliverables": [
            {
                "id": d.id,
                "vendor_id": d.vendor_id,
                "vendor_name": vendor_names.get(d.vendor_id) if d.vendor_id else None,
                "title": d.title,
                "due_on": d.due_on,
                "received_on": d.received_on,
                "note": d.note,
                "status": deliverable_status(d, today),
                "days_late": (today - d.due_on).days
                if deliverable_status(d, today) == "overdue" and d.due_on
                else 0,
                "version": d.version,
            }
            for d in deliverables
        ],
        "name_change": [
            {
                "code": i.code,
                "title": i.title,
                "hint": i.hint,
                "source": i.source,
                "approx_deadline": day + timedelta(days=i.days_after)
                if day and i.days_after
                else None,
                "done_on": checks.get(i.code),
            }
            for i in NAME_CHANGE
        ],
        "thanks": {"with_gift": gifts[0], "thanked_with_gift": gifts[1], "thanked": gifts[2]},
    }


def _deliverable(db: Session, wedding_id: UUID, deliverable_id: UUID) -> Deliverable:
    d = db.get(Deliverable, deliverable_id)
    if d is None or d.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono pozycji.", code="deliverable.not_found")
    return d


def _check_vendor(db: Session, wedding_id: UUID, vendor_id: UUID | None) -> None:
    if vendor_id is not None:
        from app.modules.vendors import service as vendors

        vendors.get_in_wedding(db, wedding_id, vendor_id)


def create_deliverable(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]
) -> Deliverable:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    _check_vendor(db, wedding_id, data.get("vendor_id"))
    d = Deliverable(wedding_id=wedding_id, **data)
    db.add(d)
    db.flush()
    _record(db, principal, wedding_id, "deliverable", d.id, "create")
    db.commit()
    return d


def update_deliverable(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    deliverable_id: UUID,
    data: dict[str, Any],
    version: int,
) -> Deliverable:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    d = _deliverable(db, wedding_id, deliverable_id)
    if d.version != version:
        raise _conflict()
    if "vendor_id" in data:
        _check_vendor(db, wedding_id, data["vendor_id"])
    for k, v in data.items():
        if v is not None or k in ("vendor_id", "due_on", "received_on", "note"):
            setattr(d, k, v)
    _record(db, principal, wedding_id, "deliverable", d.id, "update")
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise _conflict() from exc
    return d


def delete_deliverable(
    db: Session, principal: Principal, wedding_id: UUID, deliverable_id: UUID
) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    db.delete(_deliverable(db, wedding_id, deliverable_id))
    _record(db, principal, wedding_id, "deliverable", deliverable_id, "delete")
    db.commit()


def set_check(db: Session, principal: Principal, wedding_id: UUID, code: str, done: bool) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    if code not in BY_CODE:
        raise NotFound("Nie ma takiej pozycji.", code="after_check.not_found")
    existing = db.get(AfterCheck, (wedding_id, code))
    if done and existing is None:
        db.add(AfterCheck(wedding_id=wedding_id, code=code, done_on=clock.today()))
    elif not done and existing is not None:
        db.delete(existing)
    db.commit()


def overdue_lines(db: Session, wedding_id: UUID) -> list[str]:
    """Do podsumowania e-mail: rzeczy od usługodawców po terminie."""
    today = clock.today()
    rows = db.scalars(
        select(Deliverable).where(
            Deliverable.wedding_id == wedding_id,
            Deliverable.received_on.is_(None),
            Deliverable.due_on.is_not(None),
            Deliverable.due_on < today,
        )
    )
    return [f"{d.title}: termin minął {d.due_on:%d.%m.%Y}" for d in rows if d.due_on]
