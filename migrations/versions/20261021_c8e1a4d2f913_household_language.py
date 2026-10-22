"""household language

Revision ID: c8e1a4d2f913
Revises: b3d5f7a91c26
Create Date: 2026-10-21 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8e1a4d2f913"
down_revision: str | None = "b3d5f7a91c26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NULL = automatycznie (strona wg przeglądarki gościa, e-mail po polsku).
    op.add_column("households", sa.Column("language", sa.String(length=2), nullable=True))
    op.create_check_constraint(
        op.f("ck_households_language"),
        "households",
        "language IS NULL OR language IN ('pl', 'en')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_households_language"), "households", type_="check")
    op.drop_column("households", "language")
