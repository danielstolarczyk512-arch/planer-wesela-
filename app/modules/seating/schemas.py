from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.schemas import PatchModel

TableKind = Literal["regular", "head", "kids"]
Shape = Literal["round", "rectangular", "square"]
Basis = Literal["not_declined", "attending"]
RoomItemKind = Literal["dance_floor", "stage", "bar", "entrance", "buffet", "other"]
Meters = Annotated[float, Field(ge=0, le=200)]


class TableCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80, examples=["Stół 1"])
    kind: TableKind = "regular"
    shape: Shape = "round"
    capacity: int = Field(ge=1, le=40, examples=[10])
    sort_order: int = Field(default=0, ge=0, le=1000)
    notes: str | None = Field(default=None, max_length=2000)
    pos_x: Meters | None = Field(default=None, description="Środek stołu: m od lewej ściany")
    pos_y: Meters | None = Field(default=None, description="Środek stołu: m od górnej ściany")
    rotation: int = Field(default=0, ge=0, le=359)


class TableUpdate(PatchModel):
    NOT_NULL = ("name", "kind", "shape", "capacity", "sort_order", "rotation")

    name: str | None = Field(default=None, min_length=1, max_length=80)
    kind: TableKind | None = None
    shape: Shape | None = None
    capacity: int | None = Field(default=None, ge=1, le=40)
    sort_order: int | None = Field(default=None, ge=0, le=1000)
    notes: str | None = Field(default=None, max_length=2000)
    pos_x: Meters | None = None
    pos_y: Meters | None = None
    rotation: int | None = Field(default=None, ge=0, le=359)


class TableOut(BaseModel):
    id: UUID
    name: str
    kind: TableKind
    shape: Shape
    capacity: int
    sort_order: int
    notes: str | None
    pos_x: float | None
    pos_y: float | None
    rotation: int
    version: int


class SeatedGuest(BaseModel):
    guest_id: UUID
    name: str
    household_id: UUID
    age_group: str
    seat_number: int | None
    locked: bool


class TablePlan(TableOut):
    guests: list[SeatedGuest]
    free_seats: int = Field(description="Ujemne = przekroczona pojemność")


class GuestRef(BaseModel):
    guest_id: UUID
    name: str
    household_id: UUID
    age_group: str


class IssueOut(BaseModel):
    code: Literal[
        "over_capacity",
        "adult_at_kids_table",
        "apart_broken",
        "together_broken",
        "household_split",
        "not_attending_seated",
    ]
    severity: Literal["error", "warning"]
    guest_ids: list[UUID]
    table_ids: list[UUID]
    message: str


class PlanStats(BaseModel):
    tables: int
    seats: int
    seated: int
    to_seat: int = Field(description="Goście bez miejsca (bez odmów i niemowląt)")


class RoomItem(BaseModel):
    kind: RoomItemKind
    label: str | None = Field(default=None, max_length=40)
    x: Meters = Field(description="Środek elementu (m)")
    y: Meters
    w: float = Field(gt=0, le=200, description="Szerokość (m)")
    h: float = Field(gt=0, le=200, description="Głębokość (m)")


class RoomIn(BaseModel):
    width_m: float = Field(ge=4, le=200)
    length_m: float = Field(ge=4, le=200)
    items: list[RoomItem] = Field(default_factory=list, max_length=30)


class RoomOut(RoomIn):
    version: int = Field(description='0 = jeszcze nie zapisano (If-Match: "0")')


class PlanOut(BaseModel):
    room: RoomOut
    tables: list[TablePlan]
    unassigned: list[GuestRef]
    issues: list[IssueOut]
    stats: PlanStats


class SeatIn(BaseModel):
    table_id: UUID
    seat_number: int | None = Field(default=None, ge=1, le=40)


class AssignmentIn(BaseModel):
    guest_id: UUID
    table_id: UUID
    locked: bool = False


class AssignmentsIn(BaseModel):
    assignments: list[AssignmentIn] = Field(max_length=1000)
    replace_unlocked: bool = Field(
        default=True, description="Usuń dotychczasowe nieprzypięte przypisania przed zapisem"
    )


class ClearIn(BaseModel):
    include_locked: bool = False


class RuleCreate(BaseModel):
    kind: Literal["together", "apart"]
    guest_a_id: UUID
    guest_b_id: UUID
    note: str | None = Field(default=None, max_length=200)


class RuleOut(BaseModel):
    id: UUID
    kind: Literal["together", "apart"]
    guest_a_id: UUID
    guest_b_id: UUID
    note: str | None


class AutoIn(BaseModel):
    basis: Basis = Field(
        default="not_declined",
        description="not_declined: wszyscy poza odmowami; attending: tylko potwierdzeni",
    )
    keep_households: bool = True
    kids_table: bool = Field(default=True, description="Dzieci przy stole dziecięcym, jeśli jest")
    kids_table_teens: bool = Field(
        default=False, description="Przy stole dziecięcym także nastolatki (13-17), po dzieciach"
    )
    time_limit_seconds: int = Field(default=10, ge=1, le=20)
    near_groups: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Grupy gości (etykiety zaproszeń) jak najbliżej celu, np. „Rodzina Ani”",
    )
    near_target: Literal["head", "dance_floor"] = Field(
        default="head", description="Stół pary młodej albo parkiet (wg planu sali)"
    )
    dry_run: bool = True


class AutoRunOut(BaseModel):
    id: UUID
    status: Literal["queued", "running", "done", "failed"]
    error_code: str | None
    error_message: str | None
    result: "AutoResult | None" = Field(description="Propozycja (status done)")


class AssignmentOut(BaseModel):
    guest_id: UUID
    table_id: UUID
    locked: bool


class AutoResult(BaseModel):
    status: Literal["optimal", "feasible"]
    assignments: list["AssignmentOut"]
    issues: list[IssueOut]
    split_households: list[UUID]
    near_applied: bool = False


class AutoOut(BaseModel):
    dry_run: bool
    status: Literal["optimal", "feasible"]
    assignments: list[AssignmentOut]
    issues: list[IssueOut]
    split_households: list[UUID]
    near_applied: bool = Field(
        default=False,
        description="Czy uwzględniono „blisko”: wymaga pozycji stołów i celu na planie sali",
    )
    note: str = (
        "Propozycja do dopracowania: przypięte ręcznie miejsca zostały zachowane. "
        "Dokładnie ten wariant zapiszesz przez PUT …/seating/assignments."
    )


class SeatNumbersIn(BaseModel):
    table_id: UUID | None = Field(default=None, description="Domyślnie wszystkie stoły")
    keep_existing: bool = Field(default=True, description="Zachowaj wpisane już numery miejsc")
    dry_run: bool = False


class SeatNumber(BaseModel):
    guest_id: UUID
    table_id: UUID
    seat_number: int


class SeatNumbersOut(BaseModel):
    dry_run: bool
    seats: list[SeatNumber]
