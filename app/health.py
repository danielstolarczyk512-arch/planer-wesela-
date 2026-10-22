from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.deps import DbSession

router = APIRouter(prefix="/health", tags=["health"])

_ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def _expected_heads() -> set[str]:
    return set(ScriptDirectory.from_config(Config(str(_ALEMBIC_INI))).get_heads())


@router.get("/live", summary="Proces działa")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/ready",
    summary="Baza dostępna i migracje aktualne",
    responses={503: {"description": "Nie gotowe"}},
)
def ready(db: DbSession) -> JSONResponse:
    try:
        current = {row[0] for row in db.execute(text("SELECT version_num FROM alembic_version"))}
    except SQLAlchemyError:
        return JSONResponse({"status": "unavailable"}, status_code=503)
    if current != _expected_heads():
        return JSONResponse({"status": "migrations_pending"}, status_code=503)
    return JSONResponse({"status": "ok"})
