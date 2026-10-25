from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin

VENDOR_STATUSES = ("considering", "contacted", "offer_received", "booked", "rejected")
CHECKLIST_KINDS = ("question", "contract")
CHECKLIST_STATUSES = ("open", "ok", "missing")

# Kategorie usługodawców (slug → nazwa) i domyślna kategoria budżetu przy wyborze oferty.
CATEGORIES: dict[str, tuple[str, str]] = {
    "venue": ("Sala weselna", "Sala i catering"),
    "catering": ("Catering", "Sala i catering"),
    "photographer": ("Fotograf", "Foto i wideo"),
    "videographer": ("Filmowiec", "Foto i wideo"),
    "dj": ("DJ", "Muzyka"),
    "band": ("Zespół", "Muzyka"),
    "musician": ("Muzyk (saksofon, skrzypce)", "Muzyka"),
    "florist": ("Florystyka", "Dekoracje i kwiaty"),
    "decorations": ("Dekoracje", "Dekoracje i kwiaty"),
    "wedding_planner": ("Wedding planner", "Inne"),
    "bartender": ("Barman", "Atrakcje"),
    "photobooth": ("Fotobudka", "Atrakcje"),
    "attractions": ("Atrakcje weselne", "Atrakcje"),
    "cake": ("Tort", "Sala i catering"),
    "sweet_table": ("Słodki stół", "Sala i catering"),
    "transport": ("Transport", "Transport"),
    "accommodation": ("Noclegi", "Noclegi"),
    "makeup": ("Makijaż", "Strój i uroda"),
    "hairdresser": ("Fryzjer", "Strój i uroda"),
    "dress": ("Suknia ślubna", "Strój i uroda"),
    "suit": ("Garnitur", "Strój i uroda"),
    "jeweler": ("Jubiler (obrączki)", "Obrączki"),
    "invitations": ("Zaproszenia", "Papeteria"),
    "stationery": ("Papeteria", "Papeteria"),
    "other": ("Inne", "Inne"),
}


class Vendor(IdMixin, TimestampMixin, Base):
    """„Mój usługodawca”: prywatny dla wesela, dodany przez parę (nie katalog publiczny)."""

    __tablename__ = "vendors"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(32), default="other")
    website_url: Mapped[str | None] = mapped_column(String(300))
    website_domain: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(32))
    phone_normalized: Mapped[str | None] = mapped_column(String(20))
    city: Mapped[str | None] = mapped_column(String(120))
    nip: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(16), default="considering")
    notes: Mapped[str | None] = mapped_column(Text)
    # Ile osób obsługi (muzycy, fotograf) je posiłek na sali: koszt w ofercie sali (per_crew).
    crew_meals: Mapped[int | None] = mapped_column(Integer)
    # Jawne powiązanie z firmą z katalogu (ADR-0008); aktualizacja katalogu nie rusza notatek.
    catalog_vendor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("catalog_vendors.id", ondelete="SET NULL"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(f"status IN {VENDOR_STATUSES}", name="status"),
        CheckConstraint("crew_meals IS NULL OR crew_meals BETWEEN 0 AND 50", name="crew_meals"),
        CheckConstraint(f"category IN {tuple(CATEGORIES)}", name="category"),
        Index("ix_vendors_wedding_category", "wedding_id", "category"),
        Index(
            "ix_vendors_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )


class VendorChecklistItem(IdMixin, TimestampMixin, Base):
    """Pytanie do usługodawcy (z odpowiedzią) albo punkt listy kontrolnej umowy.

    Lista umowy zapisuje tylko, czy zapis jest w umowie (ok/brak) — bez oceny prawnej.
    """

    __tablename__ = "vendor_checklist_items"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    vendor_id: Mapped[UUID] = mapped_column(
        ForeignKey("vendors.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16))
    code: Mapped[str | None] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(String(300))
    answer: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(f"kind IN {CHECKLIST_KINDS}", name="kind"),
        CheckConstraint(f"status IN {CHECKLIST_STATUSES}", name="status"),
        Index("ix_vendor_checklist_wedding_kind", "wedding_id", "kind"),
    )
