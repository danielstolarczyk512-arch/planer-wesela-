from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.schemas import PatchModel
from app.modules.workspace.schemas import AwareDatetime

RunKind = Literal["there", "back", "other"]


class RunCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120, examples=["Autokar: kościół → sala"])
    kind: RunKind = Field(default="there", description="there = na wesele, back = powrót")
    departs_at: AwareDatetime | None = None
    from_place: str | None = Field(default=None, max_length=120)
    to_place: str | None = Field(default=None, max_length=120)
    capacity: int = Field(ge=1, le=500)
    vendor_id: UUID | None = Field(default=None, description="Przewoźnik (usługodawca)")
    notes: str | None = Field(default=None, max_length=2000)
    show_to_guests: bool = Field(default=False, description="Goście wybiorą kurs w RSVP")


class RunUpdate(PatchModel):
    NOT_NULL = ("name", "kind", "capacity", "show_to_guests")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    kind: RunKind | None = None
    departs_at: AwareDatetime | None = None
    from_place: str | None = Field(default=None, max_length=120)
    to_place: str | None = Field(default=None, max_length=120)
    capacity: int | None = Field(default=None, ge=1, le=500)
    vendor_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)
    show_to_guests: bool | None = None


class LodgingRoomCreate(BaseModel):
    place: str = Field(min_length=1, max_length=120, examples=["Hotel przy sali"])
    name: str = Field(min_length=1, max_length=60, examples=["Pokój 12"])
    beds: int = Field(ge=1, le=20)
    check_in: date | None = None
    check_out: date | None = None
    paid_by: str | None = Field(default=None, max_length=80, examples=["para", "goście"])
    notes: str | None = Field(default=None, max_length=2000)


class LodgingRoomUpdate(PatchModel):
    NOT_NULL = ("place", "name", "beds")

    place: str | None = Field(default=None, min_length=1, max_length=120)
    name: str | None = Field(default=None, min_length=1, max_length=60)
    beds: int | None = Field(default=None, ge=1, le=20)
    check_in: date | None = None
    check_out: date | None = None
    paid_by: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=2000)


class GuestsIn(BaseModel):
    guest_ids: list[UUID] = Field(max_length=500)


class Person(BaseModel):
    guest_id: UUID
    name: str
    declined: bool = Field(description="Gość odmówił — warto zwolnić miejsce")


class MissedItem(BaseModel):
    title: str
    starts_at: datetime


class RunOut(BaseModel):
    id: UUID
    name: str
    kind: RunKind
    vendor_id: UUID | None
    departs_at: datetime | None
    from_place: str | None
    to_place: str | None
    capacity: int
    notes: str | None
    show_to_guests: bool
    version: int
    passengers: list[Person]
    taken: int
    over: int = Field(description="Ile osób ponad liczbę miejsc")
    missed_items: list[MissedItem] = Field(
        description="Kurs powrotny: punkty programu dla gości po odjeździe"
    )


class LodgingRoomOut(BaseModel):
    id: UUID
    place: str
    name: str
    beds: int
    check_in: date | None
    check_out: date | None
    nights: int | None
    paid_by: str | None
    notes: str | None
    version: int
    occupants: list[Person]
    free: int


class LogisticsOverview(BaseModel):
    runs: list[RunOut]
    rooms: list[LodgingRoomOut]
    transport_missing: list[Person] = Field(description="Potrzebują transportu, bez kursu")
    lodging_missing: list[Person] = Field(description="Potrzebują noclegu, bez pokoju")


class VendorRun(BaseModel):
    name: str
    departs_at: datetime | None
    from_place: str | None
    to_place: str | None
    passengers: int
    capacity: int


class DayRun(BaseModel):
    id: UUID
    name: str
    kind: RunKind
    departs_at: datetime | None
    from_place: str | None
    to_place: str | None
    passengers: int
    capacity: int
