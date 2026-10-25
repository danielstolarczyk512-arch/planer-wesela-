"""Zapis wyniku ekstrakcji do katalogu: firma, fakty, pakiety, konflikty, publikacja.

Zasady (pakiet „agenci weselni”, ADR-0008):
- fakt ma dowód i datę; zmiana wartości zamyka stary rekord (historia), identyczna wartość tylko
  odświeża datę — powtórne pobranie nie mnoży rekordów;
- dwie firmy łączymy tylko po mocnych przesłankach (telefon, e-mail); sama nazwa, miasto albo
  wspólna domena nie wystarczają — wtedy powstaje osobna firma i wpis w kolejce weryfikacji;
- sprzeczne ceny z dwóch źródeł nie są cicho nadpisywane: oba pakiety dostają status `conflict`;
- brak danych (ceny, sezonu) pozostaje brakiem.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.catalog.models import (
    CatalogVendor,
    PublicPackage,
    ReviewItem,
    SourceObservation,
    VendorFact,
    VendorSource,
)
from app.modules.discovery.extract import Extracted, ExtractedPackage
from app.modules.vendors.service import normalize_phone

SINGLE_VALUED = ("name", "city", "service_area")
MULTI_VALUED = ("phone", "email", "social", "website")
CONTACT_VALID_DAYS = 30


@dataclass
class IngestStats:
    vendor_id: UUID
    facts_new: int = 0
    facts_refreshed: int = 0
    facts_closed: int = 0
    packages_new: int = 0
    packages_refreshed: int = 0
    packages_superseded: int = 0
    conflicts: int = 0


def _same_value(field: str, a: str, b: str) -> bool:
    if field == "phone":
        return normalize_phone(a) == normalize_phone(b)
    return a.strip().lower() == b.strip().lower()


def open_review(
    db: Session,
    *,
    kind: str,
    summary: str,
    dedupe_key: str,
    vendor_id: UUID | None = None,
    source_id: UUID | None = None,
    details: dict[str, Any] | None = None,
) -> ReviewItem | None:
    """Otwarty wpis o tym samym kluczu istnieje tylko raz (nie mnożymy powiadomień)."""
    existing = db.scalar(
        select(ReviewItem).where(ReviewItem.dedupe_key == dedupe_key, ReviewItem.state == "open")
    )
    if existing is not None:
        existing.summary, existing.details = summary[:400], details or {}
        return None
    item = ReviewItem(
        kind=kind,
        summary=summary[:400],
        dedupe_key=dedupe_key,
        catalog_vendor_id=vendor_id,
        source_id=source_id,
        details=details or {},
    )
    db.add(item)
    return item


def close_review(db: Session, dedupe_key: str, resolution: str) -> None:
    from app.core.db import utcnow

    for item in db.scalars(
        select(ReviewItem).where(ReviewItem.dedupe_key == dedupe_key, ReviewItem.state == "open")
    ):
        item.state, item.resolution, item.resolved_at = "resolved", resolution[:300], utcnow()


def vendor_group(db: Session, vendor_id: UUID) -> list[UUID]:
    """Firma i firmy scalone do niej (scalenie odwracalne: dane zostają przy swoich firmach)."""
    children = db.scalars(
        select(CatalogVendor.id).where(CatalogVendor.merged_into_id == vendor_id)
    ).all()
    return [vendor_id, *children]


def _strong_matches(db: Session, ex: Extracted) -> list[UUID]:
    """Firmy mające ten sam telefon albo e-mail (mocne przesłanki tożsamości)."""
    phones = {normalize_phone(v) for v in ex.values("phone")} - {None}
    emails = {v.lower() for v in ex.values("email")}
    if not phones and not emails:
        return []
    found: set[UUID] = set()
    rows = db.execute(
        select(VendorFact.catalog_vendor_id, VendorFact.field, VendorFact.value)
        .join(CatalogVendor, CatalogVendor.id == VendorFact.catalog_vendor_id)
        .where(
            VendorFact.is_current.is_(True),
            VendorFact.field.in_(("phone", "email")),
            CatalogVendor.merged_into_id.is_(None),
        )
    ).all()
    for vendor_id, field, value in rows:
        if (field == "email" and value.lower() in emails) or (
            field == "phone" and normalize_phone(value) in phones
        ):
            found.add(vendor_id)
    return sorted(found)


def resolve_vendor(db: Session, source: VendorSource, ex: Extracted) -> CatalogVendor:
    if source.catalog_vendor_id is not None:
        return db.get_one(CatalogVendor, source.catalog_vendor_id)
    matches = _strong_matches(db, ex)
    if len(matches) == 1:
        vendor = db.get_one(CatalogVendor, matches[0])
        source.catalog_vendor_id = vendor.id
        return vendor
    name = (ex.name or source.domain)[:200]
    city = next(iter(ex.values("city")), None) or source.region_hint
    vendor = CatalogVendor(
        name=name, category=source.category, city=city, publication_status="draft"
    )
    db.add(vendor)
    db.flush()
    source.catalog_vendor_id = vendor.id
    candidates: list[UUID] = list(matches)
    same_domain = db.scalars(
        select(VendorSource.catalog_vendor_id).where(
            VendorSource.domain == source.domain,
            VendorSource.id != source.id,
            VendorSource.catalog_vendor_id.is_not(None),
        )
    ).all()
    candidates += [c for c in same_domain if c is not None and c not in candidates]
    if candidates:
        vendor.publication_status = "needs_review"
        open_review(
            db,
            kind="ambiguous_merge",
            summary=f"Czy „{name}” to ta sama firma co istniejące? Nie scalono.",
            dedupe_key=f"merge:{vendor.id}",
            vendor_id=vendor.id,
            source_id=source.id,
            details={
                "candidates": [str(c) for c in candidates],
                "reason": "telefon/e-mail lub domena",
            },
        )
    return vendor


def _upsert_fact(
    db: Session,
    vendor: CatalogVendor,
    source: VendorSource,
    obs: SourceObservation,
    field: str,
    value: str,
    evidence: str,
    now: datetime,
    stats: IngestStats,
) -> None:
    valid = now + timedelta(days=CONTACT_VALID_DAYS)
    current = db.scalars(
        select(VendorFact).where(
            VendorFact.catalog_vendor_id == vendor.id,
            VendorFact.source_id == source.id,
            VendorFact.field == field,
            VendorFact.is_current.is_(True),
        )
    ).all()
    for fact in current:
        if _same_value(field, fact.value, value):
            fact.observed_at, fact.valid_until, fact.observation_id = now, valid, obs.id
            stats.facts_refreshed += 1
            return
    if field in SINGLE_VALUED:
        for fact in current:
            fact.is_current, fact.superseded_at = False, now
            stats.facts_closed += 1
    db.add(
        VendorFact(
            catalog_vendor_id=vendor.id,
            source_id=source.id,
            observation_id=obs.id,
            field=field,
            value=value,
            evidence=evidence[:600],
            observed_at=now,
            valid_until=valid,
        )
    )
    stats.facts_new += 1


def _close_missing_contacts(
    db: Session,
    vendor: CatalogVendor,
    source: VendorSource,
    ex: Extracted,
    now: datetime,
    stats: IngestStats,
) -> None:
    """Kontakt, którego strona już nie podaje, przestaje być aktualny — o ile strona podaje inny."""
    for field in ("phone", "email", "social"):
        seen = ex.values(field)
        if not seen:
            continue  # brak odczytu nie jest dowodem, że kontakt zniknął
        for fact in db.scalars(
            select(VendorFact).where(
                VendorFact.catalog_vendor_id == vendor.id,
                VendorFact.source_id == source.id,
                VendorFact.field == field,
                VendorFact.is_current.is_(True),
            )
        ):
            if not any(_same_value(field, fact.value, s) for s in seen):
                fact.is_current, fact.superseded_at = False, now
                stats.facts_closed += 1


def _price_tuple(p: PublicPackage | ExtractedPackage) -> tuple[Any, Any, str]:
    return (p.price_from, p.price_to, p.currency)


def _upsert_packages(
    db: Session,
    vendor: CatalogVendor,
    source: VendorSource,
    obs: SourceObservation,
    ex: Extracted,
    now: datetime,
    stats: IngestStats,
) -> None:
    valid = now + timedelta(days=get_settings().discovery_price_refresh_days)
    current = {
        p.key: p
        for p in db.scalars(
            select(PublicPackage).where(
                PublicPackage.catalog_vendor_id == vendor.id,
                PublicPackage.source_id == source.id,
                PublicPackage.is_current.is_(True),
            )
        )
    }
    seen: set[str] = set()
    for pkg in ex.packages:
        seen.add(pkg.key)
        old = current.get(pkg.key)
        if old is not None and _price_tuple(old) == _price_tuple(pkg):
            old.observed_at, old.valid_until, old.observation_id = now, valid, obs.id
            old.evidence = pkg.evidence
            stats.packages_refreshed += 1
            continue
        if old is not None:
            old.is_current, old.superseded_at, old.supersede_reason = False, now, "price_changed"
            stats.packages_superseded += 1
        db.add(
            PublicPackage(
                catalog_vendor_id=vendor.id,
                source_id=source.id,
                observation_id=obs.id,
                key=pkg.key[:200],
                kind=pkg.kind,
                name=pkg.name,
                price_from=pkg.price_from,
                price_to=pkg.price_to,
                currency=pkg.currency,
                unit=pkg.unit,
                season=pkg.season,
                evidence=pkg.evidence,
                observed_at=now,
                valid_until=valid,
            )
        )
        stats.packages_new += 1
    if ex.packages:
        # Pakiet zniknął ze strony, która nadal podaje inne ceny: wycofujemy go z zachowaniem
        # historii. Strona bez żadnej ceny (np. zmiana układu) niczego nie wycofuje.
        for key, old in current.items():
            if key not in seen:
                old.is_current, old.superseded_at, old.supersede_reason = False, now, "withdrawn"
                stats.packages_superseded += 1


def detect_conflicts(db: Session, vendor_id: UUID) -> int:
    """Ten sam pakiet z różnych źródeł o różnych cenach: oba na `conflict` i wpis do weryfikacji."""
    ids = vendor_group(db, vendor_id)
    rows = db.scalars(
        select(PublicPackage).where(
            PublicPackage.catalog_vendor_id.in_(ids), PublicPackage.is_current.is_(True)
        )
    ).all()
    by_key: dict[str, list[PublicPackage]] = {}
    for p in rows:
        by_key.setdefault(p.key, []).append(p)
    conflicts = 0
    for key, items in by_key.items():
        sources = {p.source_id for p in items}
        dedupe = f"conflict:{vendor_id}:{key}"[:200]
        clashing = len(sources) > 1 and len({_price_tuple(p) for p in items}) > 1
        for p in items:
            if p.verification == "confirmed":
                continue
            p.verification = "conflict" if clashing else "auto"
        if clashing:
            conflicts += 1
            open_review(
                db,
                kind="conflict",
                summary=f"Sprzeczne ceny pakietu „{items[0].name}” w różnych źródłach.",
                dedupe_key=dedupe,
                vendor_id=vendor_id,
                details={
                    "package_ids": [str(p.id) for p in items],
                    "prices": [
                        {
                            "from": str(p.price_from) if p.price_from is not None else None,
                            "to": str(p.price_to) if p.price_to is not None else None,
                            "source_id": str(p.source_id),
                        }
                        for p in items
                    ],
                },
            )
        else:
            close_review(db, dedupe, "Dane zgodne po ponownym pobraniu.")
    return conflicts


def evaluate_publication(db: Session, vendor: CatalogVendor) -> None:
    """Publikacja automatyczna tylko dla rozpoznanej, udokumentowanej firmy."""
    if vendor.publication_status == "hidden" or vendor.merged_into_id is not None:
        return
    open_merge = db.scalar(
        select(func.count())
        .select_from(ReviewItem)
        .where(
            ReviewItem.catalog_vendor_id == vendor.id,
            ReviewItem.kind == "ambiguous_merge",
            ReviewItem.state == "open",
        )
    )
    if open_merge:
        vendor.publication_status = "needs_review"
        return
    active_sources = db.scalar(
        select(func.count())
        .select_from(VendorSource)
        .where(VendorSource.catalog_vendor_id == vendor.id, VendorSource.state == "active")
    )
    contacts = db.scalar(
        select(func.count())
        .select_from(VendorFact)
        .where(
            VendorFact.catalog_vendor_id == vendor.id,
            VendorFact.is_current.is_(True),
            VendorFact.field.in_(("phone", "email")),
        )
    )
    structured_name = db.scalar(
        select(func.count())
        .select_from(VendorFact)
        .where(
            VendorFact.catalog_vendor_id == vendor.id,
            VendorFact.is_current.is_(True),
            VendorFact.field == "name",
            VendorFact.evidence.like("JSON-LD%"),
        )
    )
    documented = bool(vendor.name) and (bool(contacts) or bool(structured_name))
    if documented and active_sources:
        vendor.publication_status = "published"
        close_review(db, f"weak:{vendor.id}", "Firma ma wystarczające dowody.")
    elif vendor.publication_status != "needs_review":
        vendor.publication_status = "draft"
        if active_sources:
            open_review(
                db,
                kind="weak_evidence",
                summary=f"„{vendor.name}”: za mało danych, by opublikować (brak telefonu/e-maila).",
                dedupe_key=f"weak:{vendor.id}",
                vendor_id=vendor.id,
            )


def refresh_unchanged(db: Session, source: VendorSource, now: datetime) -> None:
    """Strona bez zmian: potwierdzamy aktualność istniejących danych bez tworzenia nowych."""
    if source.catalog_vendor_id is None:
        return
    price_valid = now + timedelta(days=get_settings().discovery_price_refresh_days)
    contact_valid = now + timedelta(days=CONTACT_VALID_DAYS)
    db.execute(
        update(PublicPackage)
        .where(PublicPackage.source_id == source.id, PublicPackage.is_current.is_(True))
        .values(observed_at=now, valid_until=price_valid)
    )
    db.execute(
        update(VendorFact)
        .where(VendorFact.source_id == source.id, VendorFact.is_current.is_(True))
        .values(observed_at=now, valid_until=contact_valid)
    )


def withdraw_source(db: Session, source: VendorSource, reason: str, now: datetime) -> None:
    """Źródło wycofane (404/410): dane przestają być aktualne, historia zostaje."""
    db.execute(
        update(PublicPackage)
        .where(PublicPackage.source_id == source.id, PublicPackage.is_current.is_(True))
        .values(is_current=False, superseded_at=now, supersede_reason=reason[:24])
    )
    db.execute(
        update(VendorFact)
        .where(VendorFact.source_id == source.id, VendorFact.is_current.is_(True))
        .values(is_current=False, superseded_at=now)
    )
    if source.catalog_vendor_id is not None:
        vendor = db.get(CatalogVendor, source.catalog_vendor_id)
        if vendor is not None:
            db.flush()
            detect_conflicts(db, vendor.id)
            evaluate_publication(db, vendor)


def ingest(
    db: Session, source: VendorSource, obs: SourceObservation, ex: Extracted, now: datetime
) -> IngestStats:
    vendor = resolve_vendor(db, source, ex)
    stats = IngestStats(vendor_id=vendor.id)
    for fact in ex.facts:
        _upsert_fact(db, vendor, source, obs, fact.field, fact.value, fact.evidence, now, stats)
    _close_missing_contacts(db, vendor, source, ex, now, stats)
    db.flush()
    _upsert_packages(db, vendor, source, obs, ex, now, stats)
    db.flush()
    stats.conflicts = detect_conflicts(db, vendor.id)
    evaluate_publication(db, vendor)
    return stats
