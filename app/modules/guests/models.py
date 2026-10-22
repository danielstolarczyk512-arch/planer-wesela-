from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow

SIDES = ("bride", "groom", "both", "other")
INVITATION_STATUSES = ("not_sent", "sent", "delivered")
LANGUAGES = ("pl", "en")
AGE_GROUPS = ("adult", "teen", "child", "infant")
DIETS = ("standard", "vegetarian", "vegan", "gluten_free", "other")
ATTENDANCE = ("pending", "attending", "declined", "maybe")
RESPONDED_VIA = ("couple", "rsvp_link")
GUEST_THEMES = ("classic", "garden", "modern")
RESERVE_STATUSES = ("waiting", "invited")
# Jak trafi zaproszenie: osobiście (polska tradycja), pocztą, e-mailem/linkiem, inaczej.
DELIVERY_METHODS = ("in_person", "post", "online", "other")


class Household(IdMixin, TimestampMixin, Base):
    """Gospodarstwo = jedno zaproszenie (np. „Państwo Kowalscy z dziećmi”)."""

    __tablename__ = "households"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(150))
    side: Mapped[str] = mapped_column(String(8), default="both")
    group_label: Mapped[str | None] = mapped_column(String(80))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    invitation_status: Mapped[str] = mapped_column(String(16), default="not_sent")
    rsvp_deadline: Mapped[date | None] = mapped_column(Date)
    # Język zaproszenia: e-mail z linkiem RSVP i język strony gościa.
    # NULL = automatycznie (strona wg przeglądarki gościa, e-mail po polsku).
    language: Mapped[str | None] = mapped_column(String(2))
    notes: Mapped[str | None] = mapped_column(Text)
    # Po weselu: co podarowali i czy podziękowaliśmy (lista podziękowań).
    gift_note: Mapped[str | None] = mapped_column(String(300))
    thanked: Mapped[bool] = mapped_column(Boolean, default=False)
    # Ostatnia wysyłka linku RSVP e-mailem (bez treści wiadomości).
    rsvp_emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Wręczanie zaproszeń: sposób, kto wręcza, miejscowość (bez pełnego adresu), plan i data.
    delivery_method: Mapped[str | None] = mapped_column(String(16))
    delivery_by: Mapped[str | None] = mapped_column(String(80))
    delivery_place: Mapped[str | None] = mapped_column(String(120))
    delivery_planned_on: Mapped[date | None] = mapped_column(Date)
    delivered_on: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(f"side IN {SIDES}", name="side"),
        CheckConstraint(f"invitation_status IN {INVITATION_STATUSES}", name="invitation_status"),
        CheckConstraint(f"language IS NULL OR language IN {LANGUAGES}", name="language"),
        CheckConstraint(
            f"delivery_method IS NULL OR delivery_method IN {DELIVERY_METHODS}",
            name="delivery_method",
        ),
        Index("ix_households_wedding", "wedding_id"),
    )


class Guest(IdMixin, TimestampMixin, Base):
    __tablename__ = "guests"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"))
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str | None] = mapped_column(String(80))
    age_group: Mapped[str] = mapped_column(String(8), default="adult")
    is_plus_one: Mapped[bool] = mapped_column(Boolean, default=False)
    # Osoba towarzysząca dopisana przez gościa w formularzu RSVP (gość może ją też usunąć).
    added_via_rsvp: Mapped[bool] = mapped_column(Boolean, default=False)
    dietary_preference: Mapped[str] = mapped_column(String(16), default="standard")
    # Może zawierać dane o zdrowiu (alergie, art. 9 RODO): szyfrowane AES-GCM.
    dietary_note_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    needs_accommodation: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_transport: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(f"age_group IN {AGE_GROUPS}", name="age_group"),
        CheckConstraint(f"dietary_preference IN {DIETS}", name="dietary_preference"),
        Index("ix_guests_wedding_household", "wedding_id", "household_id"),
    )


class GuestEventAttendance(Base):
    __tablename__ = "guest_event_attendance"

    guest_id: Mapped[UUID] = mapped_column(
        ForeignKey("guests.id", ondelete="CASCADE"), primary_key=True
    )
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="pending")
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_via: Mapped[str | None] = mapped_column(String(16))

    __table_args__ = (
        CheckConstraint(f"status IN {ATTENDANCE}", name="status"),
        CheckConstraint(
            f"responded_via IS NULL OR responded_via IN {RESPONDED_VIA}", name="responded_via"
        ),
    )


class RsvpToken(IdMixin, Base):
    """Link RSVP dla gospodarstwa. W bazie tylko hash tokena."""

    __tablename__ = "rsvp_tokens"

    household_id: Mapped[UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_rsvp_tokens_active_household",
            "household_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )


class GuestInfo(Base):
    """Strona informacyjna dla gości (pod linkiem RSVP): dojazd, nocleg, dress code, prezenty.

    Treść pisze para. Widoczna dla gości dopiero po opublikowaniu.
    """

    __tablename__ = "guest_info"

    wedding_id: Mapped[UUID] = mapped_column(
        ForeignKey("weddings.id", ondelete="CASCADE"), primary_key=True
    )
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    welcome: Mapped[str | None] = mapped_column(Text)
    directions: Mapped[str | None] = mapped_column(Text)
    accommodation: Mapped[str | None] = mapped_column(Text)
    transport: Mapped[str | None] = mapped_column(Text)
    dress_code: Mapped[str | None] = mapped_column(Text)
    gifts: Mapped[str | None] = mapped_column(Text)
    contact: Mapped[str | None] = mapped_column(Text)
    # Wygląd strony dla gości (Premium): motyw i kolor akcentu z palety sprawdzonej pod kontrast.
    theme: Mapped[str] = mapped_column(String(16), default="classic")
    accent: Mapped[str | None] = mapped_column(String(16))
    # Goście mogą zaproponować utwór w RSVP (para zatwierdza, zanim trafi do DJ-a).
    song_requests: Mapped[bool] = mapped_column(Boolean, default=False)
    # Menu z alergenami widoczne na stronie gościa.
    show_menu: Mapped[bool] = mapped_column(Boolean, default=False)
    # Każde zaproszenie widzi na swojej stronie tylko swój stół (bez innych gości).
    show_tables: Mapped[bool] = mapped_column(Boolean, default=False)
    # Księga życzeń: goście zostawiają życzenia na swojej stronie.
    wishes_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # Lista prezentów: goście rezerwują pomysły pary na swojej stronie.
    gifts_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # Komunikat dla gości (np. zmiana godziny) — baner na stronie gościa.
    announcement: Mapped[str | None] = mapped_column(String(500))
    announcement_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    announcement_emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (CheckConstraint(f"theme IN {GUEST_THEMES}", name="theme"),)


class ReserveEntry(IdMixin, TimestampMixin, Base):
    """Lista rezerwowa: osoby, które para zaprosi, gdy zwolnią się miejsca.

    Osobna tabela, a nie gospodarstwo: rezerwowi nie liczą się do budżetu, stołów ani liczb
    dla sali. Po „Zaproś” powstaje zwykłe gospodarstwo, a wpis zostaje jako ślad z linkiem.
    """

    __tablename__ = "reserve_entries"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(150))
    side: Mapped[str] = mapped_column(String(8), default="both")
    persons: Mapped[int] = mapped_column(Integer, default=1)
    position: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(16), default="waiting")
    household_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("households.id", ondelete="SET NULL")
    )
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(f"side IN {SIDES}", name="side"),
        CheckConstraint(f"status IN {RESERVE_STATUSES}", name="status"),
        CheckConstraint("persons BETWEEN 1 AND 20", name="persons"),
        Index("ix_reserve_entries_wedding", "wedding_id", "position"),
    )


class GuestWish(IdMixin, Base):
    """Życzenia od gościa (księga gości). Para może je ukryć albo usunąć; zostają jako pamiątka."""

    __tablename__ = "guest_wishes"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    household_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("households.id", ondelete="SET NULL")
    )
    author: Mapped[str] = mapped_column(String(120))
    text: Mapped[str] = mapped_column(String(1000))
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (Index("ix_guest_wishes_wedding", "wedding_id", "created_at"),)


GIFT_KINDS = ("item", "fund")


class GiftIdea(IdMixin, TimestampMixin, Base):
    """Pomysł na prezent od pary. Rzecz rezerwuje jedno zaproszenie; „fundusz” (np. podróż
    poślubna) jest tylko informacją — bez kwot i bez rezerwacji."""

    __tablename__ = "gift_ideas"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(8), default="item")
    title: Mapped[str] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(String(300))
    link: Mapped[str | None] = mapped_column(String(500))
    reserved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("households.id", ondelete="SET NULL")
    )
    reserved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    position: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(f"kind IN {GIFT_KINDS}", name="kind"),
        CheckConstraint("kind = 'item' OR reserved_by IS NULL", name="fund_not_reserved"),
        Index("ix_gift_ideas_wedding", "wedding_id", "position"),
    )
