from datetime import date, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, BaseModel, EmailStr, Field, model_validator

from app.core.schemas import Money, PatchModel

Side = Literal["bride", "groom", "both", "other"]
InvitationStatus = Literal["not_sent", "sent", "delivered"]
DeliveryMethod = Literal["in_person", "post", "online", "other"]
Language = Literal["pl", "en"]
AgeGroup = Literal["adult", "teen", "child", "infant"]
Diet = Literal["standard", "vegetarian", "vegan", "gluten_free", "other"]
AttendanceStatus = Literal["pending", "attending", "declined", "maybe"]
Email = Annotated[EmailStr, AfterValidator(lambda v: v.strip().lower())]
Phone = Annotated[str, Field(min_length=5, max_length=32, pattern=r"^[0-9+()\- ]+$")]

DIETARY_NOTE_HELP = (
    "Uwagi dietetyczne mogą zawierać dane o zdrowiu (np. alergie). Wpisujcie tylko to, co "
    "potrzebne kuchni. Dane są szyfrowane i usuwane po weselu."
)


class HouseholdCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150, examples=["Państwo Kowalscy z dziećmi"])
    side: Side = "both"
    group_label: str | None = Field(default=None, max_length=80, examples=["Rodzina Ani"])
    contact_email: Email | None = None
    contact_phone: Phone | None = None
    invitation_status: InvitationStatus = "not_sent"
    rsvp_deadline: date | None = None
    language: Language | None = Field(
        default=None,
        description="Język e-maila RSVP i strony; puste = automatycznie (przeglądarka gościa)",
    )
    notes: str | None = Field(default=None, max_length=2000)
    delivery_method: DeliveryMethod | None = Field(
        default=None, description="Jak trafi zaproszenie (osobiście, pocztą, online)"
    )
    delivery_by: str | None = Field(default=None, max_length=80, examples=["Ania i mama"])
    delivery_place: str | None = Field(
        default=None, max_length=120, description="Miejscowość (bez adresu) — do planu objazdów"
    )
    delivery_planned_on: date | None = None


class HouseholdUpdate(PatchModel):
    NOT_NULL = ("name", "side", "invitation_status")

    name: str | None = Field(default=None, min_length=1, max_length=150)
    side: Side | None = None
    group_label: str | None = Field(default=None, max_length=80)
    contact_email: Email | None = None
    contact_phone: Phone | None = None
    invitation_status: InvitationStatus | None = None
    rsvp_deadline: date | None = None
    language: Language | None = None
    notes: str | None = Field(default=None, max_length=2000)
    gift_note: str | None = Field(default=None, max_length=300, description="Co podarowali")
    thanked: bool | None = Field(default=None, description="Podziękowanie wysłane")
    delivery_method: DeliveryMethod | None = Field(
        default=None, description="Jak trafi zaproszenie (osobiście, pocztą, online)"
    )
    delivery_by: str | None = Field(default=None, max_length=80, examples=["Ania i mama"])
    delivery_place: str | None = Field(
        default=None, max_length=120, description="Miejscowość (bez adresu) — do planu objazdów"
    )
    delivery_planned_on: date | None = None
    delivered_on: date | None = None


class GuestCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    age_group: AgeGroup = "adult"
    is_plus_one: bool = False
    dietary_preference: Diet = "standard"
    dietary_note: str | None = Field(default=None, max_length=300, description=DIETARY_NOTE_HELP)
    needs_accommodation: bool = False
    needs_transport: bool = False
    notes: str | None = Field(default=None, max_length=1000)


class GuestUpdate(PatchModel):
    NOT_NULL = (
        "first_name",
        "age_group",
        "is_plus_one",
        "dietary_preference",
        "needs_accommodation",
        "needs_transport",
        "household_id",
    )

    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    age_group: AgeGroup | None = None
    is_plus_one: bool | None = None
    dietary_preference: Diet | None = None
    dietary_note: str | None = Field(default=None, max_length=300, description=DIETARY_NOTE_HELP)
    needs_accommodation: bool | None = None
    needs_transport: bool | None = None
    notes: str | None = Field(default=None, max_length=1000)
    household_id: UUID | None = Field(default=None, description="Przeniesienie do gospodarstwa")


class GuestOut(BaseModel):
    id: UUID
    household_id: UUID
    first_name: str
    last_name: str | None
    age_group: AgeGroup
    is_plus_one: bool
    added_via_rsvp: bool = Field(description="Dopisana przez gościa w formularzu RSVP")
    dietary_preference: Diet
    dietary_note: str | None
    needs_accommodation: bool
    needs_transport: bool
    notes: str | None
    attendance: dict[UUID, AttendanceStatus] = Field(description="event_id → status")
    version: int


class HouseholdOut(BaseModel):
    id: UUID
    name: str
    side: Side
    group_label: str | None
    contact_email: str | None
    contact_phone: str | None
    invitation_status: InvitationStatus
    rsvp_deadline: date | None
    language: Language | None
    rsvp_link_active: bool
    rsvp_emailed_at: datetime | None
    notes: str | None
    gift_note: str | None
    thanked: bool
    delivery_method: DeliveryMethod | None = None
    delivery_by: str | None = None
    delivery_place: str | None = None
    delivery_planned_on: date | None = None
    delivered_on: date | None = None
    guests: list[GuestOut]
    version: int


class AttendanceIn(BaseModel):
    status: AttendanceStatus


class RsvpLinkOut(BaseModel):
    token: str = Field(description="Pokazywany tylko raz; w bazie przechowujemy wyłącznie hash")
    url: str
    expires_at: datetime
    qr_svg: str = Field(description="Kod QR z adresem (SVG) — do zaproszenia; tylko teraz")


class RsvpQrIn(BaseModel):
    household_ids: list[UUID] | None = Field(
        default=None, max_length=500, description="Domyślnie wszystkie rodziny"
    )
    include_with_link: bool = Field(
        default=False,
        description="Także rodziny z aktywnym linkiem: dostaną nowy, a stary przestanie działać",
    )
    dry_run: bool = True


class RsvpQrCard(BaseModel):
    household_id: UUID
    name: str
    has_active_link: bool
    rsvp_deadline: date | None
    url: str | None = Field(description="Tylko po zapisie (dry_run=false)")
    qr_svg: str | None


class RsvpQrOut(BaseModel):
    dry_run: bool
    cards: list[RsvpQrCard]
    with_link_skipped: int = Field(description="Mają aktywny link, pominięte (include_with_link)")


class EventStats(BaseModel):
    event_id: UUID
    name: str
    kind: str
    attending: int
    declined: int
    maybe: int
    pending: int
    attending_adults: int
    attending_children: int


class GuestStats(BaseModel):
    households: int
    guests: int
    adults: int
    children: int
    plus_ones: int
    by_side: dict[str, int]
    diets: dict[str, int]
    with_dietary_note: int
    needs_accommodation: int
    needs_transport: int
    invitations: dict[str, int]
    events: list[EventStats]


class ImportIn(BaseModel):
    csv: str = Field(
        max_length=1_000_000,
        description=(
            "CSV z nagłówkiem. Kolumny: household (wymagana), first_name (wymagana), last_name, "
            "side, age_group, dietary, accommodation, transport, email, phone. Separator ; lub ,"
        ),
    )
    dry_run: bool = True


class ImportRowError(BaseModel):
    row: int
    message: str


class ImportOut(BaseModel):
    dry_run: bool
    households_created: int
    households_reused: int
    guests_created: int
    errors: list[ImportRowError]


# --- publiczne RSVP (gość bez konta) ----------------------------------------------------


class RsvpEvent(BaseModel):
    id: UUID
    kind: str
    name: str
    starts_at: datetime | None
    ends_at: datetime | None = None
    address: str | None


class RsvpGuest(BaseModel):
    id: UUID
    first_name: str
    age_group: AgeGroup
    is_plus_one: bool
    added_via_rsvp: bool = Field(description="Dopisana przez gościa — może ją usunąć")
    dietary_preference: Diet
    has_dietary_note: bool
    needs_accommodation: bool
    needs_transport: bool
    attendance: dict[UUID, AttendanceStatus]
    transport_run_ids: list[UUID] = Field(
        default_factory=list, description="Kursy (pokazane gościom), na które osoba się zapisała"
    )


class GuestInfoFields(BaseModel):
    welcome: str | None = Field(default=None, max_length=2000)
    directions: str | None = Field(default=None, max_length=2000, description="Dojazd i parking")
    accommodation: str | None = Field(default=None, max_length=2000)
    transport: str | None = Field(default=None, max_length=2000)
    dress_code: str | None = Field(default=None, max_length=1000)
    gifts: str | None = Field(default=None, max_length=1000)
    contact: str | None = Field(default=None, max_length=500, description="Kontakt w sprawach dnia")


GuestTheme = Literal["classic", "garden", "modern"]
# Kolory akcentu: każdy sprawdzony pod kontrast WCAG AA w jasnym i ciemnym motywie
# (frontend: styles/tokens.test.ts). Nazwa, nie wartość — kolor dobiera frontend.
Accent = Literal["rose", "sage", "navy", "gold", "plum", "teal"]


class GuestInfoIn(GuestInfoFields):
    published: bool = False
    theme: GuestTheme = "classic"
    accent: Accent | None = None


class GuestInfoOut(GuestInfoIn):
    version: int = Field(description='0 = jeszcze nie zapisano (If-Match: "0")')
    updated_at: datetime | None


class RsvpTransportRun(BaseModel):
    id: UUID
    name: str
    kind: Literal["there", "back", "other"]
    departs_at: datetime | None
    from_place: str | None
    to_place: str | None
    free: int = Field(description="Wolne miejsca (bez nazwisk innych pasażerów)")


class RsvpScheduleItem(BaseModel):
    title: str
    starts_at: datetime
    location: str | None


class RsvpTheme(BaseModel):
    style: GuestTheme
    accent: Accent | None


class RsvpSong(BaseModel):
    title: str
    artist: str | None


class RsvpSongs(BaseModel):
    enabled: bool = Field(description="Para zbiera propozycje utworów")
    limit: int
    mine: list[RsvpSong] = Field(description="Propozycje tego zaproszenia")


class RsvpSongIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    artist: str | None = Field(default=None, max_length=120)


class RsvpTableSeat(BaseModel):
    first_name: str
    table: str
    seat_number: int | None


class RsvpWish(BaseModel):
    author: str
    text: str


class RsvpWishes(BaseModel):
    limit: int
    mine: list[RsvpWish]


class RsvpWishIn(BaseModel):
    author: str = Field(min_length=1, max_length=120, examples=["Ciocia Basia z wujkiem"])
    text: str = Field(min_length=1, max_length=1000)


class RsvpAnnouncement(BaseModel):
    text: str
    updated_at: datetime | None


class GuestPageSettings(BaseModel):
    info_published: bool = Field(description="Informacje (dojazd, nocleg…) widoczne dla gości")
    show_menu: bool
    song_requests: bool
    gifts_enabled: bool
    runs_shown: int = Field(description="Kursy autokaru pokazane gościom")
    show_tables: bool = Field(description="Każde zaproszenie widzi swój stół na stronie gościa")
    wishes_enabled: bool = Field(description="Goście mogą zostawić życzenia na swojej stronie")
    announcement: str | None
    announcement_at: datetime | None
    announcement_emailed_at: datetime | None
    households_with_email: int
    households: int


class GuestPageSettingsIn(BaseModel):
    show_tables: bool | None = None
    wishes_enabled: bool | None = None
    gifts_enabled: bool | None = None


GiftKind = Literal["item", "fund"]


def _http_link(v: str | None) -> str | None:
    if v is None or not v.strip():
        return None
    v = v.strip()
    if not v.startswith(("https://", "http://")):
        raise ValueError("Link musi zaczynać się od https:// albo http://")
    return v


HttpLink = Annotated[str | None, AfterValidator(_http_link)]


class GiftIn(BaseModel):
    kind: GiftKind = "item"
    title: str = Field(min_length=1, max_length=200, examples=["Ekspres do kawy"])
    note: str | None = Field(default=None, max_length=300)
    link: HttpLink = Field(default=None, max_length=500)


class GiftUpdate(PatchModel):
    NOT_NULL = ("kind", "title")

    kind: GiftKind | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=300)
    link: HttpLink = Field(default=None, max_length=500)


class GiftOut(BaseModel):
    id: UUID
    kind: GiftKind
    title: str
    note: str | None
    link: str | None
    reserved: bool
    reserved_by: str | None = Field(
        description="Zaproszenie, które zarezerwowało (widzi tylko para)"
    )
    version: int


class GiftsOverview(BaseModel):
    enabled: bool
    ideas: list[GiftOut]
    reserved_count: int


class RsvpGift(BaseModel):
    id: UUID
    kind: GiftKind
    title: str
    note: str | None
    link: str | None
    reserved: bool
    mine: bool = Field(description="Zarezerwowane przez to zaproszenie")


class RsvpGiftReserveIn(BaseModel):
    reserved: bool


class AnnouncementIn(BaseModel):
    text: str | None = Field(
        default=None, max_length=500, description="Pusty tekst usuwa komunikat"
    )


class AnnouncementEmailIn(BaseModel):
    dry_run: bool = True


class AnnouncementEmailOut(BaseModel):
    dry_run: bool
    recipients: int = Field(description="Rodziny z adresem e-mail")


class WishOut(BaseModel):
    id: UUID
    author: str
    text: str
    hidden: bool
    household_name: str | None
    created_at: datetime


class WishHiddenIn(BaseModel):
    hidden: bool


class RsvpView(BaseModel):
    theme: RsvpTheme = Field(description="Wygląd strony ustawiony przez parę")
    language: Language | None = Field(
        default=None, description="Język zaproszenia; brak = wg przeglądarki gościa"
    )
    wedding_name: str
    household_name: str
    rsvp_deadline: date | None
    is_open: bool
    events: list[RsvpEvent]
    guests: list[RsvpGuest]
    info: GuestInfoFields | None = Field(description="Informacje dla gości (gdy opublikowane)")
    schedule: list[RsvpScheduleItem] = Field(description="Punkty programu oznaczone dla gości")
    transport_runs: list[RsvpTransportRun] = Field(
        default_factory=list, description="Kursy, które para pokazała gościom"
    )
    songs: RsvpSongs | None = Field(default=None, description="Propozycje utworów dla DJ-a")
    tables: list[RsvpTableSeat] | None = Field(
        default=None, description="Stół i miejsca tego zaproszenia (gdy para je pokazała)"
    )
    wishes: RsvpWishes | None = Field(default=None, description="Księga życzeń (gdy włączona)")
    announcement: RsvpAnnouncement | None = Field(default=None, description="Komunikat od pary")
    gifts: list[RsvpGift] | None = Field(default=None, description="Lista prezentów (gdy włączona)")
    menu: list["GuestDish"] | None = Field(
        default=None, description="Menu z alergenami (gdy para je pokazała)"
    )
    preview_info_published: bool | None = Field(
        default=None,
        description="Tylko w podglądzie pary: czy informacje są już widoczne dla gości",
    )
    privacy_note: str = (
        "Dane podane w formularzu widzi wyłącznie para młoda organizująca wesele. "
        "Zostaną usunięte po weselu."
    )


class RsvpResponse(BaseModel):
    guest_id: UUID
    event_id: UUID
    status: Literal["attending", "declined", "maybe"]


class RsvpGuestDetails(BaseModel):
    guest_id: UUID
    dietary_preference: Diet | None = None
    dietary_note: str | None = Field(default=None, max_length=300)
    needs_accommodation: bool | None = None
    needs_transport: bool | None = None
    transport_run_ids: list[UUID] | None = Field(
        default=None, max_length=10, description="Wybrane kursy; brak = bez zmian"
    )


class RsvpSubmit(BaseModel):
    responses: list[RsvpResponse] = Field(max_length=200)
    guests: list[RsvpGuestDetails] = Field(default_factory=list, max_length=50)
    health_data_consent: bool = Field(
        default=False,
        description="Wymagane, jeśli podajesz uwagi dietetyczne (mogą dotyczyć zdrowia).",
    )

    @model_validator(mode="after")
    def _consent_for_notes(self) -> Self:
        if any(g.dietary_note for g in self.guests) and not self.health_data_consent:
            raise ValueError("Uwagi dietetyczne wymagają zgody na przetwarzanie tych danych.")
        return self


class RsvpCompanionIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    age_group: AgeGroup = "adult"


class RsvpEmailsIn(BaseModel):
    dry_run: bool = True
    include_with_link: bool = Field(
        default=False,
        description="Także rodziny z aktywnym linkiem: dostaną nowy, a stary przestanie działać",
    )


class RsvpEmailTarget(BaseModel):
    household_id: UUID
    name: str
    email: str
    has_active_link: bool
    last_emailed_at: datetime | None


class RsvpEmailsOut(BaseModel):
    dry_run: bool
    to_send: list[RsvpEmailTarget]
    with_link_skipped: int = Field(description="Mają aktywny link, pominięte (include_with_link)")
    without_email: int = Field(description="Bez odpowiedzi, ale bez adresu e-mail")
    note: str = (
        "Wysyłamy e-mail z linkiem do potwierdzenia obecności tylko do rodzin, które jeszcze "
        "nie odpowiedziały i mają adres e-mail. Każda wysyłka tworzy nowy link."
    )


# --- lista rezerwowa i prognoza frekwencji -----------------------------------------------

ReserveStatus = Literal["waiting", "invited"]


class ReserveEntryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150, examples=["Kuzyn Marek z żoną"])
    side: Side = "both"
    persons: int = Field(default=1, ge=1, le=20, description="Ile osób obejmie zaproszenie")
    note: str | None = Field(default=None, max_length=500)


class ReserveEntryUpdate(PatchModel):
    NOT_NULL = ("name", "side", "persons", "position")

    name: str | None = Field(default=None, min_length=1, max_length=150)
    side: Side | None = None
    persons: int | None = Field(default=None, ge=1, le=20)
    note: str | None = Field(default=None, max_length=500)
    position: int | None = Field(
        default=None, ge=0, le=1000, description="Nowe miejsce w kolejce (0 = pierwsze)"
    )


class ReserveEntryOut(BaseModel):
    id: UUID
    name: str
    side: Side
    persons: int
    position: int
    note: str | None
    status: ReserveStatus
    household_id: UUID | None
    invited_at: datetime | None
    version: int


class ReserveGuestIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    age_group: AgeGroup = "adult"


class ReserveInviteIn(BaseModel):
    guests: list[ReserveGuestIn] = Field(min_length=1, max_length=20)
    rsvp_deadline: date | None = None


class ReserveInviteOut(BaseModel):
    entry: ReserveEntryOut
    household_id: UUID


class ForecastPeople(BaseModel):
    attending: int
    declined: int
    maybe: int
    pending: int
    infants: int = Field(description="Niemowlęta: poza liczbami (zwykle bez opłaty i miejsca)")


class ForecastRange(BaseModel):
    expected: int
    low: int = Field(description="Dolna granica przedziału ok. 90%")
    high: int = Field(description="Górna granica przedziału ok. 90%")
    expected_adults: int
    expected_children: int


class ForecastVenue(BaseModel):
    offer_id: UUID
    offer_title: str
    vendor_name: str
    min_guests: int
    shortfall_expected: int = Field(description="Ilu osób brakuje do minimum przy prognozie")
    shortfall_low: int
    unused_cost_expected: Money | None = Field(
        description="Koszt niewykorzystanego minimum przy prognozie (wycena oferty)"
    )
    unused_cost_low: Money | None


class ForecastDeadline(BaseModel):
    task_id: UUID
    title: str
    due_date: date | None
    days_left: int | None
    done: bool


class ForecastOverdueHousehold(BaseModel):
    household_id: UUID
    name: str
    rsvp_deadline: date
    pending: int


class ForecastSuggestion(BaseModel):
    entry_id: UUID
    name: str
    persons: int


class ForecastAlert(BaseModel):
    code: str
    message: str


class AfterPartyForecast(BaseModel):
    event_name: str
    people: ForecastPeople
    forecast: ForecastRange


class AttendanceForecast(BaseModel):
    pending_rate: float
    maybe_rate: float
    people: ForecastPeople
    forecast: ForecastRange
    after_party: AfterPartyForecast | None = Field(
        description="Osobna prognoza poprawin (gdy są w wydarzeniach); odmowa przyjęcia = odmowa"
    )
    planned: int | None = Field(description="Planowana liczba gości z ustawień wesela")
    free_places_safe: int | None = Field(
        description="Ile osób można jeszcze zaprosić, licząc wg górnej granicy prognozy"
    )
    venues: list[ForecastVenue]
    final_count: ForecastDeadline | None
    overdue_households: list[ForecastOverdueHousehold]
    reserve_waiting: int
    reserve_invite_by: date | None = Field(
        description="Do kiedy zapraszać z listy rezerwowej (6 tygodni przed ślubem, "
        "najpóźniej tydzień przed podaniem ostatecznej liczby)"
    )
    suggestions: list[ForecastSuggestion]
    alerts: list[ForecastAlert]


# --- wręczanie zaproszeń ------------------------------------------------------------------


class DeliveryHousehold(BaseModel):
    id: UUID
    name: str
    side: Side
    guests: int
    delivery_by: str | None
    delivery_planned_on: date | None
    delivered_on: date | None
    invitation_status: InvitationStatus
    version: int


class DeliveryGroup(BaseModel):
    place: str | None = Field(description="Miejscowość; null = bez miejscowości")
    households: list[DeliveryHousehold]
    remaining: int
    planned_on: list[date] = Field(description="Zaplanowane dni objazdu w tej miejscowości")


class PrintOrder(BaseModel):
    printed: int = Field(description="Papierowe: jedno na rodzinę, bez wysyłanych online")
    spare: int = Field(description="Zapas: 10%, co najmniej 3")
    reserve: int = Field(description="Czekający na liście rezerwowej")
    total: int = Field(description="Ile zamówić w drukarni")


class DeliveryOverview(BaseModel):
    in_person_total: int
    in_person_delivered: int
    by_method: dict[str, int] = Field(
        description="Liczba zaproszeń wg sposobu (bez ustalenia: none)"
    )
    deadline: date | None = Field(description="Do kiedy wręczyć (zadanie z planu albo termin RSVP)")
    weekends_left: int | None = Field(description="Ile weekendów zostało do terminu")
    groups: list[DeliveryGroup]
    print_order: PrintOrder


class DeliveryPlanIn(BaseModel):
    household_ids: list[UUID] = Field(min_length=1, max_length=200)
    planned_on: date | None = None
    delivery_by: str | None = Field(default=None, max_length=80)


class DeliveredIn(BaseModel):
    household_ids: list[UUID] = Field(min_length=1, max_length=200)
    delivered_on: date | None = Field(default=None, description="Domyślnie dzisiaj")


from app.modules.menu.schemas import GuestDish  # noqa: E402

RsvpView.model_rebuild()
