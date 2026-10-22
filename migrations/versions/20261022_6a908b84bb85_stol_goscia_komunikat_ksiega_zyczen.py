"""stół na stronie gościa, komunikat dla gości, księga życzeń

Revision ID: 6a908b84bb85
Revises: 25470a50ecdd
Create Date: 2026-10-22 12:42:57.366713
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6a908b84bb85"
down_revision: str | None = "25470a50ecdd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "guest_wishes",
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=True),
        sa.Column("author", sa.String(length=120), nullable=False),
        sa.Column("text", sa.String(length=1000), nullable=False),
        sa.Column("hidden", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name=op.f("fk_guest_wishes_household_id_households"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["wedding_id"],
            ["weddings.id"],
            name=op.f("fk_guest_wishes_wedding_id_weddings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_guest_wishes")),
    )
    op.create_index(
        "ix_guest_wishes_wedding", "guest_wishes", ["wedding_id", "created_at"], unique=False
    )
    op.add_column(
        "guest_info",
        sa.Column("show_tables", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "guest_info",
        sa.Column("wishes_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("guest_info", sa.Column("announcement", sa.String(length=500), nullable=True))
    op.add_column(
        "guest_info", sa.Column("announcement_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "guest_info",
        sa.Column("announcement_emailed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("guest_info", "announcement_emailed_at")
    op.drop_column("guest_info", "announcement_at")
    op.drop_column("guest_info", "announcement")
    op.drop_column("guest_info", "wishes_enabled")
    op.drop_column("guest_info", "show_tables")
    op.drop_index("ix_guest_wishes_wedding", table_name="guest_wishes")
    op.drop_table("guest_wishes")
