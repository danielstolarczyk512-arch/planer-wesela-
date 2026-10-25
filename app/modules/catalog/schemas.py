# ruff: noqa: RUF001
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.modules.catalog.models import CatalogVendor, PublicPackage, VendorFact
from app.modules.catalog.service import VendorCard, freshness

Freshness = Literal["fresh", "stale", "unknown"]


class PackageOut(BaseModel):
    id: UUID
    kind: Literal["package", "surcharge"]
    name: str
    price_from: Decimal | None
    price_to: Decimal | None
    currency: str
    unit: str
    price_label: str
    # Brak sezonu jest jawny: cena publiczna nie jest wyceną na datę wesela.
    season: str | None
    season_known: bool
    evidence: str
    source_url: str | None
    observed_at: datetime
    fresh: bool
    conflict: bool
    note: str

    @field_serializer("price_from", "price_to")
    def _money(self, v: Decimal | None) -> str | None:
        return None if v is None else f"{v:.2f}"


class SourceOut(BaseModel):
    url: str
    observed_at: datetime | None


class CatalogVendorOut(BaseModel):
    id: UUID
    name: str
    category: str
    city: str | None
    service_area: str | None
    website: str | None
    phones: list[str]
    emails: list[str]
    social: list[str]
    packages: list[PackageOut]
    surcharges: list[PackageOut]
    freshness: Freshness
    last_observed_at: datetime | None
    # Rozdzielone stany (pakiet: tożsamość ≠ aktualność ≠ potwierdzenie odpowiedzi ≠ ocena).
    availability: Literal["unconfirmed"] = "unconfirmed"
    price_status: Literal["public_price", "ask_for_quote"]
    sources: list[SourceOut]
    tags: list[str]
    missing: list[str]


class CatalogPage(BaseModel):
    items: list[CatalogVendorOut]
    total: int


_UNIT_LABEL = {
    "unspecified": "",
    "package": " za pakiet",
    "hour": " za godzinę",
    "person": " za osobę",
    "day": " za dzień",
    "event": " za wydarzenie",
    "km": " za km",
}


def _amount(v: Decimal) -> str:
    text = f"{v:,.2f}".replace(",", " ")
    return text.removesuffix(".00")


def price_label(p: PublicPackage) -> str:
    cur = "zł" if p.currency == "PLN" else p.currency
    unit = _UNIT_LABEL.get(p.unit, "")
    if p.price_from is None:
        return "zapytaj o wycenę"
    if p.price_to is None:
        return f"od {_amount(p.price_from)} {cur}{unit}"
    if p.price_to == p.price_from:
        return f"{_amount(p.price_from)} {cur}{unit}"
    return f"{_amount(p.price_from)}–{_amount(p.price_to)} {cur}{unit}"


def _first(facts: list[VendorFact], field: str) -> str | None:
    return next((f.value for f in facts if f.field == field), None)


def to_out(card: VendorCard, now: datetime) -> CatalogVendorOut:
    v: CatalogVendor = card.vendor
    source_urls = {s.id: s.url for s in card.sources}

    def pkg(p: PublicPackage) -> PackageOut:
        note = "Cena publiczna z cennika firmy — nie jest wyceną na Wasz termin."
        if p.verification == "conflict":
            note = "Źródła podają różne ceny. Zapytaj firmę o aktualną wycenę."
        if not p.season:
            note += " Sezon w cenniku nie jest podany."
        return PackageOut(
            id=p.id,
            kind=p.kind,
            name=p.name,
            price_from=p.price_from,
            price_to=p.price_to,
            currency=p.currency,
            unit=p.unit,
            price_label=price_label(p),
            season=p.season,
            season_known=p.season is not None,
            evidence=p.evidence,
            source_url=source_urls.get(p.source_id) if p.source_id else None,
            observed_at=p.observed_at,
            fresh=p.valid_until is None or p.valid_until >= now,
            conflict=p.verification == "conflict",
            note=note,
        )

    packages = [pkg(p) for p in card.packages if p.kind == "package"]
    surcharges = [pkg(p) for p in card.packages if p.kind == "surcharge"]
    state, newest = freshness(card, now)
    phones = [f.value for f in card.facts if f.field == "phone"]
    emails = [f.value for f in card.facts if f.field == "email"]
    missing: list[str] = []
    if not packages:
        missing.append("cennik (zapytaj o wycenę)")
    if not any(p.season_known for p in packages) and packages:
        missing.append("sezon, którego dotyczy cennik")
    missing.append("dostępność terminu (niepotwierdzona)")
    return CatalogVendorOut(
        id=v.id,
        name=v.name,
        category=v.category,
        city=v.city,
        service_area=v.service_area or _first(card.facts, "service_area"),
        website=_first(card.facts, "website"),
        phones=list(dict.fromkeys(phones)),
        emails=list(dict.fromkeys(emails)),
        social=list(dict.fromkeys(f.value for f in card.facts if f.field == "social")),
        packages=packages,
        surcharges=surcharges,
        freshness=state,
        last_observed_at=newest,
        price_status="public_price" if packages else "ask_for_quote",
        sources=[SourceOut(url=s.url, observed_at=s.last_success_at) for s in card.sources],
        tags=list(v.tags or []),
        missing=missing,
    )


class AdminVendorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    category: str
    city: str | None
    publication_status: str
    merged_into_id: UUID | None
    created_at: datetime


class StatusBody(BaseModel):
    status: Literal["published", "hidden", "draft", "needs_review"]


class TagsBody(BaseModel):
    tags: list[str] = Field(max_length=12)


class MergeBody(BaseModel):
    into: UUID


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: str
    catalog_vendor_id: UUID | None
    source_id: UUID | None
    summary: str
    details: dict[str, Any]
    state: str
    resolution: str | None
    created_at: datetime


class ResolveBody(BaseModel):
    resolution: str
    confirm_package_id: UUID | None = None
