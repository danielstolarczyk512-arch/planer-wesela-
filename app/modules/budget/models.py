from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin

COST_MODES = ("fixed", "per_guest")
GUEST_BASES = ("planned", "invited", "confirmed")
ITEM_STATUSES = ("planned", "confirmed", "paid", "cancelled")
PAYMENT_KINDS = ("deposit_zadatek", "advance_zaliczka", "installment", "final", "other")
PAYMENT_STATUSES = ("scheduled", "paid", "cancelled", "refunded")
FUNDER_SIDES = ("bride", "groom", "both", "other")
# Klauzula waloryzacji ceny w umowie: stała cena, inflacja GUS, cennik z roku wesela, limit %.
INDEXATION_KINDS = ("none", "cpi", "price_list", "cap")


class BudgetCategory(IdMixin, TimestampMixin, Base):
    __tablename__ = "budget_categories"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    planned_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_reserve: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        UniqueConstraint("wedding_id", "name", name="uq_budget_categories_wedding_name"),
        CheckConstraint("planned_amount >= 0", name="planned_non_negative"),
    )


class BudgetItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "budget_items"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    # NO ACTION (domyślne) zamiast RESTRICT: sprawdzane na końcu instrukcji, więc kaskadowe
    # usunięcie wesela działa; pustość kategorii przy jej usuwaniu pilnuje serwis.
    category_id: Mapped[UUID] = mapped_column(ForeignKey("budget_categories.id"))
    vendor_id: Mapped[UUID | None] = mapped_column(ForeignKey("vendors.id", ondelete="SET NULL"))
    offer_id: Mapped[UUID | None] = mapped_column(ForeignKey("offers.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(200))
    cost_mode: Mapped[str] = mapped_column(String(16), default="fixed")
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    # Opcjonalna cena za dziecko (4-12 lat) przy koszcie za osobę; maluchy bez opłaty.
    child_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    guest_basis: Mapped[str | None] = mapped_column(String(16))
    planned_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    confirmed_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    actual_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="PLN")
    status: Mapped[str] = mapped_column(String(16), default="planned")
    notes: Mapped[str | None] = mapped_column(Text)
    # Strażnik waloryzacji: rodzaj klauzuli, limit (łącznie, %), od kiedy cena, termin aneksu.
    indexation: Mapped[str] = mapped_column(String(16), default="none", server_default="none")
    indexation_cap_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    price_fixed_on: Mapped[date | None] = mapped_column(Date)
    price_review_on: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(f"cost_mode IN {COST_MODES}", name="cost_mode"),
        CheckConstraint(f"indexation IN {INDEXATION_KINDS}", name="indexation"),
        CheckConstraint(
            "indexation_cap_percent IS NULL OR indexation_cap_percent BETWEEN 0 AND 100",
            name="indexation_cap",
        ),
        CheckConstraint(f"status IN {ITEM_STATUSES}", name="status"),
        CheckConstraint(f"guest_basis IS NULL OR guest_basis IN {GUEST_BASES}", name="guest_basis"),
        CheckConstraint(
            "cost_mode <> 'per_guest' OR (unit_price IS NOT NULL AND guest_basis IS NOT NULL)",
            name="per_guest_complete",
        ),
        CheckConstraint(
            "cost_mode <> 'fixed' OR planned_amount IS NOT NULL", name="fixed_has_amount"
        ),
        CheckConstraint(
            "coalesce(unit_price, 0) >= 0 AND coalesce(planned_amount, 0) >= 0 "
            "AND coalesce(confirmed_amount, 0) >= 0 AND coalesce(actual_amount, 0) >= 0",
            name="amounts_non_negative",
        ),
        CheckConstraint(
            "child_unit_price IS NULL OR child_unit_price >= 0", name="child_price_non_negative"
        ),
        Index("ix_budget_items_wedding_category", "wedding_id", "category_id"),
    )


class Payment(IdMixin, TimestampMixin, Base):
    __tablename__ = "payments"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    budget_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("budget_items.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(24))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="PLN")
    due_date: Mapped[date | None] = mapped_column(Date)
    paid_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="scheduled")
    source: Mapped[str] = mapped_column(String(16), default="manual")
    notes: Mapped[str | None] = mapped_column(Text)
    # Kto płaci (portfel sponsorów); NULL = para.
    funder_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("funders.id", ondelete="SET NULL"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(f"kind IN {PAYMENT_KINDS}", name="kind"),
        CheckConstraint(f"status IN {PAYMENT_STATUSES}", name="status"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("status <> 'paid' OR paid_on IS NOT NULL", name="paid_has_date"),
        Index("ix_payments_wedding_status_due", "wedding_id", "status", "due_date"),
    )


class Funder(IdMixin, TimestampMixin, Base):
    """Źródło finansowania wesela poza parą, np. „Rodzice Panny Młodej” (portfel sponsorów)."""

    __tablename__ = "funders"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    side: Mapped[str] = mapped_column(String(8), default="both")
    pledged_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(f"side IN {FUNDER_SIDES}", name="side"),
        CheckConstraint("pledged_amount IS NULL OR pledged_amount >= 0", name="pledged"),
        Index("ix_funders_wedding", "wedding_id", "position"),
    )


class FunderContribution(IdMixin, TimestampMixin, Base):
    """Pieniądze przekazane parze przez sponsora (np. przelew od rodziców na konto pary)."""

    __tablename__ = "funder_contributions"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    funder_id: Mapped[UUID] = mapped_column(
        ForeignKey("funders.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    received_on: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(300))
    # Zgłoszona przez sponsora („reported”) liczy się dopiero po potwierdzeniu przez parę.
    status: Mapped[str] = mapped_column(String(12), default="confirmed", server_default="confirmed")

    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("status IN ('confirmed', 'reported')", name="status"),
    )


class BudgetAssumptions(TimestampMixin, Base):
    """Założenia pary dla strażnika waloryzacji (inflacja roczna: prognoza i najgorszy przypadek).

    Wspólne dla wszystkich urządzeń i ekranów (Budżet, Dziś). Brak wiersza = wartości domyślne.
    """

    __tablename__ = "budget_assumptions"

    wedding_id: Mapped[UUID] = mapped_column(
        ForeignKey("weddings.id", ondelete="CASCADE"), primary_key=True
    )
    expected_rate: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    worst_rate: Mapped[Decimal] = mapped_column(Numeric(4, 3))

    __table_args__ = (
        CheckConstraint("expected_rate >= 0 AND expected_rate <= 0.5", name="expected_rate"),
        CheckConstraint("worst_rate >= 0 AND worst_rate <= 0.5", name="worst_rate"),
    )
