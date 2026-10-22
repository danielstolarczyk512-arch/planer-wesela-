from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response

from app.core.deps import CurrentPrincipal, DbSession, IfMatchVersion, etag
from app.core.net import ip_prefix
from app.modules.guests import delivery, forecast, gifts, page, reserve, service
from app.modules.guests.models import Guest, Household, ReserveEntry
from app.modules.guests.schemas import (
    AnnouncementEmailIn,
    AnnouncementEmailOut,
    AnnouncementIn,
    AttendanceForecast,
    AttendanceIn,
    AttendanceStatus,
    DeliveredIn,
    DeliveryOverview,
    DeliveryPlanIn,
    Diet,
    GiftIn,
    GiftsOverview,
    GiftUpdate,
    GuestCreate,
    GuestInfoIn,
    GuestInfoOut,
    GuestOut,
    GuestPageSettings,
    GuestPageSettingsIn,
    GuestStats,
    GuestUpdate,
    HouseholdCreate,
    HouseholdOut,
    HouseholdUpdate,
    ImportIn,
    ImportOut,
    InvitationStatus,
    ReserveEntryCreate,
    ReserveEntryOut,
    ReserveEntryUpdate,
    ReserveInviteIn,
    ReserveInviteOut,
    RsvpCompanionIn,
    RsvpEmailsIn,
    RsvpEmailsOut,
    RsvpGiftReserveIn,
    RsvpLinkOut,
    RsvpQrIn,
    RsvpQrOut,
    RsvpSongIn,
    RsvpSubmit,
    RsvpView,
    RsvpWishIn,
    Side,
    WishHiddenIn,
    WishOut,
)

router = APIRouter(tags=["goście"])
public_router = APIRouter(prefix="/rsvp", tags=["RSVP (publiczne)"])

Responses = dict[int | str, dict[str, Any]]
_READ: Responses = {
    401: {"description": "Brak uwierzytelnienia"},
    404: {"description": "Nie znaleziono lub brak dostępu"},
}
_WRITE: Responses = {
    **_READ,
    403: {"description": "Rola tylko do odczytu"},
    422: {"description": "Błąd walidacji"},
}
_PATCH: Responses = {
    **_WRITE,
    409: {"description": "Konflikt wersji"},
    428: {"description": "Brak If-Match"},
}
W = "/weddings/{wedding_id}"


def guest_out(g: Guest, attendance: dict[UUID, str]) -> GuestOut:
    return GuestOut.model_validate(
        {
            "id": g.id,
            "household_id": g.household_id,
            "first_name": g.first_name,
            "last_name": g.last_name,
            "age_group": g.age_group,
            "is_plus_one": g.is_plus_one,
            "added_via_rsvp": g.added_via_rsvp,
            "dietary_preference": g.dietary_preference,
            "dietary_note": service.dietary_note(g),
            "needs_accommodation": g.needs_accommodation,
            "needs_transport": g.needs_transport,
            "notes": g.notes,
            "attendance": attendance,
            "version": g.version,
        }
    )


def _households_out(
    db: DbSession, households: list[Household], guests: dict[UUID, list[Guest]]
) -> list[HouseholdOut]:
    all_guests = [g for h in households for g in guests[h.id]]
    att = service.attendance_map(db, [g.id for g in all_guests])
    links = service.active_links(db, [h.id for h in households])
    return [
        HouseholdOut.model_validate(
            {
                "id": h.id,
                "name": h.name,
                "side": h.side,
                "group_label": h.group_label,
                "contact_email": h.contact_email,
                "contact_phone": h.contact_phone,
                "invitation_status": h.invitation_status,
                "rsvp_deadline": h.rsvp_deadline,
                "language": h.language,
                "rsvp_link_active": h.id in links,
                "rsvp_emailed_at": h.rsvp_emailed_at,
                "notes": h.notes,
                "gift_note": h.gift_note,
                "thanked": h.thanked,
                "delivery_method": h.delivery_method,
                "delivery_by": h.delivery_by,
                "delivery_place": h.delivery_place,
                "delivery_planned_on": h.delivery_planned_on,
                "delivered_on": h.delivered_on,
                "guests": [guest_out(g, att[g.id]) for g in guests[h.id]],
                "version": h.version,
            }
        )
        for h in households
    ]


def _household_out(db: DbSession, h: Household) -> HouseholdOut:
    return _households_out(db, [h], {h.id: service.household_guests(db, h.id)})[0]


def _guest_out(db: DbSession, g: Guest) -> GuestOut:
    return guest_out(g, service.attendance_map(db, [g.id])[g.id])


# --- gospodarstwa -----------------------------------------------------------------------------


@router.get(f"{W}/households", responses=_READ, summary="Gospodarstwa z gośćmi")
def list_households(
    wedding_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    side: Side | None = None,
    invitation_status: InvitationStatus | None = None,
) -> list[HouseholdOut]:
    households, guests = service.list_households(
        db, principal, wedding_id, side=side, invitation_status=invitation_status
    )
    return _households_out(db, households, guests)


@router.post(
    f"{W}/households",
    status_code=201,
    responses=_WRITE,
    summary="Nowe gospodarstwo (jedno zaproszenie)",
)
def create_household(
    wedding_id: UUID, body: HouseholdCreate, principal: CurrentPrincipal, db: DbSession
) -> HouseholdOut:
    return _household_out(
        db, service.create_household(db, principal, wedding_id, body.model_dump())
    )


@router.get(f"{W}/households/{{household_id}}", responses=_READ, summary="Gospodarstwo")
def get_household(
    wedding_id: UUID,
    household_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    response: Response,
) -> HouseholdOut:
    h = service.get_household(db, principal, wedding_id, household_id)
    response.headers["ETag"] = etag(h.version)
    return _household_out(db, h)


@router.patch(
    f"{W}/households/{{household_id}}", responses=_PATCH, summary="Edycja gospodarstwa (If-Match)"
)
def update_household(
    wedding_id: UUID,
    household_id: UUID,
    principal: CurrentPrincipal,
    body: HouseholdUpdate,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> HouseholdOut:
    h = service.update_household(
        db, principal, wedding_id, household_id, body.model_dump(exclude_unset=True), version
    )
    response.headers["ETag"] = etag(h.version)
    return _household_out(db, h)


@router.delete(
    f"{W}/households/{{household_id}}",
    status_code=204,
    responses=_WRITE,
    summary="Usunięcie gospodarstwa z gośćmi",
)
def delete_household(
    wedding_id: UUID, household_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.delete_household(db, principal, wedding_id, household_id)


@router.post(
    f"{W}/households/{{household_id}}/rsvp-link",
    status_code=201,
    responses=_WRITE,
    summary="Nowy link RSVP (poprzedni przestaje działać)",
)
def create_rsvp_link(
    wedding_id: UUID, household_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> RsvpLinkOut:
    token, url, expires = service.create_rsvp_link(db, principal, wedding_id, household_id)
    return RsvpLinkOut(token=token, url=url, expires_at=expires, qr_svg=service.qr_svg(url))


@router.delete(
    f"{W}/households/{{household_id}}/rsvp-link",
    status_code=204,
    responses=_WRITE,
    summary="Wyłączenie linku RSVP",
)
def revoke_rsvp_link(
    wedding_id: UUID, household_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.revoke_rsvp_link(db, principal, wedding_id, household_id)


# --- goście ---------------------------------------------------------------------------------


@router.get(
    f"{W}/guests",
    responses=_READ,
    summary="Lista gości (filtry: dieta, nocleg, odpowiedź na wydarzenie)",
)
def list_guests(
    wedding_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    dietary: Diet | None = None,
    needs_accommodation: bool | None = None,
    event_id: UUID | None = None,
    attendance: AttendanceStatus | None = None,
) -> list[GuestOut]:
    guests = service.list_guests(
        db,
        principal,
        wedding_id,
        dietary=dietary,
        needs_accommodation=needs_accommodation,
        event_id=event_id,
        attendance=attendance,
    )
    att = service.attendance_map(db, [g.id for g in guests])
    return [guest_out(g, att[g.id]) for g in guests]


@router.post(
    f"{W}/households/{{household_id}}/guests",
    status_code=201,
    responses=_WRITE,
    summary="Dodanie gościa do gospodarstwa",
)
def create_guest(
    wedding_id: UUID,
    household_id: UUID,
    body: GuestCreate,
    principal: CurrentPrincipal,
    db: DbSession,
) -> GuestOut:
    return _guest_out(
        db, service.create_guest(db, principal, wedding_id, household_id, body.model_dump())
    )


@router.patch(f"{W}/guests/{{guest_id}}", responses=_PATCH, summary="Edycja gościa (If-Match)")
def update_guest(
    wedding_id: UUID,
    guest_id: UUID,
    principal: CurrentPrincipal,
    body: GuestUpdate,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> GuestOut:
    g = service.update_guest(
        db, principal, wedding_id, guest_id, body.model_dump(exclude_unset=True), version
    )
    response.headers["ETag"] = etag(g.version)
    return _guest_out(db, g)


@router.delete(
    f"{W}/guests/{{guest_id}}", status_code=204, responses=_WRITE, summary="Usunięcie gościa"
)
def delete_guest(
    wedding_id: UUID, guest_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    service.delete_guest(db, principal, wedding_id, guest_id)


@router.put(
    f"{W}/guests/{{guest_id}}/attendance/{{event_id}}",
    responses=_WRITE,
    summary="Obecność gościa na wydarzeniu (wpisana przez parę)",
)
def set_attendance(
    wedding_id: UUID,
    guest_id: UUID,
    event_id: UUID,
    body: AttendanceIn,
    principal: CurrentPrincipal,
    db: DbSession,
) -> GuestOut:
    return _guest_out(
        db, service.set_attendance(db, principal, wedding_id, guest_id, event_id, body.status)
    )


@router.get(
    f"{W}/guests/stats",
    responses=_READ,
    summary="Statystyki: liczby, diety, noclegi, odpowiedzi per wydarzenie",
)
def guest_stats(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> GuestStats:
    return GuestStats.model_validate(service.stats(db, principal, wedding_id))


@router.post(
    f"{W}/guests/import",
    responses=_WRITE,
    summary="Import gości z CSV (najpierw dry_run, potem zapis)",
)
def import_guests(
    wedding_id: UUID, body: ImportIn, principal: CurrentPrincipal, db: DbSession
) -> ImportOut:
    return ImportOut.model_validate(
        service.import_csv(db, principal, wedding_id, body.csv, body.dry_run)
    )


# --- strona dla gości i wysyłka linków -------------------------------------------------------


def _info_out(info: Any) -> GuestInfoOut:
    if info is None:
        return GuestInfoOut(version=0, updated_at=None)
    return GuestInfoOut.model_validate(info, from_attributes=True)


@router.get(
    f"{W}/guest-info/preview",
    responses=_READ,
    summary="Podgląd strony gościa (fikcyjna rodzina, informacje także przed publikacją)",
)
def guest_page_preview(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> RsvpView:
    return RsvpView.model_validate(service.guest_page_preview(db, principal, wedding_id))


@router.get(f"{W}/guest-info", responses=_READ, summary="Strona informacyjna dla gości")
def get_guest_info(
    wedding_id: UUID, principal: CurrentPrincipal, db: DbSession, response: Response
) -> GuestInfoOut:
    out = _info_out(service.get_guest_info(db, principal, wedding_id))
    response.headers["ETag"] = etag(out.version)
    return out


@router.put(
    f"{W}/guest-info",
    responses=_PATCH,
    summary='Zapis strony dla gości (If-Match; pierwszy zapis: "0")',
)
def save_guest_info(
    wedding_id: UUID,
    body: GuestInfoIn,
    principal: CurrentPrincipal,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> GuestInfoOut:
    info = service.save_guest_info(db, principal, wedding_id, body.model_dump(), version)
    response.headers["ETag"] = etag(info.version)
    return _info_out(info)


@router.get(
    f"{W}/guests/export.csv",
    responses=_READ,
    response_class=Response,
    summary="Lista gości do arkusza (CSV, średnik, UTF-8 z BOM — polski Excel)",
)
def export_guests_csv(
    wedding_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    include_notes: bool = False,
) -> Response:
    data = service.export_csv(db, principal, wedding_id, include_notes=include_notes)
    return Response(
        content=data.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="goscie.csv"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    f"{W}/rsvp-emails",
    responses=_WRITE,
    summary="Linki RSVP e-mailem do rodzin bez odpowiedzi (dry_run = podgląd)",
)
def rsvp_emails(
    wedding_id: UUID, body: RsvpEmailsIn, principal: CurrentPrincipal, db: DbSession
) -> RsvpEmailsOut:
    return RsvpEmailsOut.model_validate(
        service.rsvp_emails(
            db,
            principal,
            wedding_id,
            dry_run=body.dry_run,
            include_with_link=body.include_with_link,
        )
    )


@router.post(
    f"{W}/rsvp-qr",
    responses=_WRITE,
    summary="Karty z kodem QR do druku: nowe linki RSVP (dry_run = podgląd, bez linków)",
)
def rsvp_qr(
    wedding_id: UUID, body: RsvpQrIn, principal: CurrentPrincipal, db: DbSession
) -> RsvpQrOut:
    return RsvpQrOut.model_validate(
        service.rsvp_qr(
            db,
            principal,
            wedding_id,
            household_ids=body.household_ids,
            include_with_link=body.include_with_link,
            dry_run=body.dry_run,
        )
    )


# --- lista rezerwowa i prognoza frekwencji -------------------------------------------------


def _reserve_out(e: ReserveEntry) -> ReserveEntryOut:
    return ReserveEntryOut.model_validate(e, from_attributes=True)


@router.get(
    f"{W}/attendance-forecast",
    responses=_READ,
    summary="Prognoza frekwencji: ilu gości przyjdzie, minimum sali, lista rezerwowa",
)
def attendance_forecast(
    wedding_id: UUID,
    principal: CurrentPrincipal,
    db: DbSession,
    pending_rate: Annotated[float, Query(ge=0.3, le=1.0)] = forecast.DEFAULT_PENDING_RATE,
    maybe_rate: Annotated[float, Query(ge=0.0, le=1.0)] = forecast.DEFAULT_MAYBE_RATE,
) -> AttendanceForecast:
    return AttendanceForecast.model_validate(
        forecast.build(db, principal, wedding_id, pending_rate=pending_rate, maybe_rate=maybe_rate)
    )


@router.get(f"{W}/reserve", responses=_READ, summary="Lista rezerwowa (w kolejności)")
def list_reserve(
    wedding_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> list[ReserveEntryOut]:
    return [_reserve_out(e) for e in reserve.list_entries(db, principal, wedding_id)]


@router.post(
    f"{W}/reserve", status_code=201, responses=_WRITE, summary="Nowa osoba na liście rezerwowej"
)
def create_reserve(
    wedding_id: UUID, body: ReserveEntryCreate, principal: CurrentPrincipal, db: DbSession
) -> ReserveEntryOut:
    return _reserve_out(reserve.create_entry(db, principal, wedding_id, body.model_dump()))


@router.patch(
    f"{W}/reserve/{{entry_id}}",
    responses=_PATCH,
    summary="Edycja lub zmiana kolejności na liście rezerwowej (If-Match)",
)
def update_reserve(
    wedding_id: UUID,
    entry_id: UUID,
    principal: CurrentPrincipal,
    body: ReserveEntryUpdate,
    version: IfMatchVersion,
    db: DbSession,
    response: Response,
) -> ReserveEntryOut:
    e = reserve.update_entry(
        db, principal, wedding_id, entry_id, body.model_dump(exclude_unset=True), version
    )
    response.headers["ETag"] = etag(e.version)
    return _reserve_out(e)


@router.delete(
    f"{W}/reserve/{{entry_id}}",
    status_code=204,
    responses=_WRITE,
    summary="Usunięcie z listy rezerwowej (gospodarstwo po zaproszeniu zostaje)",
)
def delete_reserve(
    wedding_id: UUID, entry_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    reserve.delete_entry(db, principal, wedding_id, entry_id)


@router.post(
    f"{W}/reserve/{{entry_id}}/invite",
    status_code=201,
    responses={**_WRITE, 409: {"description": "Osoba jest już zaproszona"}},
    summary="Zaproszenie z listy rezerwowej: tworzy gospodarstwo z gośćmi",
)
def invite_reserve(
    wedding_id: UUID,
    entry_id: UUID,
    body: ReserveInviteIn,
    principal: CurrentPrincipal,
    db: DbSession,
) -> ReserveInviteOut:
    e, household_id = reserve.invite(db, principal, wedding_id, entry_id, body.model_dump())
    return ReserveInviteOut(entry=_reserve_out(e), household_id=household_id)


# --- wręczanie zaproszeń ------------------------------------------------------------------


@router.get(
    f"{W}/invitation-delivery",
    responses=_READ,
    summary="Wręczanie zaproszeń osobiście: objazdy po miejscowościach i postęp",
)
def invitation_delivery(
    wedding_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> DeliveryOverview:
    return DeliveryOverview.model_validate(delivery.overview(db, principal, wedding_id))


@router.post(
    f"{W}/invitation-delivery/plan",
    responses=_WRITE,
    summary="Plan objazdu: dzień i kto wręcza dla wielu zaproszeń",
)
def plan_delivery(
    wedding_id: UUID, body: DeliveryPlanIn, principal: CurrentPrincipal, db: DbSession
) -> DeliveryOverview:
    delivery.plan(db, principal, wedding_id, body.model_dump(exclude_unset=True))
    return DeliveryOverview.model_validate(delivery.overview(db, principal, wedding_id))


@router.post(
    f"{W}/invitation-delivery/delivered",
    responses=_WRITE,
    summary="Oznacz zaproszenia jako wręczone",
)
def mark_delivered(
    wedding_id: UUID, body: DeliveredIn, principal: CurrentPrincipal, db: DbSession
) -> DeliveryOverview:
    delivery.mark_delivered(db, principal, wedding_id, body.household_ids, body.delivered_on)
    return DeliveryOverview.model_validate(delivery.overview(db, principal, wedding_id))


# --- publiczne RSVP -------------------------------------------------------------------------

_RSVP: Responses = {
    404: {"description": "Link nieprawidłowy lub wygasł"},
    429: {"description": "Zbyt wiele żądań"},
}


@public_router.get(
    "/{token}", responses=_RSVP, summary="Formularz RSVP gospodarstwa (bez logowania)"
)
def rsvp_view(token: str, request: Request, db: DbSession) -> RsvpView:
    return RsvpView.model_validate(service.rsvp_view(db, token, ip_prefix(request)))


@public_router.put(
    "/{token}",
    responses={
        **_RSVP,
        409: {"description": "Termin minął"},
        422: {"description": "Błąd walidacji"},
    },
    summary="Odpowiedź RSVP gospodarstwa",
)
def rsvp_submit(token: str, body: RsvpSubmit, request: Request, db: DbSession) -> RsvpView:
    return RsvpView.model_validate(
        service.rsvp_submit(db, token, ip_prefix(request), body.model_dump())
    )


@public_router.post(
    "/{token}/companions",
    status_code=201,
    responses={**_RSVP, 409: {"description": "Termin minął"}},
    summary="Gość dopisuje osobę towarzyszącą",
)
def rsvp_add_companion(
    token: str, body: RsvpCompanionIn, request: Request, db: DbSession
) -> RsvpView:
    return RsvpView.model_validate(
        service.rsvp_add_companion(db, token, ip_prefix(request), body.model_dump())
    )


@public_router.put(
    "/{token}/gifts/{gift_id}",
    responses={**_RSVP, 409: {"description": "Prezent już zarezerwowany"}},
    summary="Gość rezerwuje prezent albo zwalnia swoją rezerwację",
)
def rsvp_reserve_gift(
    token: str, gift_id: UUID, body: RsvpGiftReserveIn, request: Request, db: DbSession
) -> RsvpView:
    return RsvpView.model_validate(
        service.rsvp_reserve_gift(db, token, ip_prefix(request), gift_id, body.reserved)
    )


@public_router.post(
    "/{token}/wishes",
    status_code=201,
    responses={
        **_RSVP,
        409: {"description": "Limit wpisów"},
        422: {"description": "Błąd walidacji"},
    },
    summary="Gość zostawia życzenia (księga życzeń)",
)
def rsvp_add_wish(token: str, body: RsvpWishIn, request: Request, db: DbSession) -> RsvpView:
    return RsvpView.model_validate(
        service.rsvp_add_wish(db, token, ip_prefix(request), body.model_dump())
    )


@public_router.post(
    "/{token}/songs",
    status_code=201,
    responses={
        **_RSVP,
        409: {"description": "Termin minął albo limit propozycji"},
        422: {"description": "Błąd walidacji"},
    },
    summary="Gość proponuje utwór (para zatwierdza)",
)
def rsvp_suggest_song(token: str, body: RsvpSongIn, request: Request, db: DbSession) -> RsvpView:
    return RsvpView.model_validate(
        service.rsvp_suggest_song(db, token, ip_prefix(request), body.model_dump())
    )


@public_router.delete(
    "/{token}/companions/{guest_id}",
    responses={**_RSVP, 409: {"description": "Termin minął"}},
    summary="Gość usuwa dopisaną przez siebie osobę towarzyszącą",
)
def rsvp_remove_companion(token: str, guest_id: UUID, request: Request, db: DbSession) -> RsvpView:
    return RsvpView.model_validate(
        service.rsvp_remove_companion(db, token, ip_prefix(request), guest_id)
    )


# --- strona gościa: stół, komunikat, księga życzeń ----------------------------------------------

GP = f"{W}/guest-page"


@router.get(GP, responses=_READ, summary="Ustawienia strony gościa: stół, życzenia, komunikat")
def guest_page_settings(
    wedding_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> GuestPageSettings:
    return GuestPageSettings.model_validate(page.settings(db, principal, wedding_id))


@router.put(GP, responses=_WRITE, summary="Pokaż stół gościom / włącz księgę życzeń")
def save_guest_page_settings(
    wedding_id: UUID, body: GuestPageSettingsIn, principal: CurrentPrincipal, db: DbSession
) -> GuestPageSettings:
    return GuestPageSettings.model_validate(
        page.save_settings(db, principal, wedding_id, body.model_dump())
    )


@router.put(f"{GP}/announcement", responses=_WRITE, summary="Komunikat dla gości (pusty usuwa)")
def save_announcement(
    wedding_id: UUID, body: AnnouncementIn, principal: CurrentPrincipal, db: DbSession
) -> GuestPageSettings:
    return GuestPageSettings.model_validate(
        page.save_announcement(db, principal, wedding_id, body.text)
    )


@router.post(
    f"{GP}/announcement/email",
    responses={**_WRITE, 409: {"description": "Brak komunikatu albo już wysłany"}},
    summary="Komunikat e-mailem do rodzin z adresem (podgląd albo wysyłka, raz)",
)
def email_announcement(
    wedding_id: UUID, body: AnnouncementEmailIn, principal: CurrentPrincipal, db: DbSession
) -> AnnouncementEmailOut:
    return AnnouncementEmailOut.model_validate(
        page.email_announcement(db, principal, wedding_id, dry_run=body.dry_run)
    )


@router.get(f"{W}/wishes", responses=_READ, summary="Księga życzeń")
def list_wishes(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> list[WishOut]:
    return [WishOut.model_validate(w) for w in page.wishes(db, principal, wedding_id)]


@router.put(f"{W}/wishes/{{wish_id}}/hidden", responses=_WRITE, summary="Ukrycie wpisu")
def hide_wish(
    wedding_id: UUID, wish_id: UUID, body: WishHiddenIn, principal: CurrentPrincipal, db: DbSession
) -> list[WishOut]:
    page.set_hidden(db, principal, wedding_id, wish_id, body.hidden)
    return [WishOut.model_validate(w) for w in page.wishes(db, principal, wedding_id)]


@router.delete(
    f"{W}/wishes/{{wish_id}}", status_code=204, responses=_WRITE, summary="Usunięcie wpisu"
)
def delete_wish(
    wedding_id: UUID, wish_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    page.delete_wish(db, principal, wedding_id, wish_id)


# --- lista prezentów (pomysły pary) -------------------------------------------------------------

GF = f"{W}/gifts"


@router.get(GF, responses=_READ, summary="Lista prezentów i rezerwacje gości")
def list_gifts(wedding_id: UUID, principal: CurrentPrincipal, db: DbSession) -> GiftsOverview:
    return GiftsOverview.model_validate(gifts.overview(db, principal, wedding_id))


@router.post(GF, status_code=201, responses=_WRITE, summary="Nowy pomysł na prezent")
def create_gift(
    wedding_id: UUID, body: GiftIn, principal: CurrentPrincipal, db: DbSession
) -> GiftsOverview:
    gifts.create(db, principal, wedding_id, body.model_dump())
    return GiftsOverview.model_validate(gifts.overview(db, principal, wedding_id))


@router.patch(
    f"{GF}/{{gift_id}}",
    responses={**_WRITE, 428: {"description": "Brak If-Match"}},
    summary="Edycja pomysłu (If-Match)",
)
def update_gift(
    wedding_id: UUID,
    gift_id: UUID,
    body: GiftUpdate,
    principal: CurrentPrincipal,
    version: IfMatchVersion,
    db: DbSession,
) -> GiftsOverview:
    gifts.update_idea(
        db, principal, wedding_id, gift_id, body.model_dump(exclude_unset=True), version
    )
    return GiftsOverview.model_validate(gifts.overview(db, principal, wedding_id))


@router.delete(f"{GF}/{{gift_id}}", status_code=204, responses=_WRITE, summary="Usunięcie pomysłu")
def delete_gift(
    wedding_id: UUID, gift_id: UUID, principal: CurrentPrincipal, db: DbSession
) -> None:
    gifts.delete(db, principal, wedding_id, gift_id)
