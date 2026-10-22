"""guest added via rsvp

Revision ID: 5c1e7a90b2d4
Revises: eb9c974a83fa
Create Date: 2026-10-20 16:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5c1e7a90b2d4"
down_revision: str | None = "eb9c974a83fa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "guests",
        sa.Column("added_via_rsvp", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("guests", "added_via_rsvp")
