from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from app.core.deps import CurrentPrincipal, DbSession
from app.core.net import ip_prefix
from app.modules.calendar import service

router = APIRouter(tags=["kalendarz"])
public_router = APIRouter(prefix="/calendar", tags=["kalendarz (publiczne)"])

Responses = dict[int | str, dict[str, Any]]
_READ: Responses = {
    401: {"description": "Brak uwierzytelnienia"},
    404: {"description": "Nie znaleziono lub brak dostępu"},
}
W = "/weddings/{wedding_id}"


class CalendarEntry(BaseModel):
    kind: Literal["task", "payment", "event", "wedding", "reminder"]
    date: date
    time: str | None = Field(description="Godzina (czas polski) dla wydarzeń")
    title: str
    ref_id: UUID
    done: bool
    overdue: bool
    link: str | None = Field(
        default=None, description="Przypomnienie: ekran w weselu (np. formalnosci)"
    )


class FeedStatus(BaseModel):
    active: bool
    created_at: datetime | None
    last_used_at: datetime | None


class FeedCreated(BaseModel):
    token: str = Field(description="Widoczny tylko raz; adres: /api/v1/calendar/{token}.ics")
    note: str = (
        "Adres jest prywatny: każdy, kto go zna, zobaczy terminy zadań i płatności (bez kwot). "
        "Kalendarz zewnętrzny pobiera dane przez internet. Adres można w każdej chwili wyłączyć."
    )


@router.get(
    f"{W}/calendar",
    responses=_READ,
    summary="Kalendarz: zadania, płatności i wydarzenia w zakresie dat",
)
def get_calendar(
    wedding_id: UUID, start: date, end: date, principal: CurrentPrincipal, db: DbSession
) -> list[CalendarEntry]:
    return [
        CalendarEntry.model_validate(e)
        for e in service.calendar(db, principal, wedding_id, start, end)
    ]


@router.get(f"{W}/calendar-feed", responses=_READ, summary="Czy mam aktywny adres kalendarza")
def feed_status(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> FeedStatus:
    feed = service.feed_status(db, principal, wedding_id)
    return FeedStatus(
        active=feed is not None,
        created_at=feed.created_at if feed else None,
        last_used_at=feed.last_used_at if feed else None,
    )


@router.post(
    f"{W}/calendar-feed",
    status_code=201,
    responses=_READ,
    summary="Nowy prywatny adres kalendarza ICS (poprzedni przestaje działać)",
)
def create_feed(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> FeedCreated:
    return FeedCreated(token=service.create_feed(db, principal, wedding_id))


@router.delete(
    f"{W}/calendar-feed", status_code=204, responses=_READ, summary="Wyłącz adres kalendarza"
)
def revoke_feed(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> None:
    service.revoke_feed(db, principal, wedding_id)


@public_router.get(
    "/{token}.ics",
    responses={404: {"description": "Adres nieprawidłowy lub wyłączony"}, 429: {}},
    summary="Plik kalendarza (ICS) do subskrypcji w Google/Apple/Outlook",
    response_class=Response,
)
def feed_ics(token: str, request: Request, db: DbSession) -> Response:
    body = service.feed_ics(db, token, ip_prefix(request))
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Cache-Control": "private, max-age=900", "X-Robots-Tag": "noindex"},
    )
