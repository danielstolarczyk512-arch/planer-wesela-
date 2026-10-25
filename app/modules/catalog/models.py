"""Wspólny katalog firm: publiczne fakty z dowodami, niezależny od prywatnych danych wesel.

Żadna tabela tego modułu nie ma `wedding_id`: katalog nie zawiera budżetów, wiadomości ani
indywidualnych wycen (ADR-0008). Prywatny `Vendor` wskazuje firmę jawnie (`catalog_vendor_id`).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow
from app.modules.vendors.models import CATEGORIES

PUBLICATION_STATUSES = ("draft", "published", "needs_review", "hidden")
SOURCE_STATES = ("active", "paused", "blocked", "gone", "failed")
FACT_FIELDS = ("name", "phone", "email", "website", "city", "service_area", "social")
# Weryfikacja faktu: auto = odczytany z dozwolonego źródła, conflict = sprzeczny z innym źródłem,
# confirmed = potwierdzony przez administratora.
VERIFICATIONS = ("auto", "confirmed", "conflict")
PACKAGE_KINDS = ("package", "surcharge")
PRICE_UNITS = ("unspecified", "package", "hour", "person", "day", "event", "km")
REVIEW_KINDS = ("conflict", "ambiguous_merge", "weak_evidence", "source_problem")
REVIEW_STATES = ("open", "resolved")


class CatalogVendor(IdMixin, TimestampMixin, Base):
    __tablename__ = "catalog_vendors"

    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(32))
    city: Mapped[str | None] = mapped_column(String(120))
    service_area: Mapped[str | None] = mapped_column(String(300))
    publication_status: Mapped[str] = mapped_column(String(16), default="draft")
    # Opisy stylu potwierdzone przez człowieka (np. „reportaż”); dopasowanie nie czyta obrazów.
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    # Scalenie jest odwracalne: firma scalona zostaje w bazie i wskazuje docelową.
    merged_into_id: Mapped[UUID | None] = mapped_column(ForeignKey("catalog_vendors.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(f"publication_status IN {PUBLICATION_STATUSES}", name="publication_status"),
        CheckConstraint(f"category IN {tuple(CATEGORIES)}", name="category"),
        Index("ix_catalog_vendors_category_status", "category", "publication_status"),
        Index(
            "ix_catalog_vendors_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )


class VendorSource(IdMixin, TimestampMixin, Base):
    """Adres strony firmy podany przez administratora. Aktualizujemy tylko takie źródła."""

    __tablename__ = "catalog_sources"

    catalog_vendor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("catalog_vendors.id", ondelete="SET NULL"), index=True
    )
    url: Mapped[str] = mapped_column(String(500), unique=True)
    domain: Mapped[str] = mapped_column(String(200), index=True)
    platform: Mapped[str] = mapped_column(String(24), default="website")
    # Podstawa dostępu: dlaczego wolno pobierać tę stronę (wpisuje administrator).
    access_basis: Mapped[str] = mapped_column(
        String(300), default="strona firmy podana przez administratora"
    )
    category: Mapped[str] = mapped_column(String(32))
    region_hint: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(16), default="active")
    state_reason: Mapped[str | None] = mapped_column(String(300))
    refresh_interval_days: Mapped[int] = mapped_column(Integer, default=14)
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_content_hash: Mapped[str | None] = mapped_column(String(64))
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[UUID | None] = mapped_column()

    __table_args__ = (
        CheckConstraint(f"state IN {SOURCE_STATES}", name="state"),
        CheckConstraint(f"category IN {tuple(CATEGORIES)}", name="category"),
        CheckConstraint("refresh_interval_days BETWEEN 1 AND 365", name="refresh_interval"),
        Index("ix_catalog_sources_due", "next_check_at", postgresql_where="state = 'active'"),
    )


class SourceObservation(IdMixin, Base):
    """Jedno pobranie (także nieudane — liczy się do dziennego limitu)."""

    __tablename__ = "catalog_observations"

    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_sources.id", ondelete="CASCADE"), index=True
    )
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    http_status: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(24))
    final_url: Mapped[str | None] = mapped_column(String(500))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    parser_version: Mapped[str | None] = mapped_column(String(16))
    # Ograniczony wyciąg tekstu strony jako dowód; czyszczony po okresie retencji.
    excerpt: Mapped[str | None] = mapped_column(Text)
    unchanged: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_catalog_observations_fetched", "fetched_at"),)


class VendorFact(IdMixin, Base):
    """Pojedynczy fakt o firmie z dowodem. Zmiana wartości zamyka stary fakt (historia)."""

    __tablename__ = "catalog_facts"

    catalog_vendor_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_vendors.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("catalog_sources.id", ondelete="SET NULL")
    )
    observation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("catalog_observations.id", ondelete="SET NULL")
    )
    field: Mapped[str] = mapped_column(String(24))
    value: Mapped[str] = mapped_column(String(500))
    evidence: Mapped[str | None] = mapped_column(String(600))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification: Mapped[str] = mapped_column(String(12), default="auto")
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"field IN {FACT_FIELDS}", name="field"),
        CheckConstraint(f"verification IN {VERIFICATIONS}", name="verification"),
        Index("ix_catalog_facts_vendor_current", "catalog_vendor_id", "is_current"),
    )


class PublicPackage(IdMixin, Base):
    """Publiczna oferta/pakiet z cennika firmy. To nie jest wycena na konkretne wesele."""

    __tablename__ = "catalog_packages"

    catalog_vendor_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog_vendors.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("catalog_sources.id", ondelete="SET NULL"), index=True
    )
    observation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("catalog_observations.id", ondelete="SET NULL")
    )
    key: Mapped[str] = mapped_column(String(200))  # rodzaj|nazwa|jednostka|sezon — tożsamość
    kind: Mapped[str] = mapped_column(String(12), default="package")  # pakiet albo dopłata
    name: Mapped[str] = mapped_column(String(160))
    price_from: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    price_to: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="PLN")
    unit: Mapped[str] = mapped_column(String(16), default="unspecified")
    # Brak sezonu jest jawny: cena publiczna nie obiecuje wyceny na konkretną datę.
    season: Mapped[str | None] = mapped_column(String(40))
    scope: Mapped[str | None] = mapped_column(String(600))
    evidence: Mapped[str] = mapped_column(String(600))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification: Mapped[str] = mapped_column(String(12), default="auto")
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersede_reason: Mapped[str | None] = mapped_column(String(24))

    __table_args__ = (
        CheckConstraint(f"unit IN {PRICE_UNITS}", name="unit"),
        CheckConstraint(f"kind IN {PACKAGE_KINDS}", name="kind"),
        CheckConstraint(f"verification IN {VERIFICATIONS}", name="verification"),
        CheckConstraint(
            "price_from IS NULL OR price_to IS NULL OR price_to >= price_from", name="price_range"
        ),
        Index("ix_catalog_packages_vendor_current", "catalog_vendor_id", "is_current"),
    )


class ReviewItem(IdMixin, TimestampMixin, Base):
    """Kolejka weryfikacji: konflikty, niejednoznaczne scalenia, słabe dowody, problemy źródeł."""

    __tablename__ = "catalog_review_items"

    kind: Mapped[str] = mapped_column(String(24))
    catalog_vendor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("catalog_vendors.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("catalog_sources.id", ondelete="SET NULL")
    )
    summary: Mapped[str] = mapped_column(String(400))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Unikalny klucz otwartego problemu: powtórne pobranie nie mnoży identycznych wpisów.
    dedupe_key: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(12), default="open")
    resolution: Mapped[str | None] = mapped_column(String(300))
    resolved_by: Mapped[UUID | None] = mapped_column()
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"kind IN {REVIEW_KINDS}", name="kind"),
        CheckConstraint(f"state IN {REVIEW_STATES}", name="state"),
        Index(
            "uq_catalog_review_open_key",
            "dedupe_key",
            unique=True,
            postgresql_where="state = 'open'",
        ),
    )


class DomainState(Base):
    """Obciążenie domeny: odstęp między pobraniami i wyłącznik awaryjny (circuit breaker)."""

    __tablename__ = "discovery_domains"

    domain: Mapped[str] = mapped_column(String(200), primary_key=True)
    last_fetch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    circuit_open_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_after_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    robots_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    robots_txt: Mapped[str | None] = mapped_column(Text)


class DiscoveryControl(Base):
    """Jeden wiersz (id=1): pauza, limity i tętno procesów badacza."""

    __tablename__ = "discovery_control"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    daily_fetch_limit: Mapped[int] = mapped_column(Integer, default=100)
    worker_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduler_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[UUID | None] = mapped_column()

    __table_args__ = (
        CheckConstraint("id = 1", name="single_row"),
        CheckConstraint("daily_fetch_limit BETWEEN 0 AND 10000", name="daily_limit"),
    )
