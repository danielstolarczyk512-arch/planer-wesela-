from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.core.schemas import Money, PatchModel, SignedMoney

CostMode = Literal["fixed", "per_guest"]
GuestBasis = Literal["planned", "invited", "confirmed"]
ItemStatus = Literal["planned", "confirmed", "paid", "cancelled"]
PaymentStatus = Literal["scheduled", "paid", "cancelled", "refunded"]
PaymentKind = Literal["deposit_zadatek", "advance_zaliczka", "installment", "final", "other"]

PAYMENT_KIND_HELP = (
    "deposit_zadatek: zadatek (art. 394 KC), przy rezygnacji z winy wpłacającego zwykle "
    "przepada. advance_zaliczka: zaliczka, co do zasady podlega zwrotowi. Informacja ogólna, "
    "nie porada prawna: o skutkach decyduje treść umowy."
)


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    planned: Money = Field(default_factory=lambda: Money(amount=Decimal("0")))
    sort_order: int = Field(default=100, ge=0, le=10_000)
    is_reserve: bool = False


class CategoryUpdate(PatchModel):
    NOT_NULL = ("name", "planned", "sort_order", "is_reserve")

    name: str | None = Field(default=None, min_length=1, max_length=80)
    planned: Money | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    is_reserve: bool | None = None


class CategoryOut(BaseModel):
    id: UUID
    name: str
    planned: Money
    sort_order: int
    is_reserve: bool
    version: int


Indexation = Literal["none", "cpi", "price_list", "cap"]


class ItemCreate(BaseModel):
    category_id: UUID
    name: str = Field(min_length=1, max_length=200)
    cost_mode: CostMode = "fixed"
    planned: Money | None = Field(default=None, description="Kwota dla cost_mode=fixed")
    unit_price: Money | None = Field(default=None, description="Cena za osobę (per_guest)")
    child_unit_price: Money | None = Field(
        default=None,
        description=(
            "Cena za dziecko 4-12 lat (per_guest, liczby zaproszonych/potwierdzonych). "
            "Nastolatki jak dorośli, maluchy bez opłaty. Przy liczbie planowanej — bez podziału."
        ),
    )
    guest_basis: GuestBasis | None = Field(
        default=None, description="Którą liczbę gości użyć dla per_guest"
    )
    confirmed: Money | None = None
    actual: Money | None = None
    status: ItemStatus = "planned"
    notes: str | None = Field(default=None, max_length=4000)

    indexation: Indexation = Field(
        default="none",
        description="Waloryzacja ceny w umowie: none, cpi (inflacja GUS), "
        "price_list (cennik z roku "
        "wesela), cap (limit procentowy łącznie)",
    )
    indexation_cap_percent: Decimal | None = Field(
        default=None, ge=0, le=100, description="Dla cap: maksymalna podwyżka łącznie, %"
    )
    price_fixed_on: date | None = Field(default=None, description="Od kiedy obowiązuje cena")
    price_review_on: date | None = Field(
        default=None, description="Termin aneksu / potwierdzenia ceny (przypomnienie)"
    )

    @model_validator(mode="after")
    def _mode_fields(self) -> Self:
        if self.cost_mode == "fixed" and self.planned is None:
            raise ValueError("Dla kosztu stałego podaj planned.")
        if self.cost_mode == "per_guest" and (self.unit_price is None or not self.guest_basis):
            raise ValueError("Dla kosztu za osobę podaj unit_price i guest_basis.")
        return self


class ItemUpdate(PatchModel):
    NOT_NULL = ("category_id", "name", "cost_mode", "status", "indexation")

    category_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    cost_mode: CostMode | None = None
    planned: Money | None = None
    unit_price: Money | None = None
    child_unit_price: Money | None = None
    guest_basis: GuestBasis | None = None
    confirmed: Money | None = None
    actual: Money | None = None
    status: ItemStatus | None = None
    notes: str | None = Field(default=None, max_length=4000)
    indexation: Indexation | None = Field(
        default=None,
        description="Waloryzacja ceny w umowie: none, cpi (inflacja GUS), "
        "price_list (cennik z roku "
        "wesela), cap (limit procentowy łącznie)",
    )
    indexation_cap_percent: Decimal | None = Field(
        default=None, ge=0, le=100, description="Dla cap: maksymalna podwyżka łącznie, %"
    )
    price_fixed_on: date | None = Field(default=None, description="Od kiedy obowiązuje cena")
    price_review_on: date | None = Field(
        default=None, description="Termin aneksu / potwierdzenia ceny (przypomnienie)"
    )


class ItemOut(BaseModel):
    id: UUID
    category_id: UUID
    name: str
    cost_mode: CostMode
    planned: Money | None
    unit_price: Money | None
    child_unit_price: Money | None
    guest_basis: GuestBasis | None
    guest_count_used: int | None
    children_used: int | None = Field(
        default=None, description="Ile dzieci policzono po cenie dziecięcej (gdy jest ustawiona)"
    )
    confirmed: Money | None
    actual: Money | None
    estimated: Money = Field(description="Koszt szacowany: rzeczywisty → potwierdzony → plan")
    paid: Money
    status: ItemStatus
    notes: str | None
    indexation: Indexation = "none"
    indexation_cap_percent: Decimal | None = None
    price_fixed_on: date | None = None
    price_review_on: date | None = None
    version: int


class PaymentCreate(BaseModel):
    kind: PaymentKind = Field(description=PAYMENT_KIND_HELP)
    amount: Money
    due_date: date | None = None
    paid_on: date | None = Field(default=None, description="Podaj, jeśli już zapłacono")
    notes: str | None = Field(default=None, max_length=2000)
    funder_id: UUID | None = Field(default=None, description="Kto płaci; puste = para")

    @model_validator(mode="after")
    def _positive(self) -> Self:
        if self.amount.amount <= 0:
            raise ValueError("Kwota płatności musi być dodatnia.")
        return self


class PaymentUpdate(PatchModel):
    NOT_NULL = ("kind", "amount", "status")

    kind: PaymentKind | None = None
    amount: Money | None = None
    due_date: date | None = None
    status: Literal["scheduled", "cancelled", "refunded"] | None = None
    notes: str | None = Field(default=None, max_length=2000)
    funder_id: UUID | None = Field(default=None, description="Kto płaci; null = para")


class MarkPaidIn(BaseModel):
    paid_on: date | None = Field(default=None, description="Domyślnie dzisiaj")


class PaymentOut(BaseModel):
    id: UUID
    budget_item_id: UUID
    item_name: str
    kind: PaymentKind
    amount: Money
    due_date: date | None
    paid_on: date | None
    status: PaymentStatus
    is_overdue: bool
    notes: str | None
    funder_id: UUID | None = None
    version: int


class CategorySummary(BaseModel):
    id: UUID
    name: str
    planned: Money
    estimated: Money
    paid: Money
    over_plan: bool


class GuestCounts(BaseModel):
    planned: int
    invited: int
    confirmed: int


class BudgetOverview(BaseModel):
    total_budget: Money | None
    guest_counts: GuestCounts
    planned_in_categories: Money
    estimated_total: Money
    paid_total: Money
    remaining_to_pay: Money
    unallocated: SignedMoney | None = Field(
        description="Budżet minus szacowane koszty (ujemne = przekroczenie)"
    )
    over_budget: bool
    reserve_planned: Money
    cost_per_guest: Money | None
    cost_per_guest_basis: GuestBasis | None
    overdue_payments: list[PaymentOut]
    upcoming_payments_30d: list[PaymentOut]
    categories: list[CategorySummary]


class SplitIn(BaseModel):
    dry_run: bool = True


class SplitProposal(BaseModel):
    category_id: UUID
    name: str
    share_percent: Decimal
    old_planned: Money
    new_planned: Money


class SplitOut(BaseModel):
    dry_run: bool
    proposals: list[SplitProposal]
    note: str = (
        "Podział orientacyjny (hipoteza zespołu, nie dane rynkowe). Zmienia tylko kategorie "
        "domyślne; wszystkie kwoty można edytować."
    )


class HistoryEntry(BaseModel):
    occurred_at: datetime
    actor_id: UUID | None
    action: str
    entity_type: str
    entity_id: str | None
    changes: dict[str, Any] | None


# --- portfel sponsorów -------------------------------------------------------------------

FunderSide = Literal["bride", "groom", "both", "other"]


class FunderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120, examples=["Rodzice Panny Młodej"])
    side: FunderSide = "both"
    pledged_amount: Money | None = Field(default=None, description="Ile obiecali dołożyć")
    notes: str | None = Field(default=None, max_length=2000)


class FunderUpdate(PatchModel):
    NOT_NULL = ("name", "side")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    side: FunderSide | None = None
    pledged_amount: Money | None = None
    notes: str | None = Field(default=None, max_length=2000)


class FunderSummary(BaseModel):
    id: UUID
    name: str
    side: FunderSide
    pledged_amount: Money | None
    notes: str | None
    position: int
    version: int
    paid_direct: Money = Field(description="Zapłacone przez sponsora bezpośrednio firmom")
    scheduled_direct: Money = Field(
        description="Płatności przypisane sponsorowi, jeszcze do zapłaty"
    )
    given: Money = Field(description="Pieniądze przekazane parze (potwierdzone)")
    reported: Money = Field(description="Zgłoszone przez sponsora, czekają na potwierdzenie pary")
    covered: Money = Field(description="Zapłacone + przekazane")
    to_settle: SignedMoney | None = Field(
        description="Obiecane - (zapłacone + przekazane + zaplanowane); ujemne = ponad obietnicę"
    )


class FundersOverview(BaseModel):
    funders: list[FunderSummary]
    pledged_total: Money
    covered_total: Money
    couple_paid: Money = Field(description="Płatności bez sponsora (para), zapłacone")
    couple_scheduled: Money


class FunderPayment(BaseModel):
    id: UUID
    item_name: str
    kind: PaymentKind
    amount: Money
    due_date: date | None
    paid_on: date | None
    status: PaymentStatus


class ContributionCreate(BaseModel):
    amount: Money
    received_on: date | None = None
    note: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _positive(self) -> Self:
        if self.amount.amount <= 0:
            raise ValueError("Kwota wpłaty musi być dodatnia.")
        return self


class ContributionOut(BaseModel):
    id: UUID
    amount: Money
    received_on: date | None
    note: str | None
    status: Literal["confirmed", "reported"] = "confirmed"


class FunderDetail(BaseModel):
    funder: FunderSummary
    payments: list[FunderPayment]
    contributions: list[ContributionOut]


# --- strażnik waloryzacji ------------------------------------------------------------------


class IndexationItem(BaseModel):
    item_id: UUID
    name: str
    indexation: Indexation
    indexation_cap_percent: Decimal | None
    price_fixed_on: date | None
    price_review_on: date | None
    remaining: Money = Field(description="Jeszcze niezapłacona część (tylko ją obejmie podwyżka)")
    years: Decimal | None = Field(description="Lata od ustalenia ceny do ślubu")
    expected_increase: Money
    worst_increase: Money


class IndexationOverview(BaseModel):
    expected_rate: float
    worst_rate: float
    wedding_day: date | None
    approximate: bool
    today_total: Money = Field(description="Szacowany koszt wesela dziś")
    expected_total: Money = Field(description="Z prognozowanymi podwyżkami")
    worst_total: Money = Field(description="Najgorszy przypadek")
    items: list[IndexationItem]
    reviews_soon: list[IndexationItem] = Field(
        description="Terminy aneksów w ciągu 30 dni lub minione"
    )


# --- plan wydatków i koszt gościa --------------------------------------------------------------


class CashflowMonth(BaseModel):
    month: date = Field(description="Pierwszy dzień miesiąca")
    couple: Money = Field(description="Zaplanowane płatności pary")
    sponsors: Money = Field(description="Zaplanowane płatności przypisane sponsorom")
    total: Money


class Cashflow(BaseModel):
    months: list[CashflowMonth]
    overdue: Money = Field(description="Niezapłacone płatności z datą w przeszłości")
    undated: Money = Field(description="Zaplanowane płatności bez terminu")
    not_scheduled: Money = Field(description="Część kosztu bez żadnej zaplanowanej płatności")
    pledged_open: Money = Field(
        description="Deklaracje sponsorów jeszcze bez przypisanych płatności"
    )
    couple_need: Money = Field(description="Ile para musi jeszcze zapłacić sama")
    saving_months: int = Field(description="Miesiące do ślubu (z bieżącym)")
    saving_per_month: Money | None = Field(description="Ile odkładać miesięcznie")
    peak_month: date | None = Field(description="Miesiąc z najwyższymi płatnościami pary")


class GuestCostSource(BaseModel):
    name: str
    per_adult: Money
    per_child: Money


class GuestCost(BaseModel):
    average: Money | None = Field(description="Szacowany koszt wesela ÷ goście")
    average_basis: str | None = Field(description="confirmed / invited / planned")
    adults: int
    children: int
    per_adult: Money = Field(description="O ile wzrośnie koszt z jedną dorosłą osobą więcej")
    per_child: Money = Field(description="O ile wzrośnie koszt z jednym dzieckiem więcej")
    sources: list[GuestCostSource]
