from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, EmailStr, Field, HttpUrl

from app.core.schemas import PatchModel

# Musi odpowiadać kluczom CATEGORIES (pilnuje test test_vendor_categories_in_sync).
VendorCategory = Literal[
    "venue",
    "catering",
    "photographer",
    "videographer",
    "dj",
    "band",
    "musician",
    "florist",
    "decorations",
    "wedding_planner",
    "bartender",
    "photobooth",
    "attractions",
    "cake",
    "sweet_table",
    "transport",
    "accommodation",
    "makeup",
    "hairdresser",
    "dress",
    "suit",
    "jeweler",
    "invitations",
    "stationery",
    "other",
]
VendorStatus = Literal["considering", "contacted", "offer_received", "booked", "rejected"]
Email = Annotated[EmailStr, AfterValidator(lambda v: v.strip().lower())]
Phone = Annotated[str, Field(min_length=5, max_length=32, pattern=r"^[0-9+()\- ]+$")]
Nip = Annotated[str, Field(pattern=r"^\d{10}$", description="NIP: 10 cyfr bez kresek")]
CrewMeals = Annotated[
    int, Field(ge=0, le=50, description="Osoby obsługi jedzące posiłek na sali (np. muzycy)")
]
ChecklistKind = Literal["question", "contract"]
ChecklistStatus = Literal["open", "ok", "missing"]


class VendorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200, examples=["Dworek Pod Lipami"])
    category: VendorCategory = "other"
    website_url: HttpUrl | None = None
    email: Email | None = None
    phone: Phone | None = None
    city: str | None = Field(default=None, max_length=120)
    nip: Nip | None = None
    status: VendorStatus = "considering"
    notes: str | None = Field(default=None, max_length=4000)
    crew_meals: CrewMeals | None = None


class VendorUpdate(PatchModel):
    NOT_NULL = ("name", "category", "status")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: VendorCategory | None = None
    website_url: HttpUrl | None = None
    email: Email | None = None
    phone: Phone | None = None
    city: str | None = Field(default=None, max_length=120)
    nip: Nip | None = None
    status: VendorStatus | None = None
    notes: str | None = Field(default=None, max_length=4000)
    crew_meals: CrewMeals | None = None


class DuplicateHint(BaseModel):
    id: UUID
    name: str
    reasons: list[str]


class VendorOut(BaseModel):
    id: UUID
    name: str
    category: str
    category_label: str
    website_url: str | None
    email: str | None
    phone: str | None
    city: str | None
    nip: str | None
    status: VendorStatus
    notes: str | None
    crew_meals: int | None
    possible_duplicates: list[DuplicateHint] = Field(
        default_factory=list, description="Podobne wpisy w tym weselu (do sprawdzenia przez parę)"
    )
    version: int
    updated_at: datetime


class CategoryInfo(BaseModel):
    slug: str
    label: str
    budget_category: str


class ChecklistItemCreate(BaseModel):
    kind: ChecklistKind = "question"
    text: str = Field(min_length=1, max_length=300)


class ChecklistStandardIn(BaseModel):
    kind: ChecklistKind = "question"


class ChecklistItemUpdate(PatchModel):
    NOT_NULL = ("text", "status")

    text: str | None = Field(default=None, min_length=1, max_length=300)
    answer: str | None = Field(default=None, max_length=2000)
    status: ChecklistStatus | None = None


class ChecklistItemOut(BaseModel):
    id: UUID
    vendor_id: UUID
    kind: ChecklistKind
    code: str | None
    text: str
    answer: str | None
    status: ChecklistStatus
    version: int
