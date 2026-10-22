"""guest page theme

Revision ID: 3b7e9f2c5d18
Revises: 8d2f4c6a1e37
Create Date: 2026-10-20 19:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3b7e9f2c5d18"
down_revision: str | None = "8d2f4c6a1e37"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "guest_info",
        sa.Column("theme", sa.String(length=16), nullable=False, server_default="classic"),
    )
    op.add_column("guest_info", sa.Column("accent", sa.String(length=16), nullable=True))
    op.create_check_constraint(
        op.f("ck_guest_info_theme"), "guest_info", "theme IN ('classic', 'garden', 'modern')"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_guest_info_theme"), "guest_info", type_="check")
    op.drop_column("guest_info", "accent")
    op.drop_column("guest_info", "theme")
