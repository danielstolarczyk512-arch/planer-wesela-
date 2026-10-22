from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.core import clock
from app.core.clock import local
from app.core.deps import CurrentPrincipal, DbSession, IfMatchVersion, etag
from app.core.errors import Unprocessable
from app.core.schemas import Page
from app.modules.identity.models import User
from app.modules.workspace import dates, service
from app.modules.workspace.models import Event, Wedding, WeddingInvitation, WeddingMember
from app.modules.workspace.schemas import (
    CeremonyType,
    DateCheck,
    DateCheckOut,
    EventCreate,
    EventOut,
    EventUpdate,
    InvitationAccept,
    InvitationCreate,
    InvitationOut,
    MemberOut,
    MemberUpdate,
    WeddingCreate,
    WeddingOut,
    WeddingUpdate,
)

router = APIRouter(tags=["wesela"])

Responses = dict[int | str, dict[str, Any]]

_COMMON: Responses = {
    401: {"description": "Brak uwierzytelnienia"},
    404: {"description": "Nie znaleziono lub brak dostępu"},
}
_WRITE: Responses = {
    **_COMMON,
    403: {"description": "Rola nie pozwala na zapis"},
    422: {"description": "Błąd walidacji"},
}
_PATCH: Responses = {
    **_WRITE,
    409: {"description": "Konflikt wersji (If-Match)"},
    428: {"description": "Brak nagłówka If-Match"},
}


def _wedding_out(wedding: Wedding, role: str) -> WeddingOut:
    return WeddingOut.model_validate(service.wedding_to_dict(wedding, role))


def _event_out(e: Event) -> EventOut:
    return EventOut(
        id=e.id,
        kind=e.kind,
        name=e.name,
        starts_at=local(e.starts_at),
        ends_at=local(e.ends_at),
        address=e.address,
        notes=e.notes,
        version=e.version,
    )


def _member_out(m: WeddingMember, u: User) -> MemberOut:
    return MemberOut.model_validate(
        {
            "user_id": m.user_id,
            "display_name": u.display_name,
            "email": u.email,
            "role": m.role,
            "joined_at": m.joined_at,
            "funder_id": m.funder_id,
        }
    )


def _invitation_out(i: WeddingInvitation) -> InvitationOut:
    return InvitationOut(
        id=i.id,
        email=i.email,
        role=i.role,
        funder_id=i.funder_id,
        created_at=i.created_at,
        expires_at=i.expires_at,
        accepted_at=i.accepted_at,
        revoked_at=i.revoked_at,
    )


# --- wesela -------------------------------------------------------------------------


@router.post(
    "/weddings",
    status_code=status.HTTP_201_CREATED,
    responses=_WRITE,
    summary="Utworzenie wesela (twórca zostaje właścicielem)",
)
def create_wedding(
    body: WeddingCreate, principal: CurrentPrincipal, db: DbSession, response: Response
) -> WeddingOut:
    wedding = service.create_wedding(db, principal, body.model_dump(mode="python"))
    response.headers["ETag"] = etag(wedding.version)
    return _wedding_out(wedding, "owner")


@router.get(
    "/date-check",
    responses={401: {"description": "Brak uwierzytelnienia"}},
    summary="Porównanie dat ślubu: święta, Adwent/Wielki Post, sezon, zachód słońca",
)
def date_check(
    principal: CurrentPrincipal,
    dates_: Annotated[list[date], Query(alias="date", min_length=1, max_length=6)],
    ceremony_type: CeremonyType = "undecided",
    city: Annotated[str | None, Query(max_length=64)] = None,
) -> DateCheckOut:
    # Uwierzytelnienie wymagane (principal), ale bez wesela — działa też przed jego założeniem.
    if any(not dates.MIN_YEAR <= d.year <= dates.MAX_YEAR for d in dates_):
        raise Unprocessable(
            f"Rok musi być od {dates.MIN_YEAR} do {dates.MAX_YEAR}.", code="date_check.out_of_range"
        )
    chosen, now = dates.match_city(city), clock.today()
    return DateCheckOut(
        city=chosen,
        cities=sorted(dates.CITIES),
        dates=[
            DateCheck(**dates.check(d, ceremony_type=ceremony_type, city=chosen, today=now))
            for d in dates_
        ],
    )


@router.get("/weddings", responses=_COMMON, summary="Moje wesela")
def list_weddings(
    principal: CurrentPrincipal,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: Annotated[str | None, Query(max_length=64)] = None,
) -> Page[WeddingOut]:
    rows, next_cursor = service.list_weddings(db, principal, limit=limit, cursor=cursor)
    return Page[WeddingOut](items=[_wedding_out(w, r) for w, r in rows], next_cursor=next_cursor)


@router.get("/weddings/{wedding_id}", responses=_COMMON, summary="Szczegóły wesela (ETag)")
def get_wedding(
    wedding_id: UUID, principal: CurrentPrincipal, db: DbSession, response: Response
) -> WeddingOut:
    wedding, role = service.get_wedding(db, principal, wedding_id)
    response.headers["ETag"] = etag(wedding.version)
    return _wedding_out(wedding, role)


@router.patch("/weddings/{wedding_id}", responses=_PATCH, summary="Edycja wesela (wymaga If-Match)")
def update_wedding(
    wedding_id: UUID,
    principal: CurrentPrincipal,  # przed If-Match: brak tokena → 401, nie 428
    body: WeddingUpdate,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> WeddingOut:
    wedding, role = service.update_wedding(
        db, principal, wedding_id, body.model_dump(mode="python", exclude_unset=True), version
    )
    response.headers["ETag"] = etag(wedding.version)
    return _wedding_out(wedding, role)


@router.delete(
    "/weddings/{wedding_id}",
    status_code=204,
    responses={**_COMMON, 403: {"description": "Tylko właściciel"}},
    summary="Trwałe usunięcie wesela ze wszystkimi danymi",
)
def delete_wedding(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> None:
    service.delete_wedding(db, principal, wedding_id)


# --- wydarzenia ----------------------------------------------------------------------


@router.get(
    "/weddings/{wedding_id}/events",
    responses=_COMMON,
    summary="Wydarzenia (ceremonia, przyjęcie, poprawiny)",
)
def list_events(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> list[EventOut]:
    return [_event_out(e) for e in service.list_events(db, principal, wedding_id)]


@router.post(
    "/weddings/{wedding_id}/events", status_code=201, responses=_WRITE, summary="Dodanie wydarzenia"
)
def create_event(
    wedding_id: UUID, body: EventCreate, principal: CurrentPrincipal, db: DbSession
) -> EventOut:
    return _event_out(service.create_event(db, principal, wedding_id, body.model_dump()))


@router.get(
    "/weddings/{wedding_id}/events/{event_id}", responses=_COMMON, summary="Szczegóły wydarzenia"
)
def get_event(
    wedding_id: UUID,
    event_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    response: Response,
) -> EventOut:
    event = service.get_event(db, principal, wedding_id, event_id)
    response.headers["ETag"] = etag(event.version)
    return _event_out(event)


@router.patch(
    "/weddings/{wedding_id}/events/{event_id}",
    responses=_PATCH,
    summary="Edycja wydarzenia (wymaga If-Match)",
)
def update_event(
    wedding_id: UUID,
    event_id: UUID,
    principal: CurrentPrincipal,
    body: EventUpdate,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> EventOut:
    event = service.update_event(
        db, principal, wedding_id, event_id, body.model_dump(exclude_unset=True), version
    )
    response.headers["ETag"] = etag(event.version)
    return _event_out(event)


@router.delete(
    "/weddings/{wedding_id}/events/{event_id}",
    status_code=204,
    responses=_WRITE,
    summary="Usunięcie wydarzenia",
)
def delete_event(
    wedding_id: UUID, event_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.delete_event(db, principal, wedding_id, event_id)


# --- członkowie i zaproszenia ----------------------------------------------------------


@router.get("/weddings/{wedding_id}/members", responses=_COMMON, summary="Członkowie wesela")
def list_members(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> list[MemberOut]:
    return [_member_out(m, u) for m, u in service.list_members(db, principal, wedding_id)]


@router.patch(
    "/weddings/{wedding_id}/members/{user_id}",
    responses={**_WRITE, 409: {"description": "Ostatni właściciel"}},
    summary="Zmiana roli członka (tylko właściciel)",
)
def change_member_role(
    wedding_id: UUID,
    user_id: UUID,
    body: MemberUpdate,
    principal: CurrentPrincipal,
    db: DbSession,
) -> MemberOut:
    member, user = service.change_member_role(
        db, principal, wedding_id, user_id, body.role, funder_id=body.funder_id
    )
    return _member_out(member, user)


@router.delete(
    "/weddings/{wedding_id}/members/{user_id}",
    status_code=204,
    responses={**_WRITE, 409: {"description": "Ostatni właściciel"}},
    summary="Usunięcie członka lub opuszczenie wesela (własne user_id)",
)
def remove_member(
    wedding_id: UUID, user_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.remove_member(db, principal, wedding_id, user_id)


@router.get(
    "/weddings/{wedding_id}/invitations", responses=_WRITE, summary="Zaproszenia (tylko właściciel)"
)
def list_invitations(
    wedding_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> list[InvitationOut]:
    return [_invitation_out(i) for i in service.list_invitations(db, principal, wedding_id)]


@router.post(
    "/weddings/{wedding_id}/invitations",
    status_code=201,
    responses={
        **_WRITE,
        409: {"description": "Za dużo oczekujących zaproszeń"},
        429: {"description": "Limit zaproszeń"},
    },
    summary="Zaproszenie partnera lub współpracownika e-mailem",
)
def create_invitation(
    wedding_id: UUID, body: InvitationCreate, principal: CurrentPrincipal, db: DbSession
) -> InvitationOut:
    return _invitation_out(
        service.create_invitation(
            db, principal, wedding_id, email=body.email, role=body.role, funder_id=body.funder_id
        )
    )


@router.delete(
    "/weddings/{wedding_id}/invitations/{invitation_id}",
    status_code=204,
    responses=_WRITE,
    summary="Wycofanie zaproszenia",
)
def revoke_invitation(
    wedding_id: UUID, invitation_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.revoke_invitation(db, principal, wedding_id, invitation_id)


@router.post(
    "/invitations/accept",
    responses=_COMMON,
    summary="Przyjęcie zaproszenia (konto z adresem z zaproszenia)",
)
def accept_invitation(
    body: InvitationAccept, principal: CurrentPrincipal, db: DbSession
) -> WeddingOut:
    wedding, role = service.accept_invitation(db, principal, body.token)
    return _wedding_out(wedding, role)
