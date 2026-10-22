from datetime import datetime, time
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow


class ScheduleItem(IdMixin, TimestampMixin, Base):
    """Punkt programu dnia ślubu (np. błogosławieństwo, ceremonia, pierwszy taniec)."""

    __tablename__ = "schedule_items"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    event_id: Mapped[UUID | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)
    location: Mapped[str | None] = mapped_column(String(200))
    responsible_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    responsible_name: Mapped[str | None] = mapped_column(String(120))
    vendor_id: Mapped[UUID | None] = mapped_column(ForeignKey("vendors.id", ondelete="SET NULL"))
    preparations: Mapped[str | None] = mapped_column(Text)
    # Wariant awaryjny (deszcz, opóźnienie): co robimy i kogo powiadomić.
    plan_b: Mapped[str | None] = mapped_column(Text)
    # Punkt widoczny dla gości na stronie z linku RSVP (np. ceremonia, obiad, tort).
    for_guests: Mapped[bool] = mapped_column(Boolean, default=False)
    buffer_before_minutes: Mapped[int] = mapped_column(Integer, default=0)
    buffer_after_minutes: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint("duration_minutes BETWEEN 0 AND 1440", name="duration_range"),
        CheckConstraint("buffer_before_minutes BETWEEN 0 AND 600", name="buffer_before_range"),
        CheckConstraint("buffer_after_minutes BETWEEN 0 AND 600", name="buffer_after_range"),
        Index("ix_schedule_items_wedding_starts", "wedding_id", "starts_at"),
    )


class ScheduleDependency(Base):
    """`item` może zacząć się dopiero po zakończeniu `depends_on` (plus bufory)."""

    __tablename__ = "schedule_dependencies"

    item_id: Mapped[UUID] = mapped_column(
        ForeignKey("schedule_items.id", ondelete="CASCADE"), primary_key=True
    )
    depends_on_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("schedule_items.id", ondelete="CASCADE"), primary_key=True, index=True
    )

    __table_args__ = (CheckConstraint("item_id <> depends_on_item_id", name="not_self"),)


class VendorDayLink(IdMixin, Base):
    """Link tylko do odczytu z programem dnia dla usługodawcy (bez logowania).

    W bazie tylko hash tokenu. Usługodawca widzi godziny całego programu, a szczegóły
    (przygotowania, plan B, notatki) wyłącznie przy swoich punktach. Bez danych gości i kwot.
    """

    __tablename__ = "vendor_day_links"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    vendor_id: Mapped[UUID] = mapped_column(
        ForeignKey("vendors.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # Sala/catering: imiona, diety i uwagi przy stołach tylko za świadomą zgodą pary
    # (dane o zdrowiu trafiają do firmy zewnętrznej). Bez zgody — same liczby.
    share_catering: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VendorBrief(Base):
    """Informacje dla usługodawcy i wersje tego, co widzi na swoim linku.

    Wersja rośnie, gdy zmieni się treść linku (program, wydarzenia, te informacje). Liczby dla
    kuchni nie zmieniają wersji: aktualizują się po każdej odpowiedzi gości. Usługodawca
    potwierdza przeczytanie konkretnej wersji („Potwierdzam wersję 4”).
    """

    __tablename__ = "vendor_briefs"

    vendor_id: Mapped[UUID] = mapped_column(
        ForeignKey("vendors.id", ondelete="CASCADE"), primary_key=True
    )
    wedding_id: Mapped[UUID] = mapped_column(
        ForeignKey("weddings.id", ondelete="CASCADE"), index=True
    )
    must: Mapped[list[str]] = mapped_column(JSONB, default=list)
    avoid: Mapped[list[str]] = mapped_column(JSONB, default=list)
    people: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    contact: Mapped[str | None] = mapped_column(String(200))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    content_version: Mapped[int] = mapped_column(Integer, default=0)
    ack_hash: Mapped[str | None] = mapped_column(String(64))
    ack_version: Mapped[int | None] = mapped_column(Integer)
    ack_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    # Wersja do If-Match zmienia się tylko przy zapisie informacji przez parę (ręcznie w
    # save_brief), a nie przy odczytach linku, które podbijają content_version.
    version: Mapped[int] = mapped_column(Integer, default=1)


class DayChecklistItem(IdMixin, TimestampMixin, Base):
    """„Co zabrać” na dzień ślubu: rzecz, kto bierze, odhaczone."""

    __tablename__ = "day_checklist_items"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    who: Mapped[str | None] = mapped_column(String(80))
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (Index("ix_day_checklist_wedding", "wedding_id", "position"),)


MUSIC_MOMENTS = (
    "ceremony",
    "entrance",
    "first_dance",
    "parents",
    "cake",
    "oczepiny",
    "last_dance",
    "must",
    "avoid",
    "other",
)
MUSIC_STATUSES = ("approved", "suggested", "rejected")


class MusicEntry(IdMixin, TimestampMixin, Base):
    """Utwór na moment wesela, „koniecznie”, „nie grać” albo propozycja gościa z RSVP.

    Zatwierdzone utwory trafiają do linku DJ-a lub zespołu (wersja programu rośnie).
    """

    __tablename__ = "music_entries"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    moment: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(200))
    artist: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(16), default="approved")
    # Propozycja gościa: z którego zaproszenia (po usunięciu zaproszenia zostaje sam utwór).
    household_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("households.id", ondelete="SET NULL")
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(f"moment IN {MUSIC_MOMENTS}", name="moment"),
        CheckConstraint(f"status IN {MUSIC_STATUSES}", name="status"),
        Index("ix_music_entries_wedding", "wedding_id", "moment", "position"),
    )


class PhotoGroup(IdMixin, TimestampMixin, Base):
    """Zdjęcie grupowe dla fotografa: kto ma stanąć do zdjęcia, ile minut, odhaczone."""

    __tablename__ = "photo_groups"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    # Osoby spoza listy gości (np. „ksiądz”, „świadkowie z osobami towarzyszącymi”).
    extra: Mapped[str | None] = mapped_column(String(200))
    minutes: Mapped[int] = mapped_column(Integer, default=3)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint("minutes BETWEEN 1 AND 60", name="minutes"),
        Index("ix_photo_groups_wedding", "wedding_id", "position"),
    )


class PhotoGroupGuest(Base):
    __tablename__ = "photo_group_guests"

    group_id: Mapped[UUID] = mapped_column(
        ForeignKey("photo_groups.id", ondelete="CASCADE"), primary_key=True
    )
    guest_id: Mapped[UUID] = mapped_column(
        ForeignKey("guests.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class PrepPlan(Base):
    """Plan przygotowań (fryzjer, makijaż): na którą wszyscy gotowi i ile osób obsługuje."""

    __tablename__ = "prep_plans"

    wedding_id: Mapped[UUID] = mapped_column(
        ForeignKey("weddings.id", ondelete="CASCADE"), primary_key=True
    )
    ready_by: Mapped[time] = mapped_column(Time, default=time(13, 0))
    hair_artists: Mapped[int] = mapped_column(Integer, default=1)
    makeup_artists: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint("hair_artists BETWEEN 0 AND 10", name="hair_artists"),
        CheckConstraint("makeup_artists BETWEEN 0 AND 10", name="makeup_artists"),
    )


class PrepPerson(IdMixin, TimestampMixin, Base):
    """Osoba na fotelu: kto, ile minut fryzury i makijażu. Kolejność = kolejność siadania."""

    __tablename__ = "prep_people"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    hair_minutes: Mapped[int] = mapped_column(Integer, default=0)
    makeup_minutes: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint("hair_minutes BETWEEN 0 AND 300", name="hair_minutes"),
        CheckConstraint("makeup_minutes BETWEEN 0 AND 300", name="makeup_minutes"),
        Index("ix_prep_people_wedding", "wedding_id", "position"),
    )
