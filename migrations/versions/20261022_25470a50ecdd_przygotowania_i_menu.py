"""plan przygotowań (fryzjer, makijaż) i menu z alergenami

Revision ID: 25470a50ecdd
Revises: 5534deb69bf7
Create Date: 2026-10-22 12:27:51.591291
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "25470a50ecdd"
down_revision: str | None = "5534deb69bf7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "menu_dishes",
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("course", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("allergens", postgresql.ARRAY(sa.String(length=16)), nullable=False),
        sa.Column("vegetarian", sa.Boolean(), nullable=False),
        sa.Column("vegan", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "allergens <@ ARRAY['gluten', 'crustaceans', 'eggs', 'fish', 'peanuts', 'soy', 'milk', 'nuts', 'celery', 'mustard', 'sesame', 'sulphites', 'lupin', 'molluscs']::varchar[]",
            name=op.f("ck_menu_dishes_allergens"),
        ),
        sa.CheckConstraint(
            "course IN ('starter', 'soup', 'main', 'dessert', 'cake', 'hot', 'cold', 'other')",
            name=op.f("ck_menu_dishes_course"),
        ),
        sa.CheckConstraint(
            "NOT vegan OR vegetarian", name=op.f("ck_menu_dishes_vegan_is_vegetarian")
        ),
        sa.ForeignKeyConstraint(
            ["wedding_id"],
            ["weddings.id"],
            name=op.f("fk_menu_dishes_wedding_id_weddings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menu_dishes")),
    )
    op.create_index(
        "ix_menu_dishes_wedding", "menu_dishes", ["wedding_id", "course", "position"], unique=False
    )
    op.create_table(
        "prep_people",
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("hair_minutes", sa.Integer(), nullable=False),
        sa.Column("makeup_minutes", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "hair_minutes BETWEEN 0 AND 300", name=op.f("ck_prep_people_hair_minutes")
        ),
        sa.CheckConstraint(
            "makeup_minutes BETWEEN 0 AND 300", name=op.f("ck_prep_people_makeup_minutes")
        ),
        sa.ForeignKeyConstraint(
            ["wedding_id"],
            ["weddings.id"],
            name=op.f("fk_prep_people_wedding_id_weddings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prep_people")),
    )
    op.create_index(
        "ix_prep_people_wedding", "prep_people", ["wedding_id", "position"], unique=False
    )
    op.create_table(
        "prep_plans",
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("ready_by", sa.Time(), nullable=False),
        sa.Column("hair_artists", sa.Integer(), nullable=False),
        sa.Column("makeup_artists", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "hair_artists BETWEEN 0 AND 10", name=op.f("ck_prep_plans_hair_artists")
        ),
        sa.CheckConstraint(
            "makeup_artists BETWEEN 0 AND 10", name=op.f("ck_prep_plans_makeup_artists")
        ),
        sa.ForeignKeyConstraint(
            ["wedding_id"],
            ["weddings.id"],
            name=op.f("fk_prep_plans_wedding_id_weddings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("wedding_id", name=op.f("pk_prep_plans")),
    )
    op.add_column(
        "guest_info",
        sa.Column("show_menu", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("guest_info", "show_menu")
    op.drop_table("prep_plans")
    op.drop_index("ix_prep_people_wedding", table_name="prep_people")
    op.drop_table("prep_people")
    op.drop_index("ix_menu_dishes_wedding", table_name="menu_dishes")
    op.drop_table("menu_dishes")
