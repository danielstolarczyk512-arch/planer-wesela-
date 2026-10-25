# ruff: noqa: RUF001, RUF003
"""Deterministyczna ekstrakcja faktów i cen ze strony firmy (bez LLM).

Źródła danych w kolejności zaufania: JSON-LD (schema.org), linki `tel:`/`mailto:`, meta tagi,
linie tekstu z kwotą i walutą. Każdy fakt ma cytat (`evidence`) z tej strony. Czego nie da się
ustalić, zostaje nieustalone: brak ceny = „zapytaj o wycenę”, brak sezonu jest jawny.

Treść strony jest niezaufanym tekstem: ten moduł jej nie interpretuje jako poleceń (nie ma tu
modelu ani narzędzi), a ukryte elementy HTML (`hidden`, `display:none`, `aria-hidden`) są
pomijane jako tekst widoczny.
"""

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

PARSER_VERSION = "1"
MAX_PACKAGES = 40
MAX_EVIDENCE = 300
MAX_EXCERPT = 4000

_SKIP_TAGS = frozenset({"script", "style", "noscript", "svg", "template", "head", "iframe"})
_BLOCK_TAGS = frozenset(
    {
        "p", "div", "li", "br", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "section",
        "article", "header", "footer", "ul", "ol", "table", "dd", "dt", "blockquote",
    }
)  # fmt: skip
_VOID_TAGS = frozenset(
    {"br", "img", "meta", "link", "input", "hr", "area", "base", "col", "embed", "source", "wbr"}
)
_SOCIAL_HOSTS = (
    "facebook.com", "instagram.com", "youtube.com", "tiktok.com", "linkedin.com", "pinterest.com",
)  # fmt: skip


@dataclass
class ExtractedFact:
    field: str
    value: str
    evidence: str


@dataclass
class ExtractedPackage:
    name: str
    kind: str  # package | surcharge
    price_from: Decimal | None
    price_to: Decimal | None
    currency: str
    unit: str
    season: str | None
    evidence: str

    @property
    def key(self) -> str:
        return "|".join((self.kind, normalize_key(self.name), self.unit, self.season or ""))


@dataclass
class Extracted:
    name: str | None = None
    facts: list[ExtractedFact] = field(default_factory=list)
    packages: list[ExtractedPackage] = field(default_factory=list)
    text: str = ""
    structured: bool = False  # tożsamość z danych strukturalnych (JSON-LD), nie tylko z tytułu

    def values(self, field_name: str) -> list[str]:
        return [f.value for f in self.facts if f.field == field_name]


def normalize_key(text: str) -> str:
    return re.sub(r"[^a-z0-9ąćęłńóśźż]+", " ", text.lower()).strip()


class _Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta: dict[str, str] = {}
        self.links: list[tuple[str, str]] = []  # (href, tekst)
        self.jsonld: list[str] = []
        self.lines_raw: list[str] = []
        self.lang = ""
        self._skip = 0
        self._stack: list[tuple[str, bool]] = []
        self._in_title = False
        self._in_jsonld = False
        self._jsonld_buf: list[str] = []
        self._link_href: str | None = None
        self._link_text: list[str] = []
        self._buf: list[str] = []

    def _flush(self) -> None:
        if self._buf:
            self.lines_raw.append("".join(self._buf))
            self._buf = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag == "html":
            self.lang = a.get("lang", "")
        if tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._in_jsonld = True
            self._jsonld_buf = []
            return
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            key = a.get("property") or a.get("name")
            if key and "content" in a:
                self.meta.setdefault(key.lower(), a["content"].strip())
        if tag == "a" and a.get("href"):
            self._link_href, self._link_text = a["href"].strip(), []
        if tag in _VOID_TAGS:
            if tag in _BLOCK_TAGS:
                self._flush()
            return
        hidden = (
            "hidden" in a
            or a.get("aria-hidden", "").lower() == "true"
            or re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", a.get("style", ""), re.I)
            is not None
        )
        skipped = bool(hidden) or tag in _SKIP_TAGS
        self._stack.append((tag, skipped))
        if skipped:
            self._skip += 1
        if tag in _BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_jsonld:
            self._in_jsonld = False
            self.jsonld.append("".join(self._jsonld_buf))
            return
        if tag == "title":
            self._in_title = False
        if tag == "a" and self._link_href is not None:
            self.links.append((self._link_href, " ".join("".join(self._link_text).split())))
            self._link_href = None
        if tag in _VOID_TAGS:
            return
        # Niedomknięte znaczniki (<p>, <li>) nie mogą rozjechać licznika ukrytych elementów:
        # zdejmujemy ze stosu aż do pasującego znacznika (albo nic, gdy go nie było).
        if any(name == tag for name, _ in self._stack):
            while self._stack:
                name, skipped = self._stack.pop()
                if skipped:
                    self._skip -= 1
                if name == tag:
                    break
        if tag in _BLOCK_TAGS:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._in_jsonld:
            self._jsonld_buf.append(data)
            return
        if self._in_title:
            self.title += data
        if self._skip:
            return
        if self._link_href is not None:
            self._link_text.append(data)
        self._buf.append(data)

    def close(self) -> None:
        super().close()
        self._flush()


def _clean_line(line: str) -> str:
    return " ".join(line.replace(" ", " ").replace("​", "").split())


def visible_lines(parser: _Page) -> list[str]:
    lines = [_clean_line(raw) for raw in parser.lines_raw]
    return [ln for ln in lines if ln]


# --- kwoty ---------------------------------------------------------------------------------

_AMOUNT = r"\d{1,3}(?:[  .]\d{3})+(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?"
_CURRENCY = r"(?:zł|zl|pln|eur|€)"
PRICE_RE = re.compile(
    rf"(?P<from>(?:już\s+)?od\s+)?(?<![\w.,])(?P<a>{_AMOUNT})\s*(?:(?:-|–|—|do)\s*(?P<b>{_AMOUNT})\s*)?"
    rf"(?P<cur>{_CURRENCY})(?![a-ząćęłńóśźż])",
    re.IGNORECASE,
)
_NON_PRICE_WORDS = re.compile(r"zadat|zaliczk|kaucj|rabat|zniżk|gwarancj|nr konta|konto", re.I)
_SURCHARGE_WORDS = re.compile(r"dopłat|dojazd|nadgodzin|za każd|noclegu|dodatkow", re.I)
_UNITS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("hour", re.compile(r"/\s*h\b|/\s*godz|za\s+godz|na\s+godz|godzin[aęy]\b", re.I)),
    ("person", re.compile(r"/\s*os\b|/\s*osob|za\s+osob|na\s+osob|od\s+osoby|per\s+person", re.I)),
    ("day", re.compile(r"/\s*dzie[ńn]|za\s+dzie[ńn]|za\s+dob|/\s*dob", re.I)),
    ("km", re.compile(r"/\s*km\b|za\s+(?:każdy\s+)?km\b|za\s+kilometr", re.I)),
    ("event", re.compile(r"za\s+(?:całe\s+)?wesel|za\s+wydarzen|za\s+event", re.I)),
    ("package", re.compile(r"za\s+pakiet|/\s*pakiet|pakiet\b", re.I)),
)
_YEAR_RE = re.compile(r"\b(20[2-3]\d)\b")
_SEASON_WORDS = re.compile(r"sezon|cennik|oferta|rok", re.I)


def parse_amount(token: str) -> Decimal | None:
    t = token.replace(" ", " ").strip()
    if re.fullmatch(r"\d{1,3}(?:[ .]\d{3})+(?:,\d{1,2})?", t):
        t = t.replace(" ", "").replace(".", "").replace(",", ".")
    else:
        t = t.replace(" ", "").replace(",", ".")
    try:
        value = Decimal(t)
    except InvalidOperation:
        return None
    return value if value > 0 else None


def _currency(raw: str) -> str:
    return "EUR" if raw.lower() in ("eur", "€") else "PLN"


def _unit_for(line: str) -> str:
    for unit, pattern in _UNITS:
        if pattern.search(line):
            return unit
    return "unspecified"


def _season_for(line_without_price: str, context: str | None) -> str | None:
    m = _YEAR_RE.search(line_without_price)
    if m:
        return m.group(1)
    return context


def _package_name(before: str, previous: str | None) -> str:
    name = re.sub(r"[\s:–—\-|/•·]+$", "", before).strip(" :–—-|•·")
    name = re.sub(r"^(?:cena|pakiet\s*:)\s*", "", name, flags=re.I).strip()
    if len(name) >= 3:
        return name[:120]
    if previous and len(previous) <= 80 and not PRICE_RE.search(previous):
        return previous[:120]
    return "Pakiet"


def extract_packages(lines: list[str]) -> list[ExtractedPackage]:
    packages: list[ExtractedPackage] = []
    seen: set[str] = set()
    context_season: str | None = None
    previous: str | None = None
    for line in lines:
        match = PRICE_RE.search(line)
        if match is None:
            if _SEASON_WORDS.search(line) and len(line) <= 80:
                y = _YEAR_RE.search(line)
                if y:
                    context_season = y.group(1)
            previous = line
            continue
        if _NON_PRICE_WORDS.search(line) or len(line) > 400:
            previous = line
            continue
        low = _parse_price_line(line, match, previous, context_season)
        previous = line
        if low is None:
            continue
        if low.key in seen:
            continue
        seen.add(low.key)
        packages.append(low)
        if len(packages) >= MAX_PACKAGES:
            break
    return packages


def _parse_price_line(
    line: str, match: re.Match[str], previous: str | None, context_season: str | None
) -> ExtractedPackage | None:
    a = parse_amount(match.group("a"))
    if a is None:
        return None
    b = parse_amount(match.group("b")) if match.group("b") else None
    # „od 3000 zł” to dolna granica; zakres 3000–4500 to od/do; sama kwota to cena (od=do).
    if b is not None:
        if b < a:
            return None
        price_from, price_to = a, b
    elif match.group("from"):
        price_from, price_to = a, None
    else:
        price_from, price_to = a, a
    before = line[: match.start()]
    rest = line[match.end() :]
    stripped = (line[: match.start()] + " " + rest).strip()
    kind = "surcharge" if _SURCHARGE_WORDS.search(line) else "package"
    name = _package_name(before, previous)
    if kind == "surcharge" and len(before.strip(" :–—-")) < 3:
        name = (previous or "Dopłata")[:120]
    return ExtractedPackage(
        name=name,
        kind=kind,
        price_from=price_from,
        price_to=price_to,
        currency=_currency(match.group("cur")),
        unit=_unit_for(line),
        season=_season_for(stripped, context_season),
        evidence=line[:MAX_EVIDENCE],
    )


# --- dane strukturalne ----------------------------------------------------------------------

_ORG_TYPES = ("business", "organization", "photographer", "service", "store", "person", "studio")


def _jsonld_objects(blobs: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def walk(node: Any, depth: int = 0) -> None:
        if depth > 6:
            return
        if isinstance(node, list):
            for item in node:
                walk(item, depth + 1)
        elif isinstance(node, dict):
            out.append(node)
            for key in ("@graph", "makesOffer", "offers", "itemListElement", "hasOfferCatalog"):
                if key in node:
                    walk(node[key], depth + 1)

    for blob in blobs:
        try:
            walk(json.loads(blob))
        except (ValueError, RecursionError):
            continue
    return out


def _types(node: dict[str, Any]) -> list[str]:
    raw = node.get("@type", [])
    values = raw if isinstance(raw, list) else [raw]
    return [str(v).lower() for v in values]


def _str(value: Any) -> str | None:
    if isinstance(value, str):
        return " ".join(value.split()) or None
    return None


def _jsonld_offer(node: dict[str, Any], page_name: str | None) -> ExtractedPackage | None:
    price = node.get("price")
    spec = node.get("priceSpecification")
    low = high = None
    if isinstance(spec, dict):
        low = parse_amount(str(spec.get("minPrice", ""))) if spec.get("minPrice") else None
        high = parse_amount(str(spec.get("maxPrice", ""))) if spec.get("maxPrice") else None
        price = price or spec.get("price")
    if price not in (None, ""):
        amount = parse_amount(str(price))
        if amount is not None:
            low, high = (low or amount), (high or amount)
    if low is None:
        return None
    if high is not None and high < low:
        return None
    currency = str(node.get("priceCurrency") or (spec or {}).get("priceCurrency") or "PLN").upper()
    if currency not in ("PLN", "EUR"):
        return None
    offered = node.get("itemOffered")
    item: dict[str, Any] = offered if isinstance(offered, dict) else {}
    name = _str(node.get("name")) or _str(item.get("name")) or page_name or "Oferta"
    spec_d: dict[str, Any] = spec if isinstance(spec, dict) else {}
    unit_text = str(spec_d.get("unitText") or node.get("unitText") or "")
    until = _str(node.get("validThrough"))
    season = until[:4] if until and _YEAR_RE.fullmatch(until[:4]) else None
    return ExtractedPackage(
        name=name[:120],
        kind="package",
        price_from=low,
        price_to=high,
        currency=currency,
        unit=_unit_for(unit_text) if unit_text else "unspecified",
        season=season,
        evidence=json.dumps(
            {
                k: node[k]
                for k in ("name", "price", "priceCurrency", "priceSpecification")
                if k in node
            },
            ensure_ascii=False,
        )[:MAX_EVIDENCE],
    )


def _add(facts: list[ExtractedFact], field_name: str, value: str | None, evidence: str) -> None:
    if not value:
        return
    value = value.strip()[:500]
    if any(f.field == field_name and f.value == value for f in facts):
        return
    facts.append(ExtractedFact(field_name, value, evidence[:MAX_EVIDENCE]))


def _title_name(title: str) -> str | None:
    parts = [p.strip() for p in re.split(r"\s[|\-–—•·]\s", title) if p.strip()]
    for part in parts:
        if 2 <= len(part) <= 80:
            return part
    return None


def extract(html: str, page_url: str) -> Extracted:
    parser = _Page()
    parser.feed(html)
    parser.close()
    lines = visible_lines(parser)
    result = Extracted(text="\n".join(lines)[:MAX_EXCERPT])
    facts = result.facts
    objects = _jsonld_objects(parser.jsonld)

    business = next(
        (o for o in objects if any(t in ty for ty in _types(o) for t in _ORG_TYPES)), None
    )
    if business is not None and _str(business.get("name")):
        result.name = _str(business["name"])
        result.structured = True
        _add(facts, "name", result.name, f"JSON-LD name: {result.name}")
        _add(facts, "phone", _str(business.get("telephone")), "JSON-LD telephone")
        _add(facts, "email", _str(business.get("email")), "JSON-LD email")
        address = business.get("address")
        if isinstance(address, dict):
            _add(facts, "city", _str(address.get("addressLocality")), "JSON-LD addressLocality")
        area = business.get("areaServed")
        area_name = _str(area) or (_str(area.get("name")) if isinstance(area, dict) else None)
        _add(facts, "service_area", area_name, "JSON-LD areaServed")
        same_as = business.get("sameAs")
        for link in same_as if isinstance(same_as, list) else [same_as]:
            if isinstance(link, str) and _is_social(link):
                _add(facts, "social", link, "JSON-LD sameAs")
    if result.name is None:
        site = parser.meta.get("og:site_name")
        result.name = _str(site) or _title_name(" ".join(parser.title.split()))
        if result.name:
            _add(facts, "name", result.name, (site and f"og:site_name: {site}") or parser.title)

    for href, text in parser.links:
        low = href.lower()
        if low.startswith("tel:"):
            number = re.sub(r"[^\d+]", "", href[4:])
            if len(re.sub(r"\D", "", number)) >= 9:
                _add(facts, "phone", number, f"tel: {text or href[4:]}")
        elif low.startswith("mailto:"):
            address = href[7:].split("?", 1)[0].strip().lower()
            if re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", address):
                _add(facts, "email", address, f"mailto: {address}")
        elif low.startswith("http") and _is_social(href):
            _add(facts, "social", href.split("#", 1)[0], f"link: {text or href}"[:200])
    if page_url:
        _add(facts, "website", page_url, "adres źródła")

    page_name = result.name
    packages: list[ExtractedPackage] = []
    for node in objects:
        if any(t == "offer" for t in _types(node)):
            offer = _jsonld_offer(node, page_name)
            if offer is not None:
                packages.append(offer)
    packages.extend(extract_packages(lines))
    unique: dict[str, ExtractedPackage] = {}
    for pkg in packages:
        unique.setdefault(pkg.key, pkg)
    result.packages = list(unique.values())[:MAX_PACKAGES]
    return result


def _is_social(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in _SOCIAL_HOSTS)
