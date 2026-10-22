"""day checklist (co zabrać na dzień ślubu)

Revision ID: b5d7f9a1c3e4
Revises: a4c6e8f0b2d3
Create Date: 2026-10-22 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b5d7f9a1c3e4"
down_revision: str | None = "a4c6e8f0b2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "day_checklist_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("who", sa.String(length=80), nullable=True),
        sa.Column("done", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["wedding_id"],
            ["weddings.id"],
            name=op.f("fk_day_checklist_items_wedding_id_weddings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_day_checklist_items")),
    )
    op.create_index("ix_day_checklist_wedding", "day_checklist_items", ["wedding_id", "position"])


def downgrade() -> None:
    op.drop_index("ix_day_checklist_wedding", table_name="day_checklist_items")
    op.drop_table("day_checklist_items")
