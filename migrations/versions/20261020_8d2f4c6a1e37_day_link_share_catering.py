"""day link share catering

Revision ID: 8d2f4c6a1e37
Revises: 5c1e7a90b2d4
Create Date: 2026-10-20 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8d2f4c6a1e37"
down_revision: str | None = "5c1e7a90b2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vendor_day_links",
        sa.Column("share_catering", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("vendor_day_links", "share_catering")
