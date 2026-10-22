"""Błędy domenowe i odpowiedzi w formacie RFC 9457 (application/problem+json)."""

from collections.abc import Mapping
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = structlog.get_logger()

PROBLEM_JSON = "application/problem+json"


class AppError(Exception):
    status: int = 400
    code: str = "bad_request"
    title: str = "Nieprawidłowe żądanie"

    def __init__(
        self,
        detail: str | None = None,
        *,
        code: str | None = None,
        headers: dict[str, str] | None = None,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(detail or self.title)
        self.detail = detail or self.title
        if code:
            self.code = code
        self.headers = headers or {}
        self.errors = errors


class Unauthorized(AppError):
    status, code, title = 401, "auth.unauthorized", "Wymagane uwierzytelnienie"

    def __init__(self, detail: str | None = None, *, code: str | None = None) -> None:
        super().__init__(detail, code=code, headers={"WWW-Authenticate": "Bearer"})


class Forbidden(AppError):
    status, code, title = 403, "forbidden", "Brak uprawnień"


class NotFound(AppError):
    status, code, title = 404, "not_found", "Nie znaleziono"


class Conflict(AppError):
    status, code, title = 409, "conflict", "Konflikt"


class PreconditionRequired(AppError):
    status, code, title = 428, "precondition.required", "Wymagany nagłówek If-Match"


class Unprocessable(AppError):
    status, code, title = 422, "validation.failed", "Błąd walidacji"


class RateLimited(AppError):
    status, code, title = 429, "rate_limited", "Zbyt wiele żądań"

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            "Spróbuj ponownie później.",
            headers={"Retry-After": str(max(1, retry_after_seconds))},
        )


def problem(
    status: int,
    title: str,
    detail: str,
    code: str,
    errors: list[dict[str, Any]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
    }
    if errors is not None:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return problem(
            exc.status, exc.title, exc.detail, exc.code, errors=exc.errors, headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Celowo bez pola "input": nie odsyłamy (i nie logujemy) wartości, np. haseł.
        errors = [
            {"loc": list(e.get("loc", ())), "msg": e.get("msg"), "type": e.get("type")}
            for e in exc.errors()
        ]
        return problem(
            422, "Błąd walidacji", "Dane wejściowe są niepoprawne.", "validation.failed", errors
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return problem(exc.status_code, str(exc.detail), str(exc.detail), code, headers=exc.headers)

    @app.exception_handler(DataError)
    async def _data_error(_: Request, exc: DataError) -> JSONResponse:
        # Dane odrzucone przez bazę (np. znak NUL w tekście, wartość poza zakresem typu).
        log.warning("db_data_error", error_type=type(exc.orig).__name__)
        return problem(
            422,
            "Błąd walidacji",
            "Dane zawierają niedozwolone znaki lub wartości.",
            "validation.invalid_value",
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", error_type=type(exc).__name__)
        return problem(500, "Błąd serwera", "Wystąpił nieoczekiwany błąd.", "internal_error")
