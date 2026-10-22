"""Bieżąca data w strefie wesela (Polska). Jedno miejsce, łatwe do podmiany w testach."""

from datetime import date, datetime
from typing import overload
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")


def today() -> date:
    return datetime.now(WARSAW).date()


@overload
def local(value: datetime) -> datetime: ...
@overload
def local(value: None) -> None: ...
def local(value: datetime | None) -> datetime | None:
    """Godzina w czasie polskim: API zawsze zwraca terminy wydarzeń w tej samej strefie."""
    return value.astimezone(WARSAW) if value is not None else None
