"""Portfel sponsorów: kto poza parą dokłada się do wesela, ile obiecał, ile już dał.

Pieniądze sponsora liczymy na dwa sposoby: płatności za usługi przypisane do sponsora
(sponsor płaci firmie, `Payment.funder_id`) i wpłaty przekazane parze (`FunderContribution`).
„Do wyrównania” = obiecane - (zapłacone + przekazane + zaplanowane). Wartość ujemna oznacza,
że sponsorowi przypisano więcej, niż obiecał.
"""

from collections import defaultdict
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.errors import Conflict, NotFound
from app.modules.audit import service as audit
from app.modules.budget.models import BudgetItem, Funder, FunderContribution, Payment
from app.modules.identity.service import Principal
from app.modules.workspace.models import WeddingMember
from app.modules.workspace.permissions import Action, authorize

ZERO = Decimal("0.00")
OPEN = ("scheduled",)


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


def get_funder(db: Session, wedding_id: UUID, funder_id: UUID) -> Funder:
    f = db.get(Funder, funder_id)
    if f is None or f.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono sponsora.", code="funder.not_found")
    return f


def _ordered(db: Session, wedding_id: UUID) -> list[Funder]:
    return list(
        db.scalars(
            select(Funder)
            .where(Funder.wedding_id == wedding_id)
            .order_by(Funder.position, Funder.created_at)
        )
    )


def _totals(db: Session, wedding_id: UUID) -> dict[UUID | None, dict[str, Decimal]]:
    """Sumy płatności (zapłacone / zaplanowane) i wpłat na sponsora; klucz None = para."""
    out: dict[UUID | None, dict[str, Decimal]] = defaultdict(
        lambda: {"paid": ZERO, "scheduled": ZERO, "given": ZERO, "reported": ZERO}
    )
    for funder_id, status, total in db.execute(
        select(Payment.funder_id, Payment.status, func.sum(Payment.amount))
        .where(Payment.wedding_id == wedding_id, Payment.status.in_(("paid", "scheduled")))
        .group_by(Payment.funder_id, Payment.status)
    ):
        out[funder_id][status] += total
    for funder_id, status, total in db.execute(
        select(
            FunderContribution.funder_id,
            FunderContribution.status,
            func.sum(FunderContribution.amount),
        )
        .where(FunderContribution.wedding_id == wedding_id)
        .group_by(FunderContribution.funder_id, FunderContribution.status)
    ):
        out[funder_id]["given" if status == "confirmed" else "reported"] += total
    return out


def summary_of(f: Funder, t: dict[str, Decimal]) -> dict[str, Any]:
    committed = t["paid"] + t["given"] + t["scheduled"]
    return {
        "id": f.id,
        "name": f.name,
        "side": f.side,
        "pledged_amount": f.pledged_amount,
        "notes": f.notes,
        "position": f.position,
        "version": f.version,
        "paid_direct": t["paid"],
        "scheduled_direct": t["scheduled"],
        "given": t["given"],
        "reported": t["reported"],
        "covered": t["paid"] + t["given"],
        "to_settle": (f.pledged_amount - committed) if f.pledged_amount is not None else None,
    }


def overview(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    totals = _totals(db, wedding_id)
    funders = [summary_of(f, totals[f.id]) for f in _ordered(db, wedding_id)]
    couple = totals[None]
    return {
        "funders": funders,
        "pledged_total": sum((f["pledged_amount"] or ZERO for f in funders), ZERO),
        "covered_total": sum((f["covered"] for f in funders), ZERO),
        "couple_paid": couple["paid"],
        "couple_scheduled": couple["scheduled"],
    }


def create(db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]) -> Funder:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    last = db.scalar(select(func.max(Funder.position)).where(Funder.wedding_id == wedding_id))
    f = Funder(wedding_id=wedding_id, position=0 if last is None else last + 1, **data)
    db.add(f)
    db.flush()
    _record(db, principal, wedding_id, "funder", f.id, "create")
    db.commit()
    return f


def update(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    funder_id: UUID,
    data: dict[str, Any],
    version: int,
) -> Funder:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    f = get_funder(db, wedding_id, funder_id)
    if f.version != version:
        raise _conflict()
    for k, v in data.items():
        if v is not None or k in ("pledged_amount", "notes"):
            setattr(f, k, v)
    _record(db, principal, wedding_id, "funder", f.id, "update")
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise _conflict() from exc
    return f


def delete(db: Session, principal: Principal, wedding_id: UUID, funder_id: UUID) -> None:
    """Usunięcie sponsora: jego płatności wracają do pary, wpłaty znikają, sponsor traci wgląd."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    f = get_funder(db, wedding_id, funder_id)
    db.delete(f)
    _record(db, principal, wedding_id, "funder", funder_id, "delete")
    db.commit()


def detail(db: Session, wedding_id: UUID, f: Funder) -> dict[str, Any]:
    """Wkład jednego sponsora: podsumowanie, przypisane płatności i wpłaty (bez reszty budżetu)."""
    totals = _totals(db, wedding_id)
    payments = db.execute(
        select(Payment, BudgetItem.name)
        .join(BudgetItem, BudgetItem.id == Payment.budget_item_id)
        .where(Payment.funder_id == f.id, Payment.status.in_(("paid", "scheduled")))
        .order_by(Payment.due_date.asc().nulls_last(), Payment.created_at)
    )
    contributions = db.scalars(
        select(FunderContribution)
        .where(FunderContribution.funder_id == f.id)
        .order_by(FunderContribution.received_on.asc().nulls_last(), FunderContribution.created_at)
    )
    return {
        "funder": summary_of(f, totals[f.id]),
        "payments": [
            {
                "id": p.id,
                "item_name": name,
                "kind": p.kind,
                "amount": p.amount,
                "due_date": p.due_date,
                "paid_on": p.paid_on,
                "status": p.status,
            }
            for p, name in payments
        ],
        "contributions": [
            {
                "id": c.id,
                "amount": c.amount,
                "received_on": c.received_on,
                "note": c.note,
                "status": c.status,
            }
            for c in contributions
        ],
    }


def get_detail(
    db: Session, principal: Principal, wedding_id: UUID, funder_id: UUID
) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return detail(db, wedding_id, get_funder(db, wedding_id, funder_id))


def my_contribution(db: Session, principal: Principal, wedding_id: UUID) -> dict[str, Any]:
    """Widok sponsora: tylko wkład przypisany do jego członkostwa."""
    member: WeddingMember = authorize(db, principal.user.id, wedding_id, Action.FUNDER_SELF)
    if member.funder_id is None:
        raise NotFound("Para nie przypisała jeszcze Twojego wkładu.", code="funder.not_assigned")
    return detail(db, wedding_id, get_funder(db, wedding_id, member.funder_id))


def add_contribution(
    db: Session, principal: Principal, wedding_id: UUID, funder_id: UUID, data: dict[str, Any]
) -> FunderContribution:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    get_funder(db, wedding_id, funder_id)
    c = FunderContribution(wedding_id=wedding_id, funder_id=funder_id, **data)
    db.add(c)
    db.flush()
    _record(db, principal, wedding_id, "funder_contribution", c.id, "create")
    db.commit()
    return c


def delete_contribution(
    db: Session, principal: Principal, wedding_id: UUID, funder_id: UUID, contribution_id: UUID
) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    c = db.get(FunderContribution, contribution_id)
    if c is None or c.wedding_id != wedding_id or c.funder_id != funder_id:
        raise NotFound("Nie znaleziono wpłaty.", code="funder_contribution.not_found")
    db.delete(c)
    _record(db, principal, wedding_id, "funder_contribution", contribution_id, "delete")
    db.commit()


def check_funder(db: Session, wedding_id: UUID, funder_id: UUID | None) -> None:
    """Walidacja `funder_id` w płatności (sponsor z tego samego wesela)."""
    if funder_id is not None:
        get_funder(db, wedding_id, funder_id)


def report_transfer(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]
) -> dict[str, Any]:
    """Sponsor zgłasza przelew dla pary; kwota czeka na potwierdzenie (nie liczy się od razu)."""
    member: WeddingMember = authorize(db, principal.user.id, wedding_id, Action.FUNDER_SELF)
    if member.funder_id is None:
        raise NotFound("Para nie przypisała jeszcze Twojego wkładu.", code="funder.not_assigned")
    f = get_funder(db, wedding_id, member.funder_id)
    c = FunderContribution(wedding_id=wedding_id, funder_id=f.id, status="reported", **data)
    db.add(c)
    db.flush()
    _record(db, principal, wedding_id, "funder_contribution", c.id, "report")
    db.commit()
    return detail(db, wedding_id, f)


def confirm_contribution(
    db: Session, principal: Principal, wedding_id: UUID, funder_id: UUID, contribution_id: UUID
) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    c = db.get(FunderContribution, contribution_id)
    if c is None or c.wedding_id != wedding_id or c.funder_id != funder_id:
        raise NotFound("Nie znaleziono wpłaty.", code="funder_contribution.not_found")
    c.status = "confirmed"
    _record(db, principal, wedding_id, "funder_contribution", c.id, "confirm")
    db.commit()


def reported_lines(db: Session, wedding_id: UUID) -> list[tuple[str, Decimal]]:
    """Zgłoszone, niepotwierdzone przelewy sponsorów (do „Wymaga uwagi”)."""
    return [
        (name, amount)
        for name, amount in db.execute(
            select(Funder.name, FunderContribution.amount)
            .join(Funder, Funder.id == FunderContribution.funder_id)
            .where(
                FunderContribution.wedding_id == wedding_id,
                FunderContribution.status == "reported",
            )
            .order_by(FunderContribution.created_at)
        )
    ]
