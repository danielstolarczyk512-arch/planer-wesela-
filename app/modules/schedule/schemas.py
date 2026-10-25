from datetime import date, datetime, time
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.core.schemas import PatchModel
from app.modules.workspace.schemas import AwareDatetime


class ItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200, examples=["Pierwszy taniec"])
    starts_at: AwareDatetime
    duration_minutes: int = Field(default=0, ge=0, le=1440)
    event_id: UUID | None = None
    location: str | None = Field(default=None, max_length=200)
    responsible_user_id: UUID | None = None
    responsible_name: str | None = Field(default=None, max_length=120, examples=["Świadkowa Kasia"])
    vendor_id: UUID | None = None
    preparations: str | None = Field(default=None, max_length=2000)
    plan_b: str | None = Field(default=None, max_length=2000, description="Wariant awaryjny")
    for_guests: bool = Field(default=False, description="Widoczny dla gości w linku RSVP")
    buffer_before_minutes: int = Field(default=0, ge=0, le=600)
    buffer_after_minutes: int = Field(default=0, ge=0, le=600)
    notes: str | None = Field(default=None, max_length=2000)


class ItemUpdate(PatchModel):
    NOT_NULL = (
        "title",
        "for_guests",
        "starts_at",
        "duration_minutes",
        "buffer_before_minutes",
        "buffer_after_minutes",
    )

    title: str | None = Field(default=None, min_length=1, max_length=200)
    starts_at: AwareDatetime | None = None
    duration_minutes: int | None = Field(default=None, ge=0, le=1440)
    event_id: UUID | None = None
    location: str | None = Field(default=None, max_length=200)
    responsible_user_id: UUID | None = None
    responsible_name: str | None = Field(default=None, max_length=120)
    vendor_id: UUID | None = None
    preparations: str | None = Field(default=None, max_length=2000)
    plan_b: str | None = Field(default=None, max_length=2000, description="Wariant awaryjny")
    for_guests: bool | None = None
    buffer_before_minutes: int | None = Field(default=None, ge=0, le=600)
    buffer_after_minutes: int | None = Field(default=None, ge=0, le=600)
    notes: str | None = Field(default=None, max_length=2000)


class ItemOut(BaseModel):
    id: UUID
    title: str
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    event_id: UUID | None
    location: str | None
    responsible_user_id: UUID | None
    responsible_name: str | None
    vendor_id: UUID | None
    vendor_name: str | None
    preparations: str | None
    plan_b: str | None
    for_guests: bool
    buffer_before_minutes: int
    buffer_after_minutes: int
    notes: str | None
    depends_on: list[UUID]
    conflicts: list[str] = Field(description="Kody konfliktów dotyczących tego punktu")
    version: int


class ConflictOut(BaseModel):
    code: Literal[
        "vendor_double_booked",
        "person_double_booked",
        "dependency_order",
        "outside_event",
        "vendor_not_booked",
    ]
    severity: Literal["error", "warning"]
    item_ids: list[UUID]
    message: str


class ShiftIn(BaseModel):
    from_item_id: UUID = Field(description="Przesuwamy ten punkt i wszystkie późniejsze")
    minutes: int = Field(ge=-600, le=600, description="Ujemne = wcześniej")
    dry_run: bool = True
    revision: str | None = Field(
        default=None,
        max_length=64,
        description="Rewizja programu z podglądu; inna niż obecna → 409 conflict.version_mismatch",
    )

    @model_validator(mode="after")
    def _non_zero(self) -> Self:
        if self.minutes == 0:
            raise ValueError("Podaj przesunięcie różne od zera.")
        return self


class ShiftChange(BaseModel):
    item_id: UUID
    title: str
    old_starts_at: datetime
    new_starts_at: datetime


class ShiftOut(BaseModel):
    dry_run: bool
    revision: str = Field(description="Rewizja programu (po zapisie — nowa)")
    changes: list[ShiftChange]
    conflicts_after: list[ConflictOut]


class TemplateStep(BaseModel):
    title: str
    starts_at: datetime
    duration_minutes: int
    event_id: UUID | None
    preparations: str | None


class TemplateOut(BaseModel):
    dry_run: bool
    items: list[TemplateStep]
    note: str = "Szablon to punkt wyjścia: godziny i kolejność dopasujcie do swojego wesela."


class TemplateIn(BaseModel):
    day: date | None = Field(default=None, description="Dzień ślubu; domyślnie data ślubu")
    ceremony_time: time = Field(examples=["15:00"])
    dry_run: bool = True


class DayLinkStatus(BaseModel):
    active: bool
    share_catering: bool = Field(
        default=False, description="Link pokazuje imiona, diety i uwagi przy stołach"
    )
    created_at: datetime | None
    last_used_at: datetime | None


class DayLinkCreate(BaseModel):
    share_catering: bool = Field(
        default=False,
        description=(
            "Tylko sala/catering: udostępnij imiona przy stołach, diety i uwagi dla kuchni "
            "(dane o zdrowiu). Bez zgody link pokazuje same liczby."
        ),
    )


class DayLinkCreated(BaseModel):
    token: str = Field(description="Widoczny tylko raz; strona: /dzien/{token}")


class PublicEvent(BaseModel):
    name: str
    starts_at: datetime
    ends_at: datetime | None
    address: str | None


class PublicItem(BaseModel):
    title: str
    starts_at: datetime
    ends_at: datetime
    location: str | None
    mine: bool = Field(description="Punkt tego usługodawcy")
    preparations: str | None
    plan_b: str | None
    notes: str | None


class AgeCounts(BaseModel):
    adults: int
    teens: int
    children: int
    infants: int


class DietCount(BaseModel):
    diet: str
    count: int


class CateringGuest(BaseModel):
    name: str
    age_group: str
    diet: str
    diet_note: str | None


class CateringTable(BaseModel):
    name: str
    count: AgeCounts
    diets: list[DietCount]
    guests: list[CateringGuest] | None = Field(description="Tylko za zgodą pary")


class Catering(BaseModel):
    attending: AgeCounts = Field(description="Potwierdzeni na przyjęcie")
    pending: int = Field(description="Jeszcze bez odpowiedzi")
    diets: list[DietCount] = Field(description="Diety inne niż standardowa (potwierdzeni)")
    crew_meals: int
    tables: list[CateringTable]
    details_shared: bool


BriefLine = Annotated[str, Field(min_length=1, max_length=200)]


class BriefPerson(BaseModel):
    name: str = Field(min_length=1, max_length=80, examples=["Babcia Halina"])
    role: str = Field(min_length=1, max_length=120, examples=["mama Pana Młodego, na wózku"])


class BriefIn(BaseModel):
    must: list[BriefLine] = Field(
        default_factory=list,
        max_length=40,
        description="Obowiązkowe: ujęcia, utwory, elementy dekoracji (zależnie od usługodawcy)",
    )
    avoid: list[BriefLine] = Field(
        default_factory=list, max_length=40, description="Czego unikać, np. utwory „nie grać”"
    )
    people: list[BriefPerson] = Field(
        default_factory=list,
        max_length=40,
        description="Kto jest kim (dla fotografa, wodzireja) — tylko to, co potrzebne",
    )
    notes: str | None = Field(default=None, max_length=2000)
    contact: str | None = Field(
        default=None,
        max_length=200,
        description="Kontakt w dniu ślubu, np. świadek lub koordynator",
    )


class BriefOut(BriefIn):
    vendor_id: UUID
    version: int = Field(description="Wersja rekordu do If-Match (nie wersja programu)")
    updated_at: datetime


class BriefStatus(BaseModel):
    vendor_id: UUID
    vendor_name: str
    category: str
    version: int = Field(description="Aktualna wersja treści linku")
    acknowledged_version: int | None
    acknowledged_at: datetime | None
    up_to_date: bool = Field(description="Usługodawca potwierdził aktualną wersję")
    last_opened_at: datetime | None


class AckIn(BaseModel):
    version: int = Field(ge=1, description="Wersja widoczna na stronie")


class AckOut(BaseModel):
    version: int
    acknowledged_at: datetime


class VendorRunOut(BaseModel):
    name: str
    departs_at: datetime | None
    from_place: str | None
    to_place: str | None
    passengers: int
    capacity: int


class PublicDay(BaseModel):
    wedding_name: str
    wedding_date: date | None
    vendor_name: str
    vendor_category: str
    updated_at: datetime | None
    events: list[PublicEvent]
    items: list[PublicItem]
    catering: Catering | None = Field(
        default=None, description="Tylko dla sali i cateringu: liczby dla kuchni i obsługi"
    )
    brief: BriefIn
    music: list["VendorSong"] = Field(
        default_factory=list, description="Tylko DJ, zespół, muzyk: zatwierdzone utwory"
    )
    photo_groups: list["VendorPhotoGroup"] = Field(
        default_factory=list, description="Tylko fotograf i filmowiec: zdjęcia grupowe"
    )
    prep: list["VendorPrepSlot"] = Field(
        default_factory=list, description="Tylko fryzjer i makijaż: kto i o której na fotelu"
    )
    transport: list[VendorRunOut] = Field(
        default_factory=list, description="Kursy przewoźnika: godziny i liczba osób, bez nazwisk"
    )
    version: int = Field(description="Numer wersji tej treści (bez liczb dla kuchni)")
    acknowledged_version: int | None
    acknowledged_at: datetime | None
    up_to_date: bool


class ChecklistIn(BaseModel):
    title: str = Field(min_length=1, max_length=200, examples=["Obrączki"])
    who: str | None = Field(default=None, max_length=80, examples=["świadek"])


class ChecklistUpdate(PatchModel):
    NOT_NULL = ("title",)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    who: str | None = Field(default=None, max_length=80)


class ChecklistOut(BaseModel):
    id: UUID
    title: str
    who: str | None
    done: bool
    version: int


class DoneIn(BaseModel):
    done: bool


# --- muzyka ----------------------------------------------------------------------------------

MusicMoment = Literal[
    "ceremony",
    "entrance",
    "first_dance",
    "parents",
    "cake",
    "oczepiny",
    "last_dance",
    "must",
    "avoid",
    "other",
]
MusicStatus = Literal["approved", "suggested", "rejected"]


class MusicIn(BaseModel):
    moment: MusicMoment
    title: str = Field(min_length=1, max_length=200, examples=["Perfect"])
    artist: str | None = Field(default=None, max_length=120, examples=["Ed Sheeran"])
    note: str | None = Field(default=None, max_length=300, examples=["wersja akustyczna"])


class MusicUpdate(PatchModel):
    NOT_NULL = ("moment", "title", "status")

    moment: MusicMoment | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    artist: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=300)
    status: MusicStatus | None = Field(
        default=None, description="Propozycję gościa para zatwierdza (approved) albo odrzuca"
    )


class MusicOut(BaseModel):
    id: UUID
    moment: MusicMoment
    title: str
    artist: str | None
    note: str | None
    status: MusicStatus
    suggested_by: str | None = Field(description="Zaproszenie gościa, który zaproponował")
    from_guest: bool
    version: int


class MusicOverview(BaseModel):
    song_requests: bool = Field(description="Czy goście mogą proponować utwory w RSVP")
    entries: list[MusicOut]
    waiting: int = Field(description="Propozycje gości czekające na decyzję")


class SongRequestsIn(BaseModel):
    enabled: bool


class VendorSong(BaseModel):
    moment: MusicMoment
    title: str
    artist: str | None
    note: str | None


# --- zdjęcia grupowe -------------------------------------------------------------------------


class PhotoGroupIn(BaseModel):
    title: str = Field(min_length=1, max_length=200, examples=["Para Młoda z dziadkami"])
    extra: str | None = Field(default=None, max_length=200, examples=["ksiądz"])
    minutes: int = Field(default=3, ge=1, le=60)
    guest_ids: list[UUID] = Field(default_factory=list, max_length=200)


class PhotoGroupUpdate(PatchModel):
    NOT_NULL = ("title", "minutes", "guest_ids")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    extra: str | None = Field(default=None, max_length=200)
    minutes: int | None = Field(default=None, ge=1, le=60)
    guest_ids: list[UUID] | None = Field(default=None, max_length=200)


class PhotoGuest(BaseModel):
    id: UUID
    name: str


class PhotoGroupOut(BaseModel):
    id: UUID
    title: str
    extra: str | None
    minutes: int
    done: bool
    version: int
    guests: list[PhotoGuest]


class PhotoOverview(BaseModel):
    groups: list[PhotoGroupOut]
    total_minutes: int
    remaining_minutes: int


class MoveIn(BaseModel):
    direction: Literal["up", "down"]


class VendorPhotoGroup(BaseModel):
    title: str
    people: list[str] = Field(description="Imię i inicjał nazwiska")
    extra: str | None
    minutes: int


# --- przygotowania (fryzjer, makijaż) ----------------------------------------------------------


class PrepPlanIn(BaseModel):
    ready_by: time | None = Field(default=None, description="Na którą wszyscy gotowi (czas polski)")
    hair_artists: int | None = Field(default=None, ge=0, le=10)
    makeup_artists: int | None = Field(default=None, ge=0, le=10)


class PrepPersonIn(BaseModel):
    name: str = Field(min_length=1, max_length=80, examples=["Panna Młoda"])
    hair_minutes: int = Field(default=0, ge=0, le=300)
    makeup_minutes: int = Field(default=0, ge=0, le=300)


class PrepPersonUpdate(PatchModel):
    NOT_NULL = ("name", "hair_minutes", "makeup_minutes")

    name: str | None = Field(default=None, min_length=1, max_length=80)
    hair_minutes: int | None = Field(default=None, ge=0, le=300)
    makeup_minutes: int | None = Field(default=None, ge=0, le=300)


class PrepSlot(BaseModel):
    start: str = Field(description="HH:MM")
    end: str
    artist: int = Field(description="Numer fryzjerki lub makijażystki (od 1)")


class PrepPersonOut(BaseModel):
    id: UUID
    name: str
    hair_minutes: int
    makeup_minutes: int
    version: int
    hair: PrepSlot | None
    makeup: PrepSlot | None


class PrepOverview(BaseModel):
    ready_by: str
    hair_artists: int
    makeup_artists: int
    version: int = Field(description="Wersja planu do If-Match (0 = jeszcze nie zapisany)")
    start: str | None = Field(description="Kto pierwszy siada na fotel — o tej godzinie")
    hair_start: str | None
    makeup_start: str | None
    people: list[PrepPersonOut]
    warnings: list[str]


class VendorPrepSlot(BaseModel):
    name: str
    start: str
    end: str
    artist: int
