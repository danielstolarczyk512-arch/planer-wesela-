"""Pobieranie jednej strony HTML: limity, przekierowania, bez obchodzenia zabezpieczeń.

Wynik to zawsze `FetchResult` z nazwanym wynikiem (`outcome`); decyzję, co zrobić ze źródłem
(ponowić, zatrzymać, wycofać), podejmuje `service.py`. Fetcher niczego nie omija: 401/403/CAPTCHA
kończy się wynikiem `access_denied`/`captcha`, a nie próbą innego klienta czy nagłówków.
"""

import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit

import httpx

from app.core.config import Settings
from app.modules.discovery.safety import GuardedTransport, UnsafeUrl, validate_url

REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})
HTML_TYPES = ("text/html", "application/xhtml+xml")
_CAPTCHA_MARKERS = (
    "g-recaptcha",
    "h-captcha",
    "cf-turnstile",
    "challenge-platform",
    "cf-challenge",
    "attention required! | cloudflare",
    "just a moment...",
    "captcha",
)
MAX_RETRY_AFTER = 24 * 3600


@dataclass
class FetchResult:
    outcome: str
    status: int | None = None
    final_url: str | None = None
    body: bytes | None = None
    text: str | None = None
    retry_after: int | None = None
    detail: str | None = None

    @property
    def ok(self) -> bool:
        return self.outcome == "ok"


def parse_retry_after(value: str | None) -> int | None:
    """Retry-After: sekundy albo data HTTP, ograniczone do doby."""
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return min(int(value), MAX_RETRY_AFTER)
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0, min(int((when - datetime.now(UTC)).total_seconds()), MAX_RETRY_AFTER))


def decode_html(body: bytes, content_type: str | None) -> str:
    charset = None
    if content_type:
        m = re.search(r"charset=([\w\-]+)", content_type, re.IGNORECASE)
        charset = m.group(1) if m else None
    if charset is None:
        m2 = re.search(rb"<meta[^>]+charset=[\"']?([\w\-]+)", body[:4096], re.IGNORECASE)
        charset = m2.group(1).decode("ascii", "ignore") if m2 else None
    for candidate in (charset, "utf-8", "cp1250"):
        if not candidate:
            continue
        try:
            return body.decode(candidate)
        except (UnicodeDecodeError, LookupError):
            continue
    return body.decode("utf-8", "replace")


def looks_like_captcha(status: int, text: str) -> bool:
    low = text.lower()
    marked = any(marker in low for marker in _CAPTCHA_MARKERS)
    if not marked:
        return False
    if status in (403, 429, 503):
        return True
    # Formularz kontaktowy z reCAPTCHA na zwykłej stronie nie jest blokadą; pusta strona jest.
    visible = re.sub(r"<[^>]+>", " ", low)
    return status == 200 and len(visible.split()) < 60


def _same_site(a: str, b: str) -> bool:
    def strip(h: str) -> str:
        return h.removeprefix("www.")

    return strip(a) == strip(b)


def fetch_page(
    url: str,
    settings: Settings,
    *,
    transport: httpx.BaseTransport | None = None,
    accept: tuple[str, ...] = HTML_TYPES,
) -> FetchResult:
    """Pobiera stronę (GET); przekierowania tylko w obrębie witryny, do limitu z konfiguracji."""
    allow_private = settings.discovery_allow_private_hosts
    deadline = time.monotonic() + settings.discovery_timeout_seconds
    try:
        target = validate_url(url, allow_private=allow_private)
    except UnsafeUrl as exc:
        return FetchResult("unsafe_url", detail=exc.reason)
    origin_host = target.host
    current = target.url
    timeout = httpx.Timeout(settings.discovery_timeout_seconds, connect=10.0)
    headers = {
        "User-Agent": settings.discovery_user_agent,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
        "Accept-Language": "pl,en;q=0.5",
    }
    own_transport = transport or GuardedTransport(allow_private)
    try:
        with httpx.Client(
            transport=own_transport, timeout=timeout, follow_redirects=False, trust_env=False
        ) as client:
            for _hop in range(settings.discovery_max_redirects + 1):
                try:
                    with client.stream("GET", current, headers=headers) as response:
                        result = _handle(response, current, settings, deadline, accept)
                        location = response.headers.get("location")
                except UnsafeUrl as exc:
                    return FetchResult("unsafe_url", final_url=current, detail=exc.reason)
                except httpx.TimeoutException:
                    return FetchResult("timeout", final_url=current)
                except httpx.TransportError as exc:
                    return FetchResult(
                        "network_error", final_url=current, detail=type(exc).__name__
                    )
                if result is not None:
                    return result
                if not location:
                    return FetchResult(
                        "client_error", final_url=current, detail="redirect bez Location"
                    )
                try:
                    nxt = validate_url(urljoin(current, location), allow_private=allow_private)
                except UnsafeUrl as exc:
                    return FetchResult("unsafe_url", final_url=current, detail=exc.reason)
                if not _same_site(origin_host, nxt.host):
                    return FetchResult(
                        "cross_domain_redirect",
                        final_url=nxt.url,
                        detail=urlsplit(nxt.url).hostname,
                    )
                current = nxt.url
            return FetchResult("too_many_redirects", final_url=current)
    finally:
        if transport is None:
            own_transport.close()


def _handle(
    response: httpx.Response,
    url: str,
    settings: Settings,
    deadline: float,
    accept: tuple[str, ...],
) -> FetchResult | None:
    """None oznacza przekierowanie do obsłużenia przez wywołującego."""
    status = response.status_code
    if status in REDIRECT_CODES:
        return None
    retry_after = parse_retry_after(response.headers.get("retry-after"))
    if status in (404, 410):
        return FetchResult("gone", status, url)
    if status in (401, 407):
        return FetchResult("access_denied", status, url)
    if status == 429:
        return FetchResult("rate_limited", status, url, retry_after=retry_after)
    if status >= 400:
        body = _read(response, settings, deadline, limit=64_000)
        text = decode_html(body, response.headers.get("content-type")) if body else ""
        if looks_like_captcha(status, text):
            return FetchResult("captcha", status, url)
        if status == 403:
            return FetchResult("access_denied", status, url)
        if status >= 500:
            return FetchResult("server_error", status, url, retry_after=retry_after)
        return FetchResult("client_error", status, url)
    content_type = response.headers.get("content-type", "").lower()
    if not any(content_type.startswith(kind) for kind in accept):
        return FetchResult("unsupported_type", status, url, detail=content_type[:80])
    body = _read(response, settings, deadline, limit=settings.discovery_max_html_bytes + 1)
    if len(body) > settings.discovery_max_html_bytes:
        return FetchResult("too_large", status, url)
    text = decode_html(body, content_type)
    if looks_like_captcha(status, text):
        return FetchResult("captcha", status, url)
    return FetchResult("ok", status, url, body=body, text=text)


def _read(response: httpx.Response, settings: Settings, deadline: float, *, limit: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    for chunk in response.iter_bytes():
        chunks.append(chunk)
        size += len(chunk)
        if size >= limit:
            break
        if time.monotonic() > deadline:
            raise httpx.ReadTimeout("przekroczony całkowity czas pobrania")
    return b"".join(chunks)[:limit]
