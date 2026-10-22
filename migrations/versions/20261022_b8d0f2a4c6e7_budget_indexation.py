"""budget indexation (strażnik waloryzacji cen)

Revision ID: b8d0f2a4c6e7
Revises: a7c9e1b3d5f6
Create Date: 2026-10-22 04:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8d0f2a4c6e7"
down_revision: str | None = "a7c9e1b3d5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "budget_items",
        sa.Column("indexation", sa.String(length=16), server_default="none", nullable=False),
    )
    op.add_column(
        "budget_items", sa.Column("indexation_cap_percent", sa.Numeric(5, 2), nullable=True)
    )
    op.add_column("budget_items", sa.Column("price_fixed_on", sa.Date(), nullable=True))
    op.add_column("budget_items", sa.Column("price_review_on", sa.Date(), nullable=True))
    op.create_check_constraint(
        op.f("ck_budget_items_indexation"),
        "budget_items",
        "indexation IN ('none', 'cpi', 'price_list', 'cap')",
    )
    op.create_check_constraint(
        op.f("ck_budget_items_indexation_cap"),
        "budget_items",
        "indexation_cap_percent IS NULL OR indexation_cap_percent BETWEEN 0 AND 100",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_budget_items_indexation_cap"), "budget_items", type_="check")
    op.drop_constraint(op.f("ck_budget_items_indexation"), "budget_items", type_="check")
    for column in ("price_review_on", "price_fixed_on", "indexation_cap_percent", "indexation"):
        op.drop_column("budget_items", column)
