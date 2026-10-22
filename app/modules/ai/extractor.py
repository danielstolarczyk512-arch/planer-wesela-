"""OfferExtractor: tekst dokumentu → szkic oferty. Model tylko proponuje; walidacja decyduje.

Każda liczba z modelu przechodzi deterministyczną kontrolę:
1. cytat ("quote") musi dosłownie występować w tekście dokumentu,
2. kwota ("amount") musi występować w tym cytacie.
Pozycje, które nie przejdą kontroli, nie są odrzucane po cichu, tylko oznaczane jako
`unverified` (bez cytatu). Para musi je świadomie potwierdzić przy zatwierdzaniu oferty.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

COMPONENT_KINDS = {"per_guest", "per_child", "per_crew", "fixed", "per_hour", "per_unit", "percent"}
EVENT_KINDS = {"ceremony", "reception", "after_party"}
TERM_TYPES = {"deposit", "cancellation", "drinks", "corkage", "overtime", "menu", "other"}
MAX_COMPONENTS = 40
MAX_TERMS = 20
MAX_AMOUNT = Decimal("10000000")


@dataclass
class Validated:
    title: str
    min_guests: int | None
    components: list[dict[str, Any]] = field(default_factory=list)
    terms: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, int] = field(
        default_factory=lambda: {
            "components": 0,
            "terms": 0,
            "verified": 0,
            "unverified": 0,
            "dropped": 0,
        }
    )
    suspicious: list[str] = field(default_factory=list)


def build_document(pages: list[str], max_chars: int) -> tuple[str, bool]:
    """Tekst ze znacznikami stron. Zwraca (tekst, czy_obcięto)."""
    parts, total, truncated = [], 0, False
    for i, page in enumerate(pages, start=1):
        chunk = f"[STRONA {i}]\n{page}"
        if total + len(chunk) > max_chars:
            parts.append(chunk[: max(0, max_chars - total)])
            truncated = True
            break
        parts.append(chunk)
        total += len(chunk) + 2
    return "\n\n".join(parts), truncated


NBSP = chr(0xA0)  # twarda spacja (częsta w PDF przy kwotach)
_THOUSANDS = re.compile(r"(?<=\d)[ .\xa0](?=\d{3}(?!\d))")


def norm(text: str) -> str:
    text = text.replace(NBSP, " ").replace("„", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower().rstrip(".,;:")


def numbers_in(text: str) -> set[Decimal]:
    joined = _THOUSANDS.sub("", text)  # 5 000 / 5.000 -> 5000
    found = set()
    for raw in re.findall(r"\d+(?:,\d{1,2})?", joined):
        try:
            found.add(Decimal(raw.replace(",", ".")))
        except InvalidOperation:
            continue
    return found


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        return None
    if d < 0 or d > MAX_AMOUNT or not d.is_finite():
        return None
    return d.quantize(Decimal("0.01"))


def _citation(item: dict[str, Any], doc_norm: str, page_count: int) -> dict[str, Any] | None:
    quote = item.get("quote")
    if not isinstance(quote, str) or not quote.strip() or len(quote) > 500:
        return None
    if norm(quote) not in doc_norm:
        return None
    page = item.get("page")
    return {
        "quote": quote.strip(),
        "page": page if isinstance(page, int) and 1 <= page <= page_count else None,
    }


# Tekst, który wygląda na polecenie dla modelu, a nie treść oferty (prompt injection).
# Cytat z takiego fragmentu „istnieje w dokumencie”, więc sama weryfikacja cytatu nie wystarcza.
_SUSPICIOUS = re.compile(
    r"zignoruj|ignoruj\w* (?:wszystk|poprzedn|wcześniejsz)|instrukcj|polecen\w* system|"
    r"uwaga,? system|\bsystem\s*:|wpisz (?:cen|kwot)|ignore (?:all|previous|the above)|"
    r"disregard|you are now|jesteś teraz|\bprompt\b|asystent\w* ai|model\w* językow",
    re.I,
)


def suspicious_fragments(text: str) -> list[str]:
    """Linie dokumentu wyglądające na wstrzyknięte polecenia (do ostrzeżenia dla pary)."""
    return [line.strip()[:200] for line in text.splitlines() if _SUSPICIOUS.search(line)][:10]


def _confidence(
    amount: Decimal | None, citation: dict[str, Any] | None, suspicious: Sequence[str] = ()
) -> str:
    if citation is None:
        return "unverified"
    quote = norm(citation["quote"])
    if _SUSPICIOUS.search(quote) or any(quote in line for line in suspicious):
        return "unverified"  # cytat z linii wyglądającej na polecenie, nie na ofertę
    if amount is not None and amount not in numbers_in(citation["quote"]):
        return "unverified"  # liczba spoza cytatu: możliwa halucynacja
    return "medium"  # zweryfikowane automatycznie, ale wciąż do przejrzenia przez parę


_MIN_GUESTS = re.compile(r"minim\w*[^\n\d]{0,40}?(\d{1,4})\s*(?:os|gośc|gosc|pax)", re.I)


def verified_min_guests(value: Any, document_text: str) -> int | None:
    """Minimum gości tylko, gdy liczba stoi w dokumencie przy słowie „minim…”.

    Wartość modelu bez potwierdzenia jest odrzucana; gdy model nic nie podał,
    używamy deterministycznego wzorca (te same słowa kluczowe).
    """
    candidates = {int(m) for m in _MIN_GUESTS.findall(document_text)}
    if isinstance(value, int) and not isinstance(value, bool) and value in candidates:
        return value
    return next(iter(candidates)) if len(candidates) == 1 else None


# Zadatek / zaliczka z kwotą w złotych w jednej linii, np. „Zadatek w wysokości 5 000 zł”.
# Kwota: cyfry z separatorem tysięcy (spacja, kropka, twarda spacja) albo bez; grosze po przecinku.
_DEPOSIT = re.compile(
    r"(zadat\w*|zaliczk\w*)[^\d%]{0,60}?"
    + r"(\d{1,3}(?:[ .]\d{3})+|\d+)(?:,(\d{2}))?\s*(?:zł|zl|pln)",
    re.I,
)


def deposit_candidates(pages: Sequence[str]) -> list[dict[str, Any]]:
    """Linie z zadatkiem/zaliczką i kwotą w zł (deterministycznie, bez modelu)."""
    found: dict[tuple[str, Decimal], dict[str, Any]] = {}
    for page_no, page in enumerate(pages, start=1):
        for line in page.splitlines():
            for m in _DEPOSIT.finditer(line.replace(NBSP, " ")):
                amount = _decimal(_THOUSANDS.sub("", m.group(2)) + "." + (m.group(3) or "00"))
                if amount is None or amount == 0:
                    continue
                zadatek = m.group(1).lower().startswith("zadat")
                kind = "deposit_zadatek" if zadatek else "advance_zaliczka"
                found.setdefault(
                    (kind, amount),
                    {"kind": kind, "amount": amount, "quote": line.strip()[:500], "page": page_no},
                )
    return list(found.values())


def validate(
    raw: dict[str, Any],
    document_text: str,
    page_count: int,
    pages: Sequence[str] | None = None,
) -> Validated:
    doc_norm = norm(document_text)
    flagged = [norm(line) for line in document_text.splitlines() if _SUSPICIOUS.search(line)]
    title = raw.get("title") if isinstance(raw.get("title"), str) else None
    result = Validated(
        title=(title or "Oferta z dokumentu").strip()[:200] or "Oferta z dokumentu",
        min_guests=verified_min_guests(raw.get("min_guests"), document_text),
    )

    for item in (raw.get("components") or [])[:MAX_COMPONENTS]:
        if not isinstance(item, dict) or item.get("kind") not in COMPONENT_KINDS:
            result.stats["dropped"] += 1
            continue
        label = item.get("label")
        if not isinstance(label, str) or not label.strip():
            result.stats["dropped"] += 1
            continue
        amount = _decimal(item.get("amount"))
        if item["kind"] == "percent" and amount is not None and amount > 100:
            amount = None
        citation = _citation(item, doc_norm, page_count)
        confidence = _confidence(amount, citation, flagged)
        event = item.get("event_kind")
        if event not in EVENT_KINDS and "poprawin" in norm(f"{label} {item.get('quote') or ''}"):
            event = "after_party"  # reguła domenowa: poprawiny liczone osobno (inna liczba gości)
        result.components.append(
            {
                "label": label.strip()[:200],
                "kind": item["kind"],
                "amount": amount,
                "quantity": _decimal(item.get("quantity")),
                "included": bool(item.get("included")),
                "optional": bool(item.get("optional")),
                "event_kind": event if event in EVENT_KINDS else None,
                "citation": citation,
                "confidence": confidence,
            }
        )
        result.stats["components"] += 1
        result.stats["verified" if confidence == "medium" else "unverified"] += 1

    for item in (raw.get("terms") or [])[:MAX_TERMS]:
        term = _term(item, doc_norm, page_count, flagged)
        if term is None:
            result.stats["dropped"] += 1
            continue
        result.terms.append(term)
        result.stats["terms"] += 1
        result.stats["verified" if term["confidence"] == "medium" else "unverified"] += 1
    # Model nie podał pewnego zadatku/zaliczki, a w dokumencie stoi dokładnie jedna taka kwota:
    # dodajemy ją z dosłownym cytatem (wcześniej odczyt zadatku w DOCX był słaby, ogr. nr 32).
    has_deposit = any(t["term_type"] == "deposit" for t in result.terms)
    candidates = deposit_candidates(pages if pages is not None else [document_text])
    if not has_deposit and len(candidates) == 1 and len(result.terms) < MAX_TERMS:
        c = candidates[0]
        line = norm(c["quote"])
        flagged_line = bool(_SUSPICIOUS.search(line)) or any(line in f for f in flagged)
        result.terms.append(
            {
                "term_type": "deposit",
                "text": c["quote"],
                "amount": {"amount": c["amount"], "currency": "PLN"},
                "deposit_kind": c["kind"],
                "citation": {"quote": c["quote"], "page": c["page"] if pages is not None else None},
                "confidence": "unverified" if flagged_line else "medium",
            }
        )
        result.stats["terms"] += 1
        result.stats["unverified" if flagged_line else "verified"] += 1
    result.suspicious = suspicious_fragments(document_text)
    return result


def _term(
    item: Any, doc_norm: str, page_count: int, flagged: Sequence[str] = ()
) -> dict[str, Any] | None:
    if not isinstance(item, dict) or item.get("term_type") not in TERM_TYPES:
        return None
    citation = _citation(item, doc_norm, page_count)
    amount = _decimal(item.get("amount"))
    text = item.get("text") if isinstance(item.get("text"), str) else None
    term_type = item["term_type"]
    deposit_kind = None
    if term_type == "deposit":
        # Zadatek czy zaliczka: rozstrzyga słowo w cytacie (deterministycznie), nie model.
        source = norm(citation["quote"]) if citation else ""
        if "zadat" in source:
            deposit_kind = "deposit_zadatek"
        elif "zaliczk" in source:
            deposit_kind = "advance_zaliczka"
        if deposit_kind is None or amount is None:
            term_type = "other"  # niepewny charakter płatności → informacja do sprawdzenia
    return {
        "term_type": term_type,
        "text": (text or (citation["quote"] if citation else None) or "")[:2000] or None,
        "amount": {"amount": amount, "currency": "PLN"} if amount is not None else None,
        "deposit_kind": deposit_kind,
        "citation": citation,
        "confidence": _confidence(amount, citation, flagged),
    }
