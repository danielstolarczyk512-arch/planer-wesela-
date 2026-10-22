from datetime import date, datetime
from typing import Annotated, Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.core.schemas import Money, PatchModel

WARSAW = ZoneInfo("Europe/Warsaw")
CeremonyType = Literal["civil", "concordat", "religious_other", "humanist", "undecided"]
EventKind = Literal["ceremony", "reception", "after_party", "other"]
MemberRole = Literal["owner", "coorganizer", "viewer", "coordinator", "sponsor"]
InvitableRole = Literal["coorganizer", "viewer", "coordinator", "sponsor"]
PlannedMonth = Annotated[str, Field(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$", examples=["2027-08"])]
MAX_YEARS_AHEAD = 10
ShortLabel = Annotated[str, Field(min_length=1, max_length=32)]
PriorityLabel = Annotated[str, Field(min_length=1, max_length=64)]
NormalizedEmail = Annotated[EmailStr, AfterValidator(lambda v: v.strip().lower())]


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError("Data i godzina muszą zawierać strefę czasową (np. +02:00).")
    return value


AwareDatetime = Annotated[datetime, AfterValidator(_aware)]


def check_wedding_dates(wedding_date: date | None, planned_month: str | None) -> None:
    """Data ślubu: od dziś do +10 lat; planowany miesiąc: od bieżącego miesiąca do +10 lat."""
    today = datetime.now(WARSAW).date()
    if wedding_date is not None and planned_month is not None:
        raise ValueError("Podaj datę ślubu albo planowany miesiąc, nie oba naraz.")
    if wedding_date is not None:
        if wedding_date < today:
            raise ValueError("Data ślubu nie może być w przeszłości.")
        if wedding_date.year > today.year + MAX_YEARS_AHEAD:
            raise ValueError(f"Data ślubu może być najwyżej {MAX_YEARS_AHEAD} lat naprzód.")
    if planned_month is not None:
        year, month = (int(part) for part in planned_month.split("-"))
        if (year, month) < (today.year, today.month):
            raise ValueError("Planowany miesiąc nie może być w przeszłości.")
        if year > today.year + MAX_YEARS_AHEAD:
            raise ValueError(f"Planowany miesiąc może być najwyżej {MAX_YEARS_AHEAD} lat naprzód.")


class _WeddingFields(PatchModel):
    @model_validator(mode="after")
    def _date_or_month(self) -> Self:
        check_wedding_dates(
            getattr(self, "wedding_date", None), getattr(self, "planned_month", None)
        )
        return self


class WeddingCreate(_WeddingFields):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Ania i Tomek",
                "planned_month": "2027-08",
                "ceremony_type": "concordat",
                "city": "Kraków",
                "guest_count_planned": 110,
                "total_budget": {"amount": "65000.00", "currency": "PLN"},
            }
        }
    )

    name: str = Field(min_length=1, max_length=120)
    wedding_date: date | None = None
    planned_month: PlannedMonth | None = None
    ceremony_type: CeremonyType = "undecided"
    city: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=64)
    guest_count_planned: int | None = Field(default=None, ge=0, le=2000)
    total_budget: Money | None = None
    style: str | None = Field(default=None, max_length=120)
    colors: list[ShortLabel] = Field(default_factory=list, max_length=10)
    priorities: list[PriorityLabel] = Field(default_factory=list, max_length=10)


class WeddingUpdate(_WeddingFields):
    """Częściowa aktualizacja; wymaga nagłówka If-Match."""

    NOT_NULL = ("name", "ceremony_type")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    wedding_date: date | None = None
    planned_month: PlannedMonth | None = None
    ceremony_type: CeremonyType | None = None
    city: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=64)
    guest_count_planned: int | None = Field(default=None, ge=0, le=2000)
    total_budget: Money | None = None
    style: str | None = Field(default=None, max_length=120)
    colors: list[ShortLabel] | None = Field(default=None, max_length=10)
    priorities: list[PriorityLabel] | None = Field(default=None, max_length=10)


class WeddingOut(BaseModel):
    id: UUID
    name: str
    wedding_date: date | None
    planned_month: str | None
    ceremony_type: str
    city: str | None
    region: str | None
    guest_count_planned: int | None
    total_budget: Money | None
    style: str | None
    colors: list[str]
    priorities: list[str]
    timezone: str
    status: str
    my_role: MemberRole
    version: int
    created_at: datetime
    updated_at: datetime


class _EventChecks(PatchModel):
    @model_validator(mode="after")
    def _order(self) -> Self:
        starts, ends = getattr(self, "starts_at", None), getattr(self, "ends_at", None)
        if starts is not None and ends is not None and ends <= starts:
            raise ValueError("Koniec wydarzenia musi być po jego rozpoczęciu.")
        return self


class EventCreate(_EventChecks):
    kind: EventKind
    name: str = Field(min_length=1, max_length=120)
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    address: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=2000)


class EventUpdate(_EventChecks):
    NOT_NULL = ("kind", "name")

    kind: EventKind | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    address: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=2000)


class EventOut(BaseModel):
    id: UUID
    kind: str
    name: str
    starts_at: datetime | None
    ends_at: datetime | None
    address: str | None
    notes: str | None
    version: int


class MemberOut(BaseModel):
    user_id: UUID
    display_name: str | None
    email: str
    role: MemberRole
    joined_at: datetime
    funder_id: UUID | None = Field(default=None, description="Rola sponsor: czyj wkład widzi")


class MemberUpdate(BaseModel):
    role: MemberRole
    funder_id: UUID | None = Field(default=None, description="Wymagane dla roli sponsor")


class InvitationCreate(BaseModel):
    email: NormalizedEmail
    role: InvitableRole = "coorganizer"
    funder_id: UUID | None = Field(
        default=None, description="Rola sponsor: źródło finansowania, którego wkład zobaczy"
    )


class InvitationOut(BaseModel):
    id: UUID
    email: str
    role: str
    funder_id: UUID | None = None
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None


class InvitationAccept(BaseModel):
    token: str = Field(min_length=20, max_length=128)


# --- pomocnik wyboru daty -------------------------------------------------------------------


class NearHoliday(BaseModel):
    date: date
    name: str


class DateCheck(BaseModel):
    date: date
    weekday: str
    season: Literal["high", "mid", "low"] = Field(
        description="high: od czerwca do września, mid: maj i październik, low: reszta roku"
    )
    holiday: str | None = Field(description="Nazwa święta, gdy data to dzień ustawowo wolny")
    holidays_near: list[NearHoliday] = Field(description="Święta w odległości do 3 dni")
    church_season: str | None = Field(
        description="Adwent albo Wielki Post (tylko przy ślubie w kościele)"
    )
    sunset: str | None = Field(
        pattern=r"^\d{2}:\d{2}$", description="Zachód słońca HH:MM, czas polski (algorytm NOAA)"
    )
    golden_hour_from: str | None = Field(
        pattern=r"^\d{2}:\d{2}$", description="Godzina przed zachodem HH:MM (zdjęcia w plenerze)"
    )
    months_left: int
    notes: list[str]


class DateCheckOut(BaseModel):
    city: str = Field(description="Miasto, dla którego liczono zachód słońca")
    cities: list[str] = Field(description="Dostępne miasta wojewódzkie")
    dates: list[DateCheck]
