"""budget_assumptions: założenia inflacji strażnika waloryzacji zapisane na weselu

Revision ID: b7e2f4a9c1d3
Revises: a1d4c7e9b2f0
Create Date: 2026-10-23 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e2f4a9c1d3"
down_revision: str | None = "a1d4c7e9b2f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "budget_assumptions",
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("expected_rate", sa.Numeric(4, 3), nullable=False),
        sa.Column("worst_rate", sa.Numeric(4, 3), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "expected_rate >= 0 AND expected_rate <= 0.5",
            name=op.f("ck_budget_assumptions_expected_rate"),
        ),
        sa.CheckConstraint(
            "worst_rate >= 0 AND worst_rate <= 0.5", name=op.f("ck_budget_assumptions_worst_rate")
        ),
        sa.ForeignKeyConstraint(
            ["wedding_id"],
            ["weddings.id"],
            name=op.f("fk_budget_assumptions_wedding_id_weddings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("wedding_id", name=op.f("pk_budget_assumptions")),
    )


def downgrade() -> None:
    op.drop_table("budget_assumptions")
