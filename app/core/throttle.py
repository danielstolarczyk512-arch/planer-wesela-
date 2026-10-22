"""Globalny limit żądań: użytkownik (z ważnego tokena) albo prefiks IP, okno 1 minuty.

Licznik w pamięci procesu: chroni pojedynczą instancję API przed zalewem żądań (pętla
w aplikacji, skrypt). Przy wielu instancjach limit działa per instancja; wspólny licznik
(Redis) dopiero przy skalowaniu poziomym (ADR-0002). Ostrzejsze limity dla logowania,
rejestracji, RSVP i AI są osobno, w bazie (`app.core.ratelimit`).
"""

import ipaddress
import json
import time

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import decode_access_token

EXEMPT_PREFIXES = ("/health",)
_MAX_KEYS = 100_000  # ochrona pamięci przy zalewie z wielu adresów


class ThrottleMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._window = 0
        self._counts: dict[str, int] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        limit = get_settings().rate_limit_per_minute
        if scope["type"] != "http" or limit <= 0 or scope["path"].startswith(EXEMPT_PREFIXES):
            await self.app(scope, receive, send)
            return
        now = time.time()
        window = int(now // 60)
        if window != self._window or len(self._counts) > _MAX_KEYS:
            self._window, self._counts = window, {}
        key = _key(scope)
        self._counts[key] = self._counts.get(key, 0) + 1
        if self._counts[key] > limit:
            await _reject(send, retry_after=int(60 - now % 60) + 1)
            return
        await self.app(scope, receive, send)


def _key(scope: Scope) -> str:
    auth = dict(scope["headers"]).get(b"authorization", b"").decode("latin-1")
    if auth.lower().startswith("bearer "):
        try:
            user_id, _ = decode_access_token(auth[7:].strip())
            return f"u:{user_id}"
        except AppError:
            pass  # nieważny token: liczymy po adresie
    host = (scope.get("client") or ("", 0))[0]
    try:
        ip = ipaddress.ip_address(host)
        prefix = 24 if ip.version == 4 else 48
        return "ip:" + str(ipaddress.ip_network(f"{ip}/{prefix}", strict=False))
    except ValueError:
        return "ip:unknown"


async def _reject(send: Send, retry_after: int) -> None:
    body = json.dumps(
        {
            "type": "about:blank",
            "title": "Zbyt wiele żądań",
            "status": 429,
            "detail": "Spróbuj ponownie za chwilę.",
            "code": "rate_limited",
        },
        ensure_ascii=False,
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 429,
            "headers": [
                (b"content-type", b"application/problem+json"),
                (b"content-length", str(len(body)).encode()),
                (b"retry-after", str(retry_after).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
