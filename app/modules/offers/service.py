"""Oferty: komponenty cenowe, warunki, zatwierdzanie, porównanie kosztu, wybór → budżet."""

import re
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.db import utcnow
from app.core.errors import Conflict, NotFound, Unprocessable
from app.modules.audit import service as audit
from app.modules.budget.models import BudgetCategory, BudgetItem, Payment
from app.modules.documents import service as documents
from app.modules.guests import service as guests
from app.modules.identity.service import Principal
from app.modules.offers import pricing
from app.modules.offers.models import Offer, OfferTerm, PricingComponent
from app.modules.planner.service import wedding_anchor
from app.modules.vendors import service as vendors
from app.modules.vendors.models import CATEGORIES, Vendor
from app.modules.workspace.models import Wedding
from app.modules.workspace.permissions import Action, authorize

COMPARABLE = ("approved", "selected")
UNCERTAIN = ("low", "unverified")


def _conflict() -> Conflict:
    return Conflict("Oferta zmieniła się w międzyczasie.", code="conflict.version_mismatch")


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
        entity_type="offer",
        entity_id=entity_id,
        wedding_id=wedding_id,
        action=action,
        changes=changes,
    )


def _get(db: Session, wedding_id: UUID, offer_id: UUID) -> Offer:
    o = db.get(Offer, offer_id)
    if o is None or o.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono oferty.", code="offer.not_found")
    return o


def components_of(db: Session, offer_ids: list[UUID]) -> dict[UUID, list[PricingComponent]]:
    out: dict[UUID, list[PricingComponent]] = {o: [] for o in offer_ids}
    if offer_ids:
        for c in db.scalars(
            select(PricingComponent)
            .where(PricingComponent.offer_id.in_(offer_ids))
            .order_by(PricingComponent.position)
        ):
            out[c.offer_id].append(c)
    return out


def terms_of(db: Session, offer_ids: list[UUID]) -> dict[UUID, list[OfferTerm]]:
    out: dict[UUID, list[OfferTerm]] = {o: [] for o in offer_ids}
    if offer_ids:
        for t in db.scalars(select(OfferTerm).where(OfferTerm.offer_id.in_(offer_ids))):
            out[t.offer_id].append(t)
    return out


def unverified_count(components: list[PricingComponent], terms: list[OfferTerm]) -> int:
    return sum(1 for c in components if c.confidence in UNCERTAIN) + sum(
        1 for t in terms if t.confidence in UNCERTAIN
    )


# --- cytaty: każda informacja z dokumentu musi dać się w nim odnaleźć ----------------------


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _check_citations(
    db: Session, wedding_id: UUID, version_id: UUID | None, items: list[dict[str, Any]]
) -> None:
    cited = [i for i in items if i.get("citation")]
    if not cited:
        return
    if version_id is None:
        raise Unprocessable(
            "Cytat wymaga powiązania oferty z dokumentem źródłowym.",
            code="offer.citation_without_document",
        )
    version = documents.version_in_wedding(db, wedding_id, version_id)
    documents.ensure_text(version.text_status)
    text = _norm(version.extracted_text or "")
    for item in cited:
        if _norm(item["citation"]["quote"]) not in text:
            raise Unprocessable(
                f"Cytat dla „{item.get('label') or item.get('term_type')}” nie występuje w "
                "tekście dokumentu.",
                code="offer.citation_not_found",
            )


def _replace_children(db: Session, offer: Offer, data: dict[str, Any]) -> None:
    if data.get("components") is not None:
        for c in db.scalars(select(PricingComponent).where(PricingComponent.offer_id == offer.id)):
            db.delete(c)
        for i, c in enumerate(data["components"]):
            db.add(PricingComponent(offer_id=offer.id, position=i, **c))
    if data.get("terms") is not None:
        for t in db.scalars(select(OfferTerm).where(OfferTerm.offer_id == offer.id)):
            db.delete(t)
        for t in data["terms"]:
            citation, confidence = t.pop("citation", None), t.pop("confidence", "high")
            db.add(
                OfferTerm(
                    offer_id=offer.id,
                    term_type=t["term_type"],
                    value=_jsonable(t),
                    citation=citation,
                    confidence=confidence,
                )
            )


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items() if v not in (None, [])}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


# --- CRUD -------------------------------------------------------------------------------


def list_offers(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    *,
    vendor_id: UUID | None,
    status: str | None,
    category: str | None,
) -> list[tuple[Offer, Vendor]]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    stmt = (
        select(Offer, Vendor)
        .join(Vendor, Vendor.id == Offer.vendor_id)
        .where(Offer.wedding_id == wedding_id)
    )
    if vendor_id:
        stmt = stmt.where(Offer.vendor_id == vendor_id)
    if status:
        stmt = stmt.where(Offer.status == status)
    if category:
        stmt = stmt.where(Vendor.category == category)
    return [(o, v) for o, v in db.execute(stmt.order_by(Offer.created_at))]


def create_offer(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]
) -> Offer:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    vendor = vendors.get_in_wedding(db, wedding_id, data["vendor_id"])
    version_id = data.get("source_document_version_id")
    if version_id:
        documents.version_in_wedding(db, wedding_id, version_id)
    _check_citations(db, wedding_id, version_id, [*data["components"], *data["terms"]])
    offer = Offer(
        wedding_id=wedding_id,
        vendor_id=vendor.id,
        title=data["title"],
        valid_until=data.get("valid_until"),
        min_guests=data.get("min_guests"),
        notes=data.get("notes"),
        status=data["status"],
        source="manual",
        source_document_version_id=version_id,
    )
    if offer.status == "approved":
        offer.approved_by, offer.approved_at = principal.user.id, utcnow()
    db.add(offer)
    db.flush()
    _replace_children(db, offer, data)
    if vendor.status in ("considering", "contacted"):
        vendor.status = "offer_received"
    _record(
        db,
        principal,
        wedding_id,
        offer.id,
        "create",
        {"components": [None, len(data["components"])]},
    )
    db.commit()
    return offer


def get_offer(
    db: Session, principal: Principal, wedding_id: UUID, offer_id: UUID
) -> tuple[Offer, Vendor]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    offer = _get(db, wedding_id, offer_id)
    return offer, db.get_one(Vendor, offer.vendor_id)


def update_offer(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    offer_id: UUID,
    data: dict[str, Any],
    version: int,
) -> Offer:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    offer = _get(db, wedding_id, offer_id)
    if offer.version != version:
        raise _conflict()
    if offer.status == "selected":
        raise Conflict(
            "Oferta jest już wybrana i rozliczona w budżecie.", code="offer.already_selected"
        )
    _check_citations(
        db,
        wedding_id,
        offer.source_document_version_id,
        [*(data.get("components") or []), *(data.get("terms") or [])],
    )
    for key in ("title", "valid_until", "min_guests", "notes"):
        if key in data and (data[key] is not None or key != "title"):
            setattr(offer, key, data[key])
    _replace_children(db, offer, data)
    if offer.status == "approved" and ("components" in data or "terms" in data):
        offer.status = "needs_review"  # zmiana treści oferty wymaga ponownego zatwierdzenia
    offer.updated_at = utcnow()
    _record(db, principal, wedding_id, offer.id, "update", {"fields": [None, sorted(data)]})
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise _conflict() from exc
    return offer


def create_ai_draft(
    db: Session,
    *,
    wedding_id: UUID,
    vendor_id: UUID,
    version_id: UUID,
    title: str,
    min_guests: int | None,
    components: list[dict[str, Any]],
    terms: list[dict[str, Any]],
    ai_run_id: UUID,
) -> Offer:
    """Szkic oferty z AI: zawsze `needs_review`. Cytaty zweryfikowane wcześniej przez
    ai.extractor (pozycje bez potwierdzenia mają confidence="unverified")."""
    offer = Offer(
        wedding_id=wedding_id,
        vendor_id=vendor_id,
        title=title,
        min_guests=min_guests,
        status="needs_review",
        source="ai_extraction",
        source_document_version_id=version_id,
        notes="Szkic przygotowany automatycznie. Sprawdź każdą pozycję z dokumentem.",
    )
    db.add(offer)
    db.flush()
    _replace_children(db, offer, {"components": components, "terms": terms})
    audit.record(
        db,
        actor_type="system",
        actor_id=None,
        entity_type="offer",
        entity_id=offer.id,
        wedding_id=wedding_id,
        action="ai_draft",
        changes={"ai_run": [None, str(ai_run_id)]},
    )
    return offer


def delete_offer(db: Session, principal: Principal, wedding_id: UUID, offer_id: UUID) -> None:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    offer = _get(db, wedding_id, offer_id)
    db.delete(offer)
    _record(db, principal, wedding_id, offer_id, "delete")
    db.commit()


def approve(
    db: Session, principal: Principal, wedding_id: UUID, offer_id: UUID, confirm_unverified: bool
) -> Offer:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    offer = _get(db, wedding_id, offer_id)
    if offer.status not in ("draft", "needs_review", "rejected"):
        raise Conflict("Oferty w tym stanie nie można zatwierdzić.", code="offer.invalid_state")
    uncertain = unverified_count(
        components_of(db, [offer.id])[offer.id], terms_of(db, [offer.id])[offer.id]
    )
    if uncertain and not confirm_unverified:
        raise Conflict(
            f"Oferta ma {uncertain} niepewnych pól. Sprawdź je i potwierdź "
            "(confirm_unverified=true).",
            code="offer.unverified_fields",
        )
    offer.status, offer.approved_by, offer.approved_at = "approved", principal.user.id, utcnow()
    _record(
        db, principal, wedding_id, offer.id, "approve", {"unverified_confirmed": [None, uncertain]}
    )
    db.commit()
    return offer


def reject(db: Session, principal: Principal, wedding_id: UUID, offer_id: UUID) -> Offer:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    offer = _get(db, wedding_id, offer_id)
    if offer.status == "selected":
        raise Conflict("Wybranej oferty nie można odrzucić.", code="offer.already_selected")
    offer.status = "rejected"
    _record(db, principal, wedding_id, offer.id, "reject")
    db.commit()
    return offer


# --- wycena i porównanie -------------------------------------------------------------------


def priced_components(rows: list[PricingComponent]) -> list[pricing.Component]:
    return [
        pricing.Component(
            label=c.label,
            kind=c.kind,
            amount=c.amount,
            quantity=c.quantity,
            included=c.included,
            optional=c.optional,
            event_kind=c.event_kind,
        )
        for c in rows
    ]


def scenario_for(db: Session, wedding: Wedding, data: dict[str, Any]) -> pricing.Scenario:
    adults, children = guests.age_breakdown(db, wedding, data.get("guest_basis", "planned"))
    if data.get("adults") is not None:
        adults = data["adults"]
    if data.get("children") is not None:
        children = data["children"]
    crew = data.get("crew")
    if crew is None:
        crew = crew_meals(db, wedding.id)
    return pricing.Scenario(
        adults=adults,
        children=children,
        after_party_adults=data.get("after_party_adults"),
        after_party_children=data.get("after_party_children"),
        hours=data.get("hours"),
        include_optional=data.get("include_optional", False),
        crew=crew,
    )


def crew_meals(db: Session, wedding_id: UUID) -> int:
    """Posiłki dla obsługi: suma z usługodawców wesela (bez odrzuconych)."""
    total = db.scalar(
        select(func.coalesce(func.sum(Vendor.crew_meals), 0)).where(
            Vendor.wedding_id == wedding_id, Vendor.status != "rejected"
        )
    )
    return int(total or 0)


def missing_terms(vendor: Vendor, terms: list[OfferTerm]) -> list[str]:
    """Neutralne flagi informacyjne (bez oceny prawnej), zob. iteracja 4."""
    types = {t.term_type for t in terms}
    missing = []
    if not types & {"deposit", "payment_schedule"}:
        missing.append("Brak informacji o zadatku/zaliczce i terminach płatności.")
    if "cancellation" not in types:
        missing.append("Nie wpisano warunków odwołania lub zmiany terminu.")
    if vendor.category in ("venue", "catering") and "drinks" not in types:
        missing.append("Brak informacji o napojach i alkoholu (w cenie czy osobno?).")
    return missing


def compare(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]
) -> tuple[pricing.Scenario, list[dict[str, Any]]]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    wedding = db.get_one(Wedding, wedding_id)
    ids = list(dict.fromkeys(data["offer_ids"]))
    offers = [_get(db, wedding_id, i) for i in ids]
    not_ready = [o.title for o in offers if o.status not in COMPARABLE]
    if not_ready:
        raise Conflict(
            f"Najpierw zatwierdź oferty: {', '.join(not_ready)}.", code="offer.not_approved"
        )
    scenario = scenario_for(db, wedding, data)
    comps, terms = components_of(db, ids), terms_of(db, ids)
    results = []
    for o in offers:
        vendor = db.get_one(Vendor, o.vendor_id)
        q = pricing.quote(priced_components(comps[o.id]), o.min_guests, scenario)
        results.append(
            {
                "offer": o,
                "vendor": vendor,
                "quote": q,
                "missing_terms": missing_terms(vendor, terms[o.id]),
            }
        )
    return scenario, results


# --- wybór oferty: pozycja budżetu + płatności ---------------------------------------------


def select_offer(
    db: Session, principal: Principal, wedding_id: UUID, offer_id: UUID, data: dict[str, Any]
) -> dict[str, Any]:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    offer = _get(db, wedding_id, offer_id)
    if offer.status == "selected":
        raise Conflict("Ta oferta jest już wybrana.", code="offer.already_selected")
    if offer.status != "approved":
        raise Conflict("Najpierw zatwierdź ofertę.", code="offer.not_approved")
    wedding = db.get_one(Wedding, wedding_id)
    vendor = db.get_one(Vendor, offer.vendor_id)
    category = _budget_category(db, wedding_id, vendor, data.get("budget_category_id"))
    scenario = scenario_for(db, wedding, {"guest_basis": data["guest_basis"]})
    q = pricing.quote(
        priced_components(components_of(db, [offer.id])[offer.id]), offer.min_guests, scenario
    )
    item = BudgetItem(
        wedding_id=wedding_id,
        category_id=category.id,
        name=f"{vendor.name}: {offer.title}"[:200],
        cost_mode="fixed",
        planned_amount=q.total,
        status="confirmed",
        vendor_id=vendor.id,
        offer_id=offer.id,
        notes=(
            f"Wyliczono z oferty dla {scenario.adults} dorosłych i {scenario.children} "
            f"dzieci ({data['guest_basis']}). Nieznane pozycje: "
            f"{', '.join(q.unknown) or 'brak'}."
        ),
    )
    db.add(item)
    db.flush()
    warnings = list(q.warnings)
    created = 0
    if data["create_payments"]:
        created = _create_payments(db, wedding, item, terms_of(db, [offer.id])[offer.id], warnings)
    offer.status, offer.selected_budget_item_id = "selected", item.id
    vendor.status = "booked"
    rejected = 0
    if data["reject_competing"]:
        competing = db.scalars(
            select(Offer)
            .join(Vendor, Vendor.id == Offer.vendor_id)
            .where(
                Offer.wedding_id == wedding_id,
                Offer.id != offer.id,
                Vendor.category == vendor.category,
                Offer.status.in_(("draft", "needs_review", "approved")),
            )
        )
        for other in competing:
            other.status = "rejected"
            rejected += 1
    _record(
        db,
        principal,
        wedding_id,
        offer.id,
        "select",
        {
            "budget_item": [None, str(item.id)],
            "total": [None, str(q.total)],
            "payments": [None, created],
            "rejected": [None, rejected],
        },
    )
    db.commit()
    return {
        "offer_id": offer.id,
        "budget_item_id": item.id,
        "planned_amount": q.total,
        "payments_created": created,
        "rejected_offers": rejected,
        "warnings": warnings,
    }


def _budget_category(
    db: Session, wedding_id: UUID, vendor: Vendor, category_id: UUID | None
) -> BudgetCategory:
    if category_id:
        c = db.get(BudgetCategory, category_id)
        if c is None or c.wedding_id != wedding_id:
            raise NotFound("Nie znaleziono kategorii budżetu.", code="budget.category_not_found")
        return c
    wanted = CATEGORIES[vendor.category][1]
    categories = list(
        db.scalars(select(BudgetCategory).where(BudgetCategory.wedding_id == wedding_id))
    )
    for name in (wanted, "Inne"):
        for c in categories:
            if c.name.lower() == name.lower():
                return c
    c = BudgetCategory(
        wedding_id=wedding_id, name="Inne", sort_order=1000, planned_amount=Decimal("0.00")
    )
    db.add(c)
    db.flush()
    return c


def payment_rows(
    terms: list[OfferTerm], anchor: date | None, warnings: list[str]
) -> list[dict[str, Any]]:
    """Płatności wpisane w warunkach oferty (zadatek/zaliczka, raty) z wyliczonym terminem."""
    out: list[dict[str, Any]] = []
    for t in terms:
        v = t.value
        rows: list[dict[str, Any]] = []
        if t.term_type == "deposit":
            rows = [
                {"kind": v["deposit_kind"], "amount": v["amount"], "due_date": v.get("due_date")}
            ]
        elif t.term_type == "payment_schedule":
            rows = v.get("installments", [])
        for r in rows:
            due = date.fromisoformat(r["due_date"]) if r.get("due_date") else None
            if due is None and r.get("days_before_wedding") is not None:
                if anchor is None:
                    warnings.append("payment.no_date: brak daty ślubu, termin płatności pusty")
                else:
                    due = anchor - timedelta(days=int(r["days_before_wedding"]))
            out.append(
                {"kind": r["kind"], "amount": Decimal(r["amount"]["amount"]), "due_date": due}
            )
    return out


def payment_plan(
    terms: list[OfferTerm], total: Decimal, anchor: date | None
) -> tuple[list[dict[str, Any]], Decimal, list[str]]:
    """Harmonogram płatności dla wyceny (bez zapisu).

    Kwoty stałe (zadatek, zaliczka, raty) — jak w ofercie. Dopłata = suma - kwoty stałe: przy
    innej liczbie gości zmienia się właśnie ona. Rata „final” z oferty wyznacza tylko termin
    dopłaty (jej kwota w ofercie dotyczyła liczby gości z oferty).
    """
    warnings: list[str] = []
    rows = payment_rows(terms, anchor, warnings)
    fixed = [{**r, "computed": False} for r in rows if r["kind"] != "final"]
    final_due = next((r["due_date"] for r in rows if r["kind"] == "final"), None)
    remainder = total - sum((r["amount"] for r in fixed), Decimal("0"))
    if remainder < 0:
        warnings.append("payment.fixed_exceed_total: kwoty stałe z oferty przekraczają koszt")
        remainder = Decimal("0")
    plan = sorted(fixed, key=lambda r: (r["due_date"] is None, r["due_date"] or date.max))
    if remainder > 0:
        plan.append({"kind": "final", "amount": remainder, "due_date": final_due, "computed": True})
    return plan, remainder, warnings


def scenarios(
    db: Session, principal: Principal, wedding_id: UUID, data: dict[str, Any]
) -> list[dict[str, Any]]:
    """„Co jeśli”: te same oferty w 2-3 scenariuszach, różnica względem pierwszego i raty."""
    authorize(db, principal.user.id, wedding_id, Action.READ)
    wedding = db.get_one(Wedding, wedding_id)
    ids = list(dict.fromkeys(data["offer_ids"]))
    offers = [_get(db, wedding_id, i) for i in ids]
    not_ready = [o.title for o in offers if o.status not in COMPARABLE]
    if not_ready:
        raise Conflict(
            f"Najpierw zatwierdź oferty: {', '.join(not_ready)}.", code="offer.not_approved"
        )
    comps, terms = components_of(db, ids), terms_of(db, ids)
    anchor = wedding_anchor(wedding)
    built = [(s, scenario_for(db, wedding, s)) for s in data["scenarios"]]
    out = []
    for o in offers:
        vendor = db.get_one(Vendor, o.vendor_id)
        per: list[dict[str, Any]] = []
        for raw, sc in built:
            q = pricing.quote(priced_components(comps[o.id]), o.min_guests, sc)
            plan, final, plan_warnings = payment_plan(terms[o.id], q.total, anchor)
            per.append(
                {
                    "label": raw["label"],
                    "scenario": sc,
                    "quote": q,
                    "payments": plan,
                    "final_payment": final,
                    "warnings": [*q.warnings, *plan_warnings],
                }
            )
        base = per[0]
        for p in per:
            p["difference_to_first"] = p["quote"].total - base["quote"].total
            p["final_difference_to_first"] = p["final_payment"] - base["final_payment"]
        out.append({"offer": o, "vendor": vendor, "per_scenario": per})
    return out


def _create_payments(
    db: Session, wedding: Wedding, item: BudgetItem, terms: list[OfferTerm], warnings: list[str]
) -> int:
    rows = payment_rows(terms, wedding_anchor(wedding), warnings)
    for r in rows:
        db.add(
            Payment(
                wedding_id=wedding.id,
                budget_item_id=item.id,
                kind=r["kind"],
                amount=r["amount"],
                due_date=r["due_date"],
                status="scheduled",
                source="offer",
                notes="Utworzono z warunków oferty: sprawdź z umową.",
            )
        )
    return len(rows)
