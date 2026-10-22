from typing import Any
from uuid import UUID

from fastapi import APIRouter, Response

from app.core.deps import CurrentPrincipal, DbSession, IfMatchVersion, etag
from app.core.schemas import Money
from app.modules.offers import service
from app.modules.offers.models import Offer, OfferTerm, PricingComponent
from app.modules.offers.schemas import (
    ApproveIn,
    CompareIn,
    CompareOut,
    OfferCreate,
    OfferOut,
    OfferStatus,
    OfferUpdate,
    ScenariosIn,
    ScenariosOut,
    SelectIn,
    SelectOut,
)
from app.modules.vendors.models import Vendor
from app.modules.vendors.schemas import VendorCategory

router = APIRouter(tags=["oferty"])

Responses = dict[int | str, dict[str, Any]]
_READ: Responses = {
    401: {"description": "Brak uwierzytelnienia"},
    404: {"description": "Nie znaleziono lub brak dostępu"},
}
_WRITE: Responses = {
    **_READ,
    403: {"description": "Rola tylko do odczytu"},
    409: {"description": "Niedozwolony stan oferty"},
    422: {"description": "Błąd walidacji (np. cytat spoza dokumentu)"},
}
W = "/weddings/{wedding_id}"


def _component(c: PricingComponent) -> dict[str, Any]:
    return {
        "id": c.id,
        "label": c.label,
        "kind": c.kind,
        "amount": c.amount,
        "quantity": c.quantity,
        "included": c.included,
        "optional": c.optional,
        "event_kind": c.event_kind,
        "citation": c.citation,
        "confidence": c.confidence,
    }


def _term(t: OfferTerm) -> dict[str, Any]:
    return {
        **t.value,
        "id": t.id,
        "term_type": t.term_type,
        "citation": t.citation,
        "confidence": t.confidence,
    }


def offers_out(db: DbSession, rows: list[tuple[Offer, Vendor]]) -> list[OfferOut]:
    ids = [o.id for o, _ in rows]
    comps, terms = service.components_of(db, ids), service.terms_of(db, ids)
    return [
        OfferOut.model_validate(
            {
                "id": o.id,
                "vendor_id": v.id,
                "vendor_name": v.name,
                "vendor_category": v.category,
                "title": o.title,
                "valid_until": o.valid_until,
                "min_guests": o.min_guests,
                "notes": o.notes,
                "status": o.status,
                "source": o.source,
                "source_document_version_id": o.source_document_version_id,
                "components": [_component(c) for c in comps[o.id]],
                "terms": [_term(t) for t in terms[o.id]],
                "unverified_fields": service.unverified_count(comps[o.id], terms[o.id]),
                "selected_budget_item_id": o.selected_budget_item_id,
                "version": o.version,
                "updated_at": o.updated_at,
            }
        )
        for o, v in rows
    ]


def _one(db: DbSession, offer: Offer) -> OfferOut:
    return offers_out(db, [(offer, db.get_one(Vendor, offer.vendor_id))])[0]


@router.get(f"{W}/offers", responses=_READ, summary="Oferty (filtry: usługodawca, status)")
def list_offers(
    wedding_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    vendor_id: UUID | None = None,
    status: OfferStatus | None = None,
    category: VendorCategory | None = None,
) -> list[OfferOut]:
    return offers_out(
        db,
        service.list_offers(
            db, principal, wedding_id, vendor_id=vendor_id, status=status, category=category
        ),
    )


@router.post(
    f"{W}/offers",
    status_code=201,
    responses=_WRITE,
    summary="Nowa oferta z komponentami cenowymi i warunkami",
)
def create_offer(
    wedding_id: UUID, body: OfferCreate, principal: CurrentPrincipal, db: DbSession
) -> OfferOut:
    return _one(db, service.create_offer(db, principal, wedding_id, body.model_dump()))


@router.get(f"{W}/offers/{{offer_id}}", responses=_READ, summary="Oferta")
def get_offer(
    wedding_id: UUID, offer_id: UUID, principal: CurrentPrincipal, db: DbSession, response: Response
) -> OfferOut:
    offer, vendor = service.get_offer(db, principal, wedding_id, offer_id)
    response.headers["ETag"] = etag(offer.version)
    return offers_out(db, [(offer, vendor)])[0]


@router.patch(
    f"{W}/offers/{{offer_id}}",
    responses={**_WRITE, 428: {"description": "Brak If-Match"}},
    summary="Edycja oferty (zmiana cen wymaga ponownego zatwierdzenia)",
)
def update_offer(
    wedding_id: UUID,
    offer_id: UUID,
    principal: CurrentPrincipal,
    body: OfferUpdate,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> OfferOut:
    offer = service.update_offer(
        db, principal, wedding_id, offer_id, body.model_dump(exclude_unset=True), version
    )
    response.headers["ETag"] = etag(offer.version)
    return _one(db, offer)


@router.delete(
    f"{W}/offers/{{offer_id}}", status_code=204, responses=_WRITE, summary="Usunięcie oferty"
)
def delete_offer(
    wedding_id: UUID, offer_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.delete_offer(db, principal, wedding_id, offer_id)


@router.post(
    f"{W}/offers/{{offer_id}}/approve",
    responses=_WRITE,
    summary="Zatwierdzenie oferty (wymagane przed porównaniem)",
)
def approve(
    wedding_id: UUID, offer_id: UUID, body: ApproveIn, principal: CurrentPrincipal, db: DbSession
) -> OfferOut:
    return _one(db, service.approve(db, principal, wedding_id, offer_id, body.confirm_unverified))


@router.post(f"{W}/offers/{{offer_id}}/reject", responses=_WRITE, summary="Odrzucenie oferty")
def reject(
    wedding_id: UUID, offer_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> OfferOut:
    return _one(db, service.reject(db, principal, wedding_id, offer_id))


@router.post(
    f"{W}/offers/compare",
    responses=_WRITE,
    summary="Porównanie realnego kosztu całkowitego ofert przy tej samej liczbie gości",
)
def compare(
    wedding_id: UUID, body: CompareIn, principal: CurrentPrincipal, db: DbSession
) -> CompareOut:
    scenario, results = service.compare(db, principal, wedding_id, body.model_dump())
    cheapest = min((r["quote"].total for r in results), default=None)
    out = []
    for r in sorted(results, key=lambda r: r["quote"].total):
        q = r["quote"]
        per_adult = q.per_adult(scenario.adults)
        out.append(
            {
                "offer_id": r["offer"].id,
                "vendor_name": r["vendor"].name,
                "title": r["offer"].title,
                "total": Money(amount=q.total),
                "per_adult_effective": Money(amount=per_adult) if per_adult is not None else None,
                "difference_to_cheapest": Money(amount=q.total - (cheapest or q.total)),
                "lines": [
                    {
                        "label": ln.label,
                        "kind": ln.kind,
                        "amount": ln.amount,
                        "quantity": ln.quantity,
                        "subtotal": Money(amount=ln.subtotal),
                        "note": ln.note,
                    }
                    for ln in q.lines
                ],
                "unknown": q.unknown,
                "optional_excluded": q.optional_excluded,
                "warnings": q.warnings,
                "missing_terms": r["missing_terms"],
            }
        )
    return CompareOut.model_validate(
        {
            "scenario": {
                "adults": scenario.adults,
                "children": scenario.children,
                "after_party_adults": scenario.after_party_adults,
                "after_party_children": scenario.after_party_children,
                "hours": str(scenario.hours) if scenario.hours is not None else None,
                "include_optional": scenario.include_optional,
                "crew": scenario.crew,
                "guest_basis": body.guest_basis,
            },
            "results": out,
            "cheapest_offer_id": out[0]["offer_id"] if out else None,
        }
    )


@router.post(
    f"{W}/offers/scenarios",
    responses=_WRITE,
    summary="„Co jeśli”: koszt i raty tych samych ofert w 2-3 scenariuszach",
)
def offer_scenarios(
    wedding_id: UUID, body: ScenariosIn, principal: CurrentPrincipal, db: DbSession
) -> ScenariosOut:
    results = service.scenarios(db, principal, wedding_id, body.model_dump())
    return ScenariosOut.model_validate(
        {
            "results": [
                {
                    "offer_id": r["offer"].id,
                    "vendor_name": r["vendor"].name,
                    "title": r["offer"].title,
                    "scenarios": [
                        {
                            "label": p["label"],
                            "adults": p["scenario"].adults,
                            "children": p["scenario"].children,
                            "total": Money(amount=p["quote"].total),
                            "difference_to_first": Money(amount=p["difference_to_first"]),
                            "final_payment": Money(amount=p["final_payment"]),
                            "final_difference_to_first": Money(
                                amount=p["final_difference_to_first"]
                            ),
                            "payments": [
                                {**pay, "amount": Money(amount=pay["amount"])}
                                for pay in p["payments"]
                            ],
                            "unknown": p["quote"].unknown,
                            "warnings": p["warnings"],
                        }
                        for p in r["per_scenario"]
                    ],
                }
                for r in results
            ]
        }
    )


@router.post(
    f"{W}/offers/{{offer_id}}/select",
    responses=_WRITE,
    summary="Wybór oferty: pozycja budżetu i płatności z warunków oferty",
)
def select(
    wedding_id: UUID, offer_id: UUID, body: SelectIn, principal: CurrentPrincipal, db: DbSession
) -> SelectOut:
    r = service.select_offer(db, principal, wedding_id, offer_id, body.model_dump())
    return SelectOut.model_validate({**r, "planned_amount": Money(amount=r["planned_amount"])})
