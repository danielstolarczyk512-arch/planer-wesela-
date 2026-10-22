"""Menu wesela z alergenami (14 alergenów z rozporządzenia UE 1169/2011, załącznik II)."""

from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin

ALLERGENS = (
    "gluten",
    "crustaceans",
    "eggs",
    "fish",
    "peanuts",
    "soy",
    "milk",
    "nuts",
    "celery",
    "mustard",
    "sesame",
    "sulphites",
    "lupin",
    "molluscs",
)
COURSES = ("starter", "soup", "main", "dessert", "cake", "hot", "cold", "other")


class MenuDish(IdMixin, TimestampMixin, Base):
    __tablename__ = "menu_dishes"

    wedding_id: Mapped[UUID] = mapped_column(ForeignKey("weddings.id", ondelete="CASCADE"))
    course: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(300))
    allergens: Mapped[list[str]] = mapped_column(ARRAY(String(16)), default=list)
    vegetarian: Mapped[bool] = mapped_column(Boolean, default=False)
    vegan: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        CheckConstraint(f"course IN {COURSES}", name="course"),
        CheckConstraint(f"allergens <@ ARRAY{list(ALLERGENS)}::varchar[]", name="allergens"),
        CheckConstraint("NOT vegan OR vegetarian", name="vegan_is_vegetarian"),
        Index("ix_menu_dishes_wedding", "wedding_id", "course", "position"),
    )
