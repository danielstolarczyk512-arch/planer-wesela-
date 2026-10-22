"""seating room layout

Revision ID: 7f3c1d5a9b02
Revises: 6e1a2b9c4f70
Create Date: 2026-10-21 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7f3c1d5a9b02"
down_revision: str | None = "6e1a2b9c4f70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("seating_tables", sa.Column("pos_x", sa.Numeric(6, 2), nullable=True))
    op.add_column("seating_tables", sa.Column("pos_y", sa.Numeric(6, 2), nullable=True))
    op.add_column(
        "seating_tables",
        sa.Column("rotation", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        op.f("ck_seating_tables_rotation_range"), "seating_tables", "rotation BETWEEN 0 AND 359"
    )
    op.create_table(
        "seating_rooms",
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("width_m", sa.Numeric(6, 2), nullable=False),
        sa.Column("length_m", sa.Numeric(6, 2), nullable=False),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["wedding_id"],
            ["weddings.id"],
            name=op.f("fk_seating_rooms_wedding_id_weddings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("wedding_id", name=op.f("pk_seating_rooms")),
    )


def downgrade() -> None:
    op.drop_table("seating_rooms")
    op.drop_constraint(op.f("ck_seating_tables_rotation_range"), "seating_tables", type_="check")
    op.drop_column("seating_tables", "rotation")
    op.drop_column("seating_tables", "pos_y")
    op.drop_column("seating_tables", "pos_x")
