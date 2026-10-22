"""budget child unit price

Revision ID: 9a4e2c7d1b55
Revises: 7f3c1d5a9b02
Create Date: 2026-10-21 02:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9a4e2c7d1b55"
down_revision: str | None = "7f3c1d5a9b02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("budget_items", sa.Column("child_unit_price", sa.Numeric(12, 2), nullable=True))
    op.create_check_constraint(
        op.f("ck_budget_items_child_price_non_negative"),
        "budget_items",
        "child_unit_price IS NULL OR child_unit_price >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_budget_items_child_price_non_negative"), "budget_items", type_="check"
    )
    op.drop_column("budget_items", "child_unit_price")
