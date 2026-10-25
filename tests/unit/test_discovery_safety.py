# ruff: noqa: PT018
"""Ochrona przed SSRF i zachowanie fetchera (bez sieci: atrapy transportu i DNS)."""

import socket
from collections.abc import Callable

import httpx
import pytest

from app.core.config import get_settings
from app.modules.discovery import fetcher, safety
from app.modules.discovery.safety import UnsafeUrl, validate_url


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/",
        "gopher://example.com/",
        "http://user:pass@example.com/",
        "http://localhost/",
        "http://foo.localhost/",
        "http://127.0.0.1/",
        "http://127.1.2.3/",
        "http://10.0.0.5/",
        "http://172.16.0.1/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://100.64.0.1/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://[::ffff:10.0.0.1]/",
        "http://[fe80::1]/",
        "http://[fd00::1]/",
        "http://[64:ff9b::7f00:1]/",
        "http://example.com:8080/",
        "http://example.com:22/",
        "http://exa mple.com/",
        "https:///nohost",
    ],
)
def test_unsafe_urls_rejected(url: str) -> None:
    with pytest.raises(UnsafeUrl):
        validate_url(url)


def test_public_urls_accepted_and_normalized() -> None:
    t = validate_url("HTTPS://Studio-Foto.EXAMPLE:443/cennik?x=1")
    assert (t.scheme, t.host, t.port) == ("https", "studio-foto.example", 443)
    assert t.url == "https://studio-foto.example/cennik?x=1"
    assert validate_url("http://example.com").url == "http://example.com/"


def _patch_dns(monkeypatch: pytest.MonkeyPatch, ips: Callable[[], list[str]]) -> None:
    def fake(host: str, port: int, **_: object) -> list[tuple]:  # type: ignore[type-arg]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in ips()]

    monkeypatch.setattr(safety.socket, "getaddrinfo", fake)


def test_decimal_and_mixed_hostnames_blocked_by_dns_check(monkeypatch: pytest.MonkeyPatch) -> None:
    # „http://2130706433/” rozwiązuje się do 127.0.0.1 — blokada działa po rozwiązaniu nazwy.
    _patch_dns(monkeypatch, lambda: ["127.0.0.1"])
    with pytest.raises(UnsafeUrl):
        safety.resolve_public("2130706433", 80)


def test_all_resolved_addresses_must_be_public(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_dns(monkeypatch, lambda: ["93.184.216.34", "10.0.0.1"])
    with pytest.raises(UnsafeUrl):
        safety.resolve_public("mixed.example", 443)


def test_dns_rebinding_is_caught_at_connect_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """Walidacja widzi adres publiczny, połączenie — prywatny: pobranie musi zostać zablokowane."""
    answers = iter([["93.184.216.34"], ["127.0.0.1"], ["127.0.0.1"]])
    _patch_dns(monkeypatch, lambda: next(answers))
    safety.resolve_public("rebind.example", 80)  # „walidacja” (pierwsza odpowiedź)
    result = fetcher.fetch_page("http://rebind.example/", get_settings())
    assert result.outcome == "unsafe_url"


def test_redirect_to_private_ip_blocked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data/"})

    result = fetcher.fetch_page(
        "https://studio.example/", get_settings(), transport=httpx.MockTransport(handler)
    )
    assert result.outcome == "unsafe_url"


def test_redirect_to_other_domain_not_followed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(301, headers={"Location": "https://inna-firma.example/"})

    result = fetcher.fetch_page(
        "https://studio.example/", get_settings(), transport=httpx.MockTransport(handler)
    )
    assert (result.outcome, result.detail) == ("cross_domain_redirect", "inna-firma.example")


def test_redirect_within_site_followed_and_limited() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path == "/":
            return httpx.Response(301, headers={"Location": "https://www.studio.example/cennik"})
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<p>ok</p>")

    result = fetcher.fetch_page(
        "https://studio.example/", get_settings(), transport=httpx.MockTransport(handler)
    )
    assert result.ok and result.final_url == "https://www.studio.example/cennik"

    def loop(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": request.url.path + "x"})

    looped = fetcher.fetch_page(
        "https://studio.example/a", get_settings(), transport=httpx.MockTransport(loop)
    )
    assert looped.outcome == "too_many_redirects"


def _fetch(handler: Callable[[httpx.Request], httpx.Response]) -> fetcher.FetchResult:
    return fetcher.fetch_page(
        "https://studio.example/", get_settings(), transport=httpx.MockTransport(handler)
    )


def test_status_codes_map_to_outcomes() -> None:
    def respond(status: int, **kw: object) -> Callable[[httpx.Request], httpx.Response]:
        return lambda _r: httpx.Response(status, **kw)  # type: ignore[arg-type]

    assert _fetch(respond(404)).outcome == "gone"
    assert _fetch(respond(410)).outcome == "gone"
    assert _fetch(respond(401)).outcome == "access_denied"
    assert _fetch(respond(403, text="Forbidden")).outcome == "access_denied"
    assert _fetch(respond(418)).outcome == "client_error"
    limited = _fetch(respond(429, headers={"Retry-After": "120"}))
    assert (limited.outcome, limited.retry_after) == ("rate_limited", 120)
    down = _fetch(respond(503, headers={"Retry-After": "30"}, text="busy"))
    assert (down.outcome, down.retry_after) == ("server_error", 30)
    assert _fetch(respond(500)).outcome == "server_error"


def test_captcha_and_challenge_pages_are_not_bypassed() -> None:
    challenge = "<html><title>Just a moment...</title><div id='cf-challenge'></div></html>"
    r = _fetch(
        lambda _r: httpx.Response(403, headers={"content-type": "text/html"}, text=challenge)
    )
    assert r.outcome == "captcha"
    thin = "<html><body><div class='g-recaptcha'></div></body></html>"
    r2 = _fetch(lambda _r: httpx.Response(200, headers={"content-type": "text/html"}, text=thin))
    assert r2.outcome == "captcha"
    # Formularz kontaktowy z reCAPTCHA na normalnej, pełnej stronie to nie blokada.
    page = "<html><body>" + "słowo " * 200 + "<div class='g-recaptcha'></div></body></html>"
    r3 = _fetch(lambda _r: httpx.Response(200, headers={"content-type": "text/html"}, text=page))
    assert r3.ok


def test_size_type_and_timeout_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WP_DISCOVERY_MAX_HTML_BYTES", "1000")
    get_settings.cache_clear()
    try:
        big = _fetch(
            lambda _r: httpx.Response(
                200, headers={"content-type": "text/html"}, content=b"a" * 5000
            )
        )
        assert big.outcome == "too_large"
    finally:
        monkeypatch.delenv("WP_DISCOVERY_MAX_HTML_BYTES")
        get_settings.cache_clear()
    pdf = _fetch(lambda _r: httpx.Response(200, headers={"content-type": "application/pdf"}))
    assert pdf.outcome == "unsupported_type"

    def slow(_r: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("zbyt wolno")

    assert _fetch(slow).outcome == "timeout"

    def broken(_r: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("odmowa")

    assert _fetch(broken).outcome == "network_error"


def test_retry_after_parsing() -> None:
    assert fetcher.parse_retry_after("90") == 90
    assert fetcher.parse_retry_after("999999") == fetcher.MAX_RETRY_AFTER
    assert fetcher.parse_retry_after("jutro") is None
    assert fetcher.parse_retry_after(None) is None
    assert fetcher.parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 0


def test_charset_decoding_polish() -> None:
    body = "Zażółć gęślą jaźń".encode("cp1250")
    assert fetcher.decode_html(body, "text/html; charset=windows-1250") == "Zażółć gęślą jaźń"
    utf = "Zażółć".encode()
    assert fetcher.decode_html(utf, "text/html") == "Zażółć"
