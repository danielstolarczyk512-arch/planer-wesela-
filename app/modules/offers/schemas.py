from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.core.schemas import Money, PatchModel

ComponentKind = Literal[
    "per_guest", "per_child", "per_crew", "fixed", "per_hour", "per_unit", "percent"
]
Confidence = Literal["high", "medium", "low", "unverified"]
OfferStatus = Literal["draft", "needs_review", "approved", "selected", "rejected"]
EventKind = Literal["ceremony", "reception", "after_party"]
TermType = Literal[
    "deposit", "payment_schedule", "cancellation", "menu", "drinks", "corkage", "overtime", "other"
]
PaymentKind = Literal["deposit_zadatek", "advance_zaliczka", "installment", "final", "other"]
GuestBasis = Literal["planned", "invited", "confirmed"]
Quantity = Annotated[Decimal, Field(ge=0, le=100_000, max_digits=10, decimal_places=2)]


class Citation(BaseModel):
    """Źródło informacji w dokumencie: strona i dosłowny fragment."""

    page: int | None = Field(default=None, ge=1, le=1000)
    quote: str = Field(min_length=1, max_length=500)


class ComponentIn(BaseModel):
    label: str = Field(min_length=1, max_length=200, examples=["Menu weselne"])
    kind: ComponentKind
    amount: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)] | None = Field(
        default=None, description="Kwota (dla percent: procent). Brak = nieznana kwota."
    )
    quantity: Quantity | None = None
    included: bool = False
    optional: bool = False
    event_kind: EventKind | None = None
    citation: Citation | None = None
    confidence: Confidence = "high"

    @model_validator(mode="after")
    def _percent(self) -> Self:
        if self.kind == "percent" and self.amount is not None and self.amount > 100:
            raise ValueError("Procent nie może przekraczać 100.")
        return self


class Installment(BaseModel):
    kind: PaymentKind
    amount: Money
    due_date: date | None = None
    days_before_wedding: int | None = Field(default=None, ge=-60, le=1000)

    @model_validator(mode="after")
    def _when(self) -> Self:
        if self.due_date is not None and self.days_before_wedding is not None:
            raise ValueError("Podaj due_date albo days_before_wedding, nie oba.")
        return self


class TermIn(BaseModel):
    term_type: TermType
    text: str | None = Field(default=None, max_length=2000, description="Opis z oferty")
    amount: Money | None = Field(default=None, description="np. zadatek, korkowe, nadgodzina")
    deposit_kind: Literal["deposit_zadatek", "advance_zaliczka"] | None = None
    due_date: date | None = None
    installments: list[Installment] = Field(default_factory=list, max_length=24)
    citation: Citation | None = None
    confidence: Confidence = "high"

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if self.term_type == "deposit" and (self.amount is None or self.deposit_kind is None):
            raise ValueError("Zadatek/zaliczka wymaga amount i deposit_kind.")
        if self.term_type == "payment_schedule" and not self.installments:
            raise ValueError("Harmonogram płatności wymaga listy installments.")
        return self


class OfferCreate(BaseModel):
    vendor_id: UUID
    title: str = Field(min_length=1, max_length=200)
    valid_until: date | None = None
    min_guests: int | None = Field(default=None, ge=0, le=2000)
    notes: str | None = Field(default=None, max_length=4000)
    source_document_version_id: UUID | None = None
    status: Literal["draft", "approved"] = Field(
        default="approved", description="Oferta wpisana ręcznie jest od razu zatwierdzona"
    )
    components: list[ComponentIn] = Field(default_factory=list, max_length=100)
    terms: list[TermIn] = Field(default_factory=list, max_length=50)


class OfferUpdate(PatchModel):
    NOT_NULL = ("title", "components", "terms")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    valid_until: date | None = None
    min_guests: int | None = Field(default=None, ge=0, le=2000)
    notes: str | None = Field(default=None, max_length=4000)
    components: list[ComponentIn] | None = Field(
        default=None, max_length=100, description="Zastępuje całą listę"
    )
    terms: list[TermIn] | None = Field(
        default=None, max_length=50, description="Zastępuje całą listę"
    )


class ComponentOut(ComponentIn):
    id: UUID


class TermOut(TermIn):
    id: UUID


class OfferOut(BaseModel):
    id: UUID
    vendor_id: UUID
    vendor_name: str
    vendor_category: str
    title: str
    valid_until: date | None
    min_guests: int | None
    notes: str | None
    status: OfferStatus
    source: str
    source_document_version_id: UUID | None
    components: list[ComponentOut]
    terms: list[TermOut]
    unverified_fields: int
    selected_budget_item_id: UUID | None
    version: int
    updated_at: datetime


class ApproveIn(BaseModel):
    confirm_unverified: bool = Field(
        default=False, description="Potwierdzam pola oznaczone jako niepewne/niezweryfikowane"
    )


class CompareIn(BaseModel):
    offer_ids: list[UUID] = Field(min_length=1, max_length=10)
    guest_basis: GuestBasis = "planned"
    adults: int | None = Field(default=None, ge=0, le=2000, description="Nadpisuje liczbę")
    children: int | None = Field(default=None, ge=0, le=500)
    after_party_adults: int | None = Field(default=None, ge=0, le=2000)
    after_party_children: int | None = Field(default=None, ge=0, le=500)
    hours: Quantity | None = None
    include_optional: bool = False
    crew: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Posiłki dla obsługi; domyślnie suma z usługodawców (bez odrzuconych)",
    )


class ScenarioIn(BaseModel):
    label: str = Field(min_length=1, max_length=40, examples=["Plan", "Co jeśli +20 gości"])
    guest_basis: GuestBasis = "planned"
    adults: int | None = Field(default=None, ge=0, le=2000)
    children: int | None = Field(default=None, ge=0, le=500)
    after_party_adults: int | None = Field(default=None, ge=0, le=2000)
    after_party_children: int | None = Field(default=None, ge=0, le=500)
    hours: Quantity | None = None
    include_optional: bool = False
    crew: int | None = Field(default=None, ge=0, le=100)


class ScenariosIn(BaseModel):
    offer_ids: list[UUID] = Field(min_length=1, max_length=10)
    scenarios: list[ScenarioIn] = Field(
        min_length=2, max_length=3, description="Pierwszy scenariusz jest punktem odniesienia"
    )


class PlannedPayment(BaseModel):
    kind: PaymentKind
    amount: Money
    due_date: date | None
    computed: bool = Field(description="Dopłata wyliczona (suma - kwoty stałe), nie z oferty")


class ScenarioQuote(BaseModel):
    label: str
    adults: int
    children: int
    total: Money
    difference_to_first: Money
    final_payment: Money = Field(description="Dopłata: suma - zadatek - raty stałe")
    final_difference_to_first: Money
    payments: list[PlannedPayment]
    unknown: list[str]
    warnings: list[str]


class OfferScenarios(BaseModel):
    offer_id: UUID
    vendor_name: str
    title: str
    scenarios: list[ScenarioQuote]


class ScenariosOut(BaseModel):
    results: list[OfferScenarios]
    disclaimer: str = (
        "Wyliczenie z ofert zatwierdzonych przez Was. Terminy i kwoty rat: jak w ofercie; dopłata "
        "to różnica między kosztem a kwotami stałymi. Wiążąca jest treść umowy."
    )


class QuoteLine(BaseModel):
    label: str
    kind: str
    amount: Decimal
    quantity: Decimal
    subtotal: Money
    note: str | None


class OfferQuote(BaseModel):
    offer_id: UUID
    vendor_name: str
    title: str
    total: Money
    per_adult_effective: Money | None
    difference_to_cheapest: Money
    lines: list[QuoteLine]
    unknown: list[str]
    optional_excluded: list[str]
    warnings: list[str]
    missing_terms: list[str]


class CompareOut(BaseModel):
    scenario: dict[str, Any]
    results: list[OfferQuote]
    cheapest_offer_id: UUID | None
    disclaimer: str = (
        "Wyliczenie na podstawie danych ofert zatwierdzonych przez Was. Pozycje „nieznane” nie "
        "są wliczone. To nie jest porada prawna ani finansowa: wiążąca jest treść umowy."
    )


class SelectIn(BaseModel):
    budget_category_id: UUID | None = Field(
        default=None, description="Domyślnie kategoria wynikająca z kategorii usługodawcy"
    )
    guest_basis: GuestBasis = "planned"
    create_payments: bool = True
    reject_competing: bool = Field(
        default=True, description="Odrzuć inne oferty tej samej kategorii usługodawców"
    )


class SelectOut(BaseModel):
    offer_id: UUID
    budget_item_id: UUID
    planned_amount: Money
    payments_created: int
    rejected_offers: int
    warnings: list[str]
