"""funder contributions: reported by sponsor, confirmed by couple

Revision ID: a4c6e8f0b2d3
Revises: f3b5d7e9a1c2
Create Date: 2026-10-22 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4c6e8f0b2d3"
down_revision: str | None = "f3b5d7e9a1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "funder_contributions",
        sa.Column("status", sa.String(length=12), server_default="confirmed", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_funder_contributions_status"),
        "funder_contributions",
        "status IN ('confirmed', 'reported')",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_funder_contributions_status"), "funder_contributions", type_="check"
    )
    op.drop_column("funder_contributions", "status")
