"""Limit rozmiaru treści żądania: zbyt duże uploady odrzucane przed wczytaniem całości."""

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings

OVERHEAD = 1024 * 1024  # nagłówki multipart i pola formularza


class _TooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = get_settings().max_upload_mb * 1024 * 1024 + OVERHEAD
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await _reject(send, limit)
            return
        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > limit:
                raise _TooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            response_started = response_started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _TooLarge:
            if not response_started:
                await _reject(send, limit)


async def _reject(send: Send, limit: int) -> None:
    mb = (limit - OVERHEAD) // (1024 * 1024)
    body = json.dumps(
        {
            "type": "about:blank",
            "title": "Plik jest zbyt duży",
            "status": 413,
            "detail": f"Maksymalny rozmiar pliku to {mb} MB.",
            "code": "document.too_large",
        },
        ensure_ascii=False,
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/problem+json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
