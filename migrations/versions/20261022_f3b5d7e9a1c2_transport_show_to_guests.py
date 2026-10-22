"""transport runs: show to guests in RSVP

Revision ID: f3b5d7e9a1c2
Revises: e2a4c6d8f0b1
Create Date: 2026-10-22 08:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3b5d7e9a1c2"
down_revision: str | None = "e2a4c6d8f0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transport_runs",
        sa.Column("show_to_guests", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("transport_runs", "show_to_guests")
