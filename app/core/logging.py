"""Logi strukturalne (JSON) z request_id. Nigdy nie logujemy treści żądań ani tokenów."""

import logging
import re
import time
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.context import request_id_var
from app.core.ids import uuid7

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9\-]{8,64}$")


def configure_logging(level: str, json: bool) -> None:
    logging.basicConfig(format="%(message)s", level=level)
    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        cache_logger_on_first_use=True,
    )


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if _REQUEST_ID_RE.match(incoming) else str(uuid7())
        token = request_id_var.set(rid)
        structlog.contextvars.bind_contextvars(request_id=rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        route = request.scope.get("route")
        structlog.get_logger().info(
            "http_request",
            method=request.method,
            # szablon trasy zamiast surowej ścieżki: tokeny w URL nie trafią do logów
            route=getattr(route, "path", "unmatched"),
            status=response.status_code,
            duration_ms=round((time.perf_counter() - start) * 1000, 1),
        )
        structlog.contextvars.clear_contextvars()
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers.setdefault("Cache-Control", "no-store")
        return response
