"""reserve entries

Revision ID: d4f6b8a0c2e1
Revises: c8e1a4d2f913
Create Date: 2026-10-21 23:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4f6b8a0c2e1"
down_revision: str | None = "c8e1a4d2f913"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reserve_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("persons", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=True),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "side IN ('bride', 'groom', 'both', 'other')", name=op.f("ck_reserve_entries_side")
        ),
        sa.CheckConstraint(
            "status IN ('waiting', 'invited')", name=op.f("ck_reserve_entries_status")
        ),
        sa.CheckConstraint("persons BETWEEN 1 AND 20", name=op.f("ck_reserve_entries_persons")),
        sa.ForeignKeyConstraint(
            ["wedding_id"],
            ["weddings.id"],
            name=op.f("fk_reserve_entries_wedding_id_weddings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name=op.f("fk_reserve_entries_household_id_households"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reserve_entries")),
    )
    op.create_index("ix_reserve_entries_wedding", "reserve_entries", ["wedding_id", "position"])


def downgrade() -> None:
    op.drop_index("ix_reserve_entries_wedding", table_name="reserve_entries")
    op.drop_table("reserve_entries")
