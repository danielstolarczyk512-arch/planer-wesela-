"""Dobór firm z katalogu: ograniczenia, jawne preferencje, kompletność i aktualność dowodów.

Działa w kodzie, bez modelu. Zwraca uzasadnienie i braki zamiast pozornie precyzyjnej oceny
(np. „97/100”). Zasady z pakietu „agenci weselni”:
- najpierw ograniczenia: kategoria i region; nieznany termin pozostaje nieznany, a nie „wolny”;
- budżet jest warunkiem tylko tam, gdzie zakres i cena są porównywalne; cena „od” to wskazówka;
- styl portfolio opiera się na tagach potwierdzonych przez człowieka, nie na analizie obrazów;
- każde uzasadnienie ma dowód (cytat i źródło) albo jest jawnie oznaczone jako brak informacji.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.modules.catalog.models import PublicPackage
from app.modules.catalog.service import VendorCard, freshness

# Jednostki, w których cena pakietu jest porównywalna z budżetem na całą usługę.
COMPARABLE_UNITS = ("package", "event", "unspecified")


@dataclass(frozen=True)
class WeddingContext:
    city: str | None
    region: str | None
    guest_count: int | None
    date_label: str | None


@dataclass(frozen=True)
class Preferences:
    category: str
    scope_terms: tuple[str, ...] = ()
    style_tags: tuple[str, ...] = ()
    budget_max: Decimal | None = None


@dataclass
class Reason:
    kind: str  # category | region | budget | scope | style | freshness | price
    text: str
    evidence: str | None = None
    source_url: str | None = None


@dataclass
class Match:
    card: VendorCard
    reasons: list[Reason] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    region_fit: str = "unknown"  # match | unknown
    budget_fit: str = "unknown"  # fits | over | unknown
    matched_scope: int = 0
    matched_style: int = 0
    completeness: int = 0
    fresh: bool = False
    rank: tuple[Any, ...] = ()


def _norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _packages(card: VendorCard) -> list[PublicPackage]:
    return [p for p in card.packages if p.kind == "package"]


def _source_url(card: VendorCard, package: PublicPackage) -> str | None:
    for s in card.sources:
        if s.id == package.source_id:
            return s.url
    return None


def _region(match: Match, ctx: WeddingContext) -> None:
    v = match.card.vendor
    city = _norm(ctx.city)
    area = (
        _norm(v.service_area)
        + " "
        + _norm(next((f.value for f in match.card.facts if f.field == "service_area"), None))
    )
    if not city:
        match.missing.append("miejscowość wesela (uzupełnij w ustawieniach, by ocenić dojazd)")
        return
    if _norm(v.city) == city or city in area:
        match.region_fit = "match"
        where = v.city if _norm(v.city) == city else (v.service_area or "obszar działania")
        match.reasons.append(Reason("region", f"Działa w okolicy wesela ({where})."))
        return
    if ctx.region and _norm(ctx.region) in area:
        match.region_fit = "match"
        match.reasons.append(Reason("region", f"Obsługuje region wesela ({ctx.region})."))
        return
    if v.city or v.service_area:
        match.flags.append(
            f"dojazd do {ctx.city} do potwierdzenia (firma: {v.city or v.service_area})"
        )
    else:
        match.missing.append("obszar dojazdu")


def _budget(match: Match, prefs: Preferences) -> None:
    if prefs.budget_max is None:
        return
    comparable = [
        p for p in _packages(match.card) if p.unit in COMPARABLE_UNITS and p.price_from is not None
    ]
    if not comparable:
        match.missing.append("cena porównywalna z budżetem (cennik w innej jednostce lub brak)")
        return
    cheapest = min(comparable, key=lambda p: p.price_from or Decimal(0))
    price = cheapest.price_from or Decimal(0)
    exact = cheapest.price_to == cheapest.price_from
    label = f"{price:,.0f}".replace(",", " ")
    ev = cheapest.evidence
    src = _source_url(match.card, cheapest)
    if price <= prefs.budget_max:
        match.budget_fit = "fits"
        hint = "" if exact else " (cena „od” — to wskazówka, nie wycena)"
        match.reasons.append(
            Reason(
                "budget",
                f"Najtańszy pakiet „{cheapest.name}” od {label} zł mieści się w budżecie{hint}.",
                ev,
                src,
            )
        )
    else:
        match.budget_fit = "over"
        match.flags.append(f"najtańszy pakiet „{cheapest.name}” ({label} zł) przekracza budżet")


def _terms(match: Match, prefs: Preferences) -> None:
    corpus = [(p, _norm(f"{p.name} {p.evidence} {p.scope or ''}")) for p in match.card.packages]
    for term in prefs.scope_terms:
        t = _norm(term)
        hit = next(((p, text) for p, text in corpus if t and t in text), None)
        if hit:
            match.matched_scope += 1
            match.reasons.append(
                Reason(
                    "scope",
                    f"W cenniku jest „{term}”.",
                    hit[0].evidence,
                    _source_url(match.card, hit[0]),
                )
            )
        else:
            match.missing.append(f"czy zakres obejmuje „{term}” (brak informacji na stronie)")
    tags = {_norm(t) for t in getattr(match.card.vendor, "tags", None) or []}
    for tag in prefs.style_tags:
        if _norm(tag) in tags:
            match.matched_style += 1
            match.reasons.append(Reason("style", f"Styl „{tag}” potwierdzony w katalogu."))
        else:
            match.missing.append(f"styl „{tag}” (brak potwierdzonego opisu)")


def _completeness(match: Match, now: datetime) -> None:
    card = match.card
    pkgs = _packages(card)
    score = 0
    if pkgs:
        score += 1
    else:
        match.missing.append("cennik (zapytaj o wycenę)")
    if pkgs and any(p.season for p in pkgs):
        score += 1
    elif pkgs:
        match.missing.append("sezon, którego dotyczy cennik")
    if any(f.field in ("phone", "email") for f in card.facts):
        score += 1
    state, _newest = freshness(card, now)
    match.fresh = state == "fresh"
    if state == "stale":
        match.flags.append("dane mogą być nieaktualne (minął okres ważności odczytu)")
    if any(p.verification == "conflict" for p in card.packages):
        match.flags.append("źródła podają różne ceny — zapytaj o wycenę")
    match.completeness = score
    match.missing.append("dostępność terminu (niepotwierdzona)")


def match_vendors(
    cards: list[VendorCard],
    ctx: WeddingContext,
    prefs: Preferences,
    now: datetime,
    *,
    excluded_ids: frozenset[Any] = frozenset(),
) -> list[Match]:
    """Zwraca dopasowania od najlepszego. Odrzuceni (`excluded_ids`) nie są pokazywani."""
    results: list[Match] = []
    for card in cards:
        v = card.vendor
        if v.category != prefs.category or v.id in excluded_ids:
            continue
        m = Match(card=card)
        m.reasons.append(Reason("category", f"Kategoria: {v.category}."))
        _region(m, ctx)
        _budget(m, prefs)
        _terms(m, prefs)
        _completeness(m, now)
        m.rank = (
            m.budget_fit == "over",  # poza budżetem na dół, ale nie znika
            m.region_fit != "match",
            -m.matched_scope,
            -m.matched_style,
            -m.completeness,
            not m.fresh,
            _norm(v.name),
        )
        results.append(m)
    results.sort(key=lambda m: m.rank)
    return results
