"""Dobór usługodawców: preferencje, wyszukiwanie w katalogu, kandydaci, prośby o research.

Każda funkcja dostaje `wedding_id` z autoryzowanego kontekstu i sprawdza rolę (`authorize`).
Katalog jest wspólny i publiczny, wszystko inne (preferencje, kandydaci, zlecenia) jest prywatne
dla wesela.
"""

from datetime import timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.db import utcnow
from app.core.errors import Conflict, NotFound, PreconditionRequired, RateLimited, Unprocessable
from app.jobs.queue import enqueue
from app.modules.audit import service as audit
from app.modules.catalog import service as catalog
from app.modules.catalog.models import CatalogVendor, VendorSource
from app.modules.concierge.matching import Match, Preferences, WeddingContext, match_vendors
from app.modules.concierge.models import Candidate, DiscoveryRequest, VendorPreferences
from app.modules.discovery import service as discovery
from app.modules.identity.service import Principal
from app.modules.vendors import service as vendors
from app.modules.vendors.models import CATEGORIES
from app.modules.workspace.models import Wedding
from app.modules.workspace.permissions import Action, authorize

log = structlog.get_logger()

MAX_REQUESTS_PER_DAY = 5
MAX_SOURCES_PER_REQUEST = 10
SEARCH_POOL = 300


def _commit(db: Session) -> None:
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise Conflict(
            "Dane zmieniły się w międzyczasie. Pobierz aktualną wersję.",
            code="conflict.version_mismatch",
        ) from exc


def check_category(category: str) -> None:
    if category not in CATEGORIES:
        raise Unprocessable("Nieznana kategoria.", code="concierge.bad_category")


# --- kontekst wesela (tylko to, co potrzebne do doboru) -------------------------------------


def wedding_context(db: Session, wedding_id: UUID) -> WeddingContext:
    """Termin, miejscowość i liczba gości. Bez listy gości, diet, dokumentów i harmonogramu."""
    w = db.get(Wedding, wedding_id)
    if w is None:
        raise NotFound("Nie znaleziono wesela.", code="wedding.not_found")
    label = None
    if w.wedding_date:
        label = w.wedding_date.isoformat()
    elif w.planned_month:
        label = w.planned_month.strftime("%Y-%m")
    return WeddingContext(
        city=w.city, region=w.region, guest_count=w.guest_count_planned, date_label=label
    )


# --- preferencje ----------------------------------------------------------------------------


def get_preferences(
    db: Session, principal: Principal, wedding_id: UUID, category: str
) -> VendorPreferences | None:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    check_category(category)
    return db.get(VendorPreferences, (wedding_id, category))


def put_preferences(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    category: str,
    data: dict[str, Any],
    expected_version: int | None,
) -> VendorPreferences:
    """Tworzy albo zmienia preferencje. Zmiana istniejących wymaga wersji (If-Match)."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    check_category(category)
    prefs = db.get(VendorPreferences, (wedding_id, category))
    if prefs is None:
        prefs = VendorPreferences(wedding_id=wedding_id, category=category)
        db.add(prefs)
    else:
        if expected_version is None:
            raise PreconditionRequired()
        if prefs.version != expected_version:
            raise Conflict(
                "Preferencje zmieniły się w międzyczasie. Pobierz aktualną wersję.",
                code="conflict.version_mismatch",
            )
    prefs.scope_terms = _clean(data.get("scope_terms", prefs.scope_terms or []), 8, 60)
    prefs.style_tags = _clean(data.get("style_tags", prefs.style_tags or []), 8, 40)
    if "budget_max" in data:
        prefs.budget_max = data["budget_max"]
    if "notes" in data:
        prefs.notes = (data["notes"] or None) and data["notes"][:1000]
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="vendor_preferences",
        entity_id=None,
        wedding_id=wedding_id,
        action="put",
        changes={"category": category},
    )
    _commit(db)
    return prefs


def _clean(values: list[str], limit: int, width: int) -> list[str]:
    return list(dict.fromkeys(v.strip()[:width] for v in values if v and v.strip()))[:limit]


def preferences_for(db: Session, wedding_id: UUID, category: str) -> Preferences:
    row = db.get(VendorPreferences, (wedding_id, category))
    if row is None:
        return Preferences(category=category)
    return Preferences(
        category=category,
        scope_terms=tuple(row.scope_terms or ()),
        style_tags=tuple(row.style_tags or ()),
        budget_max=row.budget_max,
    )


# --- wyszukiwanie ---------------------------------------------------------------------------


def rejected_ids(db: Session, wedding_id: UUID) -> frozenset[UUID]:
    return frozenset(
        db.scalars(
            select(Candidate.catalog_vendor_id).where(
                Candidate.wedding_id == wedding_id, Candidate.state == "rejected"
            )
        )
    )


def search(
    db: Session,
    wedding_id: UUID,
    category: str,
    *,
    limit: int = 5,
    prefs: Preferences | None = None,
) -> list[Match]:
    """Dobór z katalogu dla wesela (wywołanie wewnętrzne — autoryzację robi wywołujący)."""
    check_category(category)
    cards, _total = catalog.list_published(
        db, category=category, city=None, q=None, limit=catalog.MAX_PAGE, offset=0
    )
    pool = list(cards)
    offset = len(pool)
    while len(pool) < SEARCH_POOL and offset < _total:
        more, _ = catalog.list_published(
            db, category=category, city=None, q=None, limit=catalog.MAX_PAGE, offset=offset
        )
        if not more:
            break
        pool.extend(more)
        offset += len(more)
    matches = match_vendors(
        pool,
        wedding_context(db, wedding_id),
        prefs or preferences_for(db, wedding_id, category),
        utcnow(),
        excluded_ids=rejected_ids(db, wedding_id),
    )
    return matches[: max(1, min(limit, 20))]


def search_for(
    db: Session, principal: Principal, wedding_id: UUID, category: str, limit: int
) -> list[Match]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return search(db, wedding_id, category, limit=limit)


def reasoning_of(match: Match) -> dict[str, Any]:
    return {
        "reasons": [
            {"kind": r.kind, "text": r.text, "evidence": r.evidence, "source_url": r.source_url}
            for r in match.reasons
        ],
        "missing": list(dict.fromkeys(match.missing)),
        "flags": list(match.flags),
        "saved_at": utcnow().isoformat(),
    }


# --- kandydaci ------------------------------------------------------------------------------


def save_candidate(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    catalog_vendor_id: UUID,
    note: str | None,
) -> Candidate:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    card = catalog.get_published(db, catalog_vendor_id)
    category = card.vendor.category
    match = next(
        iter(
            match_vendors(
                [card],
                wedding_context(db, wedding_id),
                preferences_for(db, wedding_id, category),
                utcnow(),
            )
        )
    )
    cand = db.scalar(
        select(Candidate).where(
            Candidate.wedding_id == wedding_id, Candidate.catalog_vendor_id == catalog_vendor_id
        )
    )
    if cand is None:
        cand = Candidate(
            wedding_id=wedding_id,
            catalog_vendor_id=catalog_vendor_id,
            category=category,
            created_by=principal.user.id,
        )
        db.add(cand)
    cand.state = "saved"
    cand.note = (note or "")[:500] or cand.note
    cand.reasoning = reasoning_of(match)
    db.flush()
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="candidate",
        entity_id=cand.id,
        wedding_id=wedding_id,
        action="save",
    )
    db.commit()
    return cand


def list_candidates(
    db: Session, principal: Principal, wedding_id: UUID, state: str | None = "saved"
) -> list[tuple[Candidate, CatalogVendor]]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    query = (
        select(Candidate, CatalogVendor)
        .join(CatalogVendor, CatalogVendor.id == Candidate.catalog_vendor_id)
        .where(Candidate.wedding_id == wedding_id)
        .order_by(Candidate.created_at)
    )
    if state:
        query = query.where(Candidate.state == state)
    return [(c, v) for c, v in db.execute(query).all()]


def _candidate(db: Session, wedding_id: UUID, candidate_id: UUID) -> Candidate:
    cand = db.get(Candidate, candidate_id)
    if cand is None or cand.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono kandydata.", code="concierge.candidate_not_found")
    return cand


def set_candidate_state(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    candidate_id: UUID,
    state: str,
    note: str | None,
) -> Candidate:
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    cand = _candidate(db, wedding_id, candidate_id)
    cand.state = state
    if note is not None:
        cand.note = note[:500] or None
    db.commit()
    return cand


def compare(
    db: Session, principal: Principal, wedding_id: UUID, catalog_vendor_ids: list[UUID]
) -> list[Match]:
    """Porównanie kilku firm: te same kryteria, te same braki, bez rankingu punktowego."""
    authorize(db, principal.user.id, wedding_id, Action.READ)
    if not 2 <= len(catalog_vendor_ids) <= 4:
        raise Unprocessable("Porównaj od 2 do 4 firm.", code="concierge.compare_count")
    cards = [catalog.get_published(db, vid) for vid in dict.fromkeys(catalog_vendor_ids)]
    if len({c.vendor.category for c in cards}) > 1:
        raise Unprocessable("Porównuj firmy z jednej kategorii.", code="concierge.compare_mixed")
    category = cards[0].vendor.category
    return match_vendors(
        cards,
        wedding_context(db, wedding_id),
        preferences_for(db, wedding_id, category),
        utcnow(),
    )


def candidate_to_vendor(
    db: Session, principal: Principal, wedding_id: UUID, candidate_id: UUID
) -> Candidate:
    """Prywatna kopia firmy w „Moich usługodawcach” z jawnym powiązaniem do katalogu."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    cand = _candidate(db, wedding_id, candidate_id)
    if cand.vendor_id is not None:
        raise Conflict("Ta firma jest już w Waszych usługodawcach.", code="concierge.already_added")
    card = catalog.get_published(db, cand.catalog_vendor_id)
    first = {
        f: next((x.value for x in card.facts if x.field == f), None)
        for f in ("phone", "email", "website")
    }
    vendor = vendors.create_vendor(
        db,
        principal,
        wedding_id,
        {
            "name": card.vendor.name,
            "category": card.vendor.category,
            "city": card.vendor.city,
            "phone": first["phone"],
            "email": first["email"],
            "website_url": first["website"],
            "status": "considering",
        },
    )
    vendor.catalog_vendor_id = card.vendor.id
    cand.vendor_id = vendor.id
    db.commit()
    return cand


# --- prośba o dodatkowy research ------------------------------------------------------------


def request_discovery(
    db: Session,
    principal: Principal,
    wedding_id: UUID,
    category: str,
    region: str | None,
) -> DiscoveryRequest:
    """Zlecenie badaczowi. Do kolejki trafia tylko id zlecenia (kategoria i region są w tabeli)."""
    authorize(db, principal.user.id, wedding_id, Action.WRITE)
    check_category(category)
    since = utcnow() - timedelta(days=1)
    used = db.scalar(
        select(func.count())
        .select_from(DiscoveryRequest)
        .where(DiscoveryRequest.wedding_id == wedding_id, DiscoveryRequest.created_at > since)
    )
    if (used or 0) >= MAX_REQUESTS_PER_DAY:
        raise RateLimited(3600)
    if region is None:
        region = wedding_context(db, wedding_id).region or wedding_context(db, wedding_id).city
    req = DiscoveryRequest(
        wedding_id=wedding_id,
        requested_by=principal.user.id,
        category=category,
        region=(region or None) and region[:120],
    )
    db.add(req)
    db.flush()
    enqueue(db, discovery.REQUEST_JOB, {"request_id": str(req.id)}, max_attempts=2)
    audit.record(
        db,
        actor_type="user",
        actor_id=principal.user.id,
        entity_type="discovery_request",
        entity_id=req.id,
        wedding_id=wedding_id,
        action="create",
        changes={"category": category},
    )
    db.commit()
    return req


def get_request(
    db: Session, principal: Principal, wedding_id: UUID, request_id: UUID
) -> DiscoveryRequest:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    req = db.get(DiscoveryRequest, request_id)
    if req is None or req.wedding_id != wedding_id:
        raise NotFound("Nie znaleziono zlecenia.", code="concierge.request_not_found")
    return req


def list_requests(db: Session, principal: Principal, wedding_id: UUID) -> list[DiscoveryRequest]:
    authorize(db, principal.user.id, wedding_id, Action.READ)
    return list(
        db.scalars(
            select(DiscoveryRequest)
            .where(DiscoveryRequest.wedding_id == wedding_id)
            .order_by(DiscoveryRequest.created_at.desc())
            .limit(20)
        )
    )


def run_discovery_request(db: Session, payload: dict[str, Any]) -> None:
    """Zadanie badacza: odświeża znane źródła z kategorii i regionu. Nie wymyśla wyników."""
    req = db.get(DiscoveryRequest, UUID(payload["request_id"]))
    if req is None or req.state not in ("queued", "running"):
        return
    req.state = "running"
    db.flush()
    query = select(VendorSource).where(
        VendorSource.category == req.category, VendorSource.state == "active"
    )
    sources = list(db.scalars(query.order_by(VendorSource.last_success_at.nulls_first())))
    region = (req.region or "").strip().lower()
    scoped = [
        s
        for s in sources
        if not region
        or not s.region_hint
        or region in s.region_hint.lower()
        or s.region_hint.lower() in region
    ]
    chosen = scoped[:MAX_SOURCES_PER_REQUEST]
    now = utcnow()
    for source in chosen:
        source.next_check_at = min(source.next_check_at, now)
    # Zadania pobrania planuje scheduler badacza (jedno źródło = jedno zadanie, limity domen).
    caps = discovery.capabilities()
    req.result = {
        "known_sources": len(scoped),
        "refreshed_sources": len(chosen),
        "new_sources_search": caps["search_new_sources"],
        "message": (
            f"Odświeżamy {len(chosen)} znanych źródeł w tej kategorii. "
            "Nowych firm nie wyszukujemy w internecie — brak skonfigurowanego, legalnego źródła."
        ),
    }
    req.state, req.finished_at = "done", now
    db.commit()
    log.info("discovery_request_done", request_id=str(req.id), refreshed=len(chosen))
