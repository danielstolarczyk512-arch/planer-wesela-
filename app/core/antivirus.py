"""Skanowanie plików przez ClamAV (clamd) — osobny proces/kontener, rozmowa przez TCP.

ClamAV jest na licencji GPL, dlatego działa wyłącznie jako osobna usługa sieciowa (ADR-0006);
aplikacja nie linkuje jego kodu. Klient to kilkanaście linii protokołu `INSTREAM`
(biblioteka standardowa, bez dodatkowych zależności):

    zINSTREAM\\0  →  [4 bajty długości (big-endian) + porcja danych]...  →  [0000]
    ←  "stream: OK\\0"  |  "stream: <sygnatura> FOUND\\0"  |  "... ERROR\\0"
"""

import socket
import struct
from dataclasses import dataclass

from app.core.config import get_settings

CHUNK = 64 * 1024


class ScannerUnavailable(Exception):
    """Brak połączenia ze skanerem albo błąd po jego stronie — plik czeka na ponowienie."""


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    signature: str | None = None


def enabled() -> bool:
    return bool(get_settings().clamav_host)


def scan(data: bytes) -> ScanResult:
    s = get_settings()
    if not s.clamav_host:
        raise ScannerUnavailable("Skaner nie jest skonfigurowany (WP_CLAMAV_HOST).")
    try:
        with socket.create_connection(
            (s.clamav_host, s.clamav_port), timeout=s.clamav_timeout_seconds
        ) as conn:
            conn.sendall(b"zINSTREAM\0")
            for start in range(0, len(data), CHUNK):
                chunk = data[start : start + CHUNK]
                conn.sendall(struct.pack(">I", len(chunk)) + chunk)
            conn.sendall(struct.pack(">I", 0))
            reply = _read_reply(conn)
    except OSError as exc:  # odmowa połączenia, przekroczony czas, zerwane połączenie
        raise ScannerUnavailable(type(exc).__name__) from exc
    return parse_reply(reply)


def _read_reply(conn: socket.socket) -> str:
    buf = b""
    while not buf.endswith(b"\0"):
        part = conn.recv(4096)
        if not part:
            break
        buf += part
    return buf.rstrip(b"\0").decode("utf-8", "replace").strip()


def parse_reply(reply: str) -> ScanResult:
    # Format: "stream: OK" albo "stream: Win.Test.EICAR_HDB-1 FOUND"; wszystko inne to błąd.
    body = reply.split(":", 1)[1].strip() if ":" in reply else reply
    if body == "OK":
        return ScanResult(clean=True)
    if body.endswith(" FOUND"):
        return ScanResult(clean=False, signature=body.removesuffix(" FOUND").strip()[:200])
    # Np. "INSTREAM size limit exceeded. ERROR" — nie przepuszczamy, ponawiamy/zgłaszamy.
    raise ScannerUnavailable(f"Odpowiedź skanera: {body[:200]}")
