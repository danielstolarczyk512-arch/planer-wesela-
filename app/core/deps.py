from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import PreconditionRequired, Unauthorized, Unprocessable
from app.core.security import decode_access_token
from app.modules.identity.service import Principal, authenticate

_bearer = HTTPBearer(auto_error=False, description="Access token z /auth/login")

DbSession = Annotated[Session, Depends(get_db)]


def get_principal(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise Unauthorized()
    user_id, session_id = decode_access_token(credentials.credentials)
    return authenticate(db, user_id, session_id)


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def required_version(
    if_match: Annotated[
        str | None, Header(description='Wersja zasobu z nagłówka ETag, np. "3"')
    ] = None,
) -> int:
    """Optymistyczne blokowanie: PATCH wymaga If-Match z wersją z ETag."""
    if if_match is None:
        raise PreconditionRequired()
    raw = if_match.strip().removeprefix("W/").strip('"')
    try:
        return int(raw)
    except ValueError as exc:
        raise Unprocessable(
            "Nieprawidłowy nagłówek If-Match.", code="precondition.invalid"
        ) from exc


IfMatchVersion = Annotated[int, Depends(required_version)]


def etag(version: int) -> str:
    return f'"{version}"'
