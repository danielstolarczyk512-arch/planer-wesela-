"""Kontekst żądania (request_id) dostępny dla logów i audytu."""

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
