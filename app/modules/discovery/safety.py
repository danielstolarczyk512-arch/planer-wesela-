"""Ochrona przed SSRF dla badacza katalogu (ADR-0008).

Reguły: tylko http/https, porty 80/443, bez danych logowania w adresie, bez adresów prywatnych,
zarezerwowanych, link-local, loopback i metadanych chmurowych (IPv4 i IPv6, także IPv4 w IPv6).
DNS jest sprawdzany przy KAŻDYM połączeniu (`GuardedBackend`), więc zmiana odpowiedzi DNS między
walidacją a połączeniem (DNS rebinding) i przekierowania nie obchodzą blokady: łączymy się z tym
adresem IP, który przeszedł kontrolę.
"""

import ipaddress
import socket
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpcore
import httpx

ALLOWED_PORTS = frozenset({80, 443})
MAX_URL_LENGTH = 500
# Zakresy, które Python uznaje za „global”, a nie są celem dla zwykłej strony firmy.
_EXTRA_BLOCKED = tuple(
    ipaddress.ip_network(n)
    for n in (
        "64:ff9b::/96",  # NAT64
        "2002::/16",  # 6to4 (zawiera adres IPv4)
        "2001::/32",  # Teredo
        "100.64.0.0/10",  # CGNAT
        "169.254.0.0/16",  # link-local, w tym metadane chmurowe 169.254.169.254
        "192.0.0.0/24",
        "198.18.0.0/15",
    )
)


class UnsafeUrl(Exception):
    """Adres nie przeszedł kontroli bezpieczeństwa (komunikat bez danych wrażliwych)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Target:
    url: str
    scheme: str
    host: str
    port: int


def is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return is_public_ip(ip.ipv4_mapped)
    if not ip.is_global or ip.is_multicast:
        return False
    return not any(ip in net for net in _EXTRA_BLOCKED if net.version == ip.version)


def _check_ip(value: str, allow_private: bool) -> None:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError as exc:
        raise UnsafeUrl("niepoprawny adres IP") from exc
    if not allow_private and not is_public_ip(ip):
        raise UnsafeUrl("adres wewnętrzny lub zarezerwowany")


def validate_url(url: str, *, allow_private: bool = False) -> Target:
    """Składniowa kontrola adresu (bez DNS). Zwraca znormalizowany cel."""
    if len(url) > MAX_URL_LENGTH or any(ord(c) < 33 or ord(c) == 127 for c in url):
        raise UnsafeUrl("niepoprawny adres")
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeUrl("dozwolone tylko http i https")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise UnsafeUrl("adres nie może zawierać danych logowania")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise UnsafeUrl("brak nazwy hosta")
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError as exc:
        raise UnsafeUrl("niepoprawny port") from exc
    if port not in ALLOWED_PORTS and not allow_private:
        raise UnsafeUrl("niedozwolony port")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        internal = host == "localhost" or host.endswith((".localhost", ".local", ".internal"))
        if internal and not allow_private:
            raise UnsafeUrl("adres wewnętrzny") from None
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise UnsafeUrl("niepoprawna nazwa hosta") from exc
    else:
        _check_ip(host, allow_private)
    shown = f"[{host}]" if ":" in host else host
    default_port = 443 if parts.scheme == "https" else 80
    netloc = shown if port == default_port else f"{shown}:{port}"
    path = parts.path or "/"
    clean = f"{parts.scheme}://{netloc}{path}" + (f"?{parts.query}" if parts.query else "")
    return Target(url=clean, scheme=parts.scheme, host=host, port=port)


def resolve_public(host: str, port: int, *, allow_private: bool = False) -> list[str]:
    """Rozwiązuje nazwę i wymaga, by WSZYSTKIE adresy były publiczne (bez wyboru „lepszego”)."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeUrl("nie udało się rozwiązać nazwy hosta") from exc
    addresses: list[str] = []
    for info in infos:
        address = str(info[4][0]).split("%", 1)[0]
        _check_ip(address, allow_private)
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise UnsafeUrl("brak adresów dla hosta")
    return addresses


class GuardedBackend(httpcore.SyncBackend):
    """Sieć httpcore, która przed każdym połączeniem TCP sprawdza adres IP i łączy się z nim."""

    def __init__(self, allow_private: bool = False) -> None:
        super().__init__()
        self.allow_private = allow_private

    def connect_tcp(  # type: ignore[no-untyped-def]
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ):
        last: Exception | None = None
        for ip in resolve_public(host, port, allow_private=self.allow_private):
            try:
                # Łączymy się z zatwierdzonym IP; nazwa hosta (SNI, Host) zostaje z URL-a.
                return super().connect_tcp(ip, port, timeout, local_address, socket_options)
            except httpcore.ConnectError as exc:
                last = exc
        raise last or httpcore.ConnectError("brak adresu")


class _Stream(httpx.SyncByteStream):
    def __init__(self, inner: Iterable[bytes]) -> None:
        self._inner = inner

    def __iter__(self):  # type: ignore[no-untyped-def]
        yield from self._inner

    def close(self) -> None:
        close = getattr(self._inner, "close", None)
        if close is not None:
            close()


class GuardedTransport(httpx.BaseTransport):
    """Transport httpx na `GuardedBackend`: bez proxy z środowiska, bez HTTP/2, weryfikacja TLS."""

    def __init__(self, allow_private: bool = False) -> None:
        self._pool = httpcore.ConnectionPool(
            ssl_context=httpx.create_ssl_context(verify=True),
            max_connections=4,
            max_keepalive_connections=0,
            keepalive_expiry=0,
            http1=True,
            http2=False,
            network_backend=GuardedBackend(allow_private),
        )

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        req = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        try:
            resp = self._pool.handle_request(req)
        except httpcore.TimeoutException as exc:
            raise httpx.TimeoutException(str(exc), request=request) from exc
        except httpcore.NetworkError as exc:
            raise httpx.TransportError(str(exc), request=request) from exc
        except httpcore.ProtocolError as exc:
            raise httpx.TransportError(str(exc), request=request) from exc
        return httpx.Response(
            status_code=resp.status,
            headers=resp.headers,
            stream=_Stream(resp.stream),  # type: ignore[arg-type]
            extensions=resp.extensions,
        )

    def close(self) -> None:
        self._pool.close()
