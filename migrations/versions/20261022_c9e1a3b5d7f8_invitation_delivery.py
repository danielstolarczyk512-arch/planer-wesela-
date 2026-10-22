"""invitation delivery (wręczanie zaproszeń osobiście)

Revision ID: c9e1a3b5d7f8
Revises: b8d0f2a4c6e7
Create Date: 2026-10-22 05:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9e1a3b5d7f8"
down_revision: str | None = "b8d0f2a4c6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("households", sa.Column("delivery_method", sa.String(length=16), nullable=True))
    op.add_column("households", sa.Column("delivery_by", sa.String(length=80), nullable=True))
    op.add_column("households", sa.Column("delivery_place", sa.String(length=120), nullable=True))
    op.add_column("households", sa.Column("delivery_planned_on", sa.Date(), nullable=True))
    op.add_column("households", sa.Column("delivered_on", sa.Date(), nullable=True))
    op.create_check_constraint(
        op.f("ck_households_delivery_method"),
        "households",
        "delivery_method IS NULL OR delivery_method IN ('in_person', 'post', 'online', 'other')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_households_delivery_method"), "households", type_="check")
    for column in (
        "delivered_on",
        "delivery_planned_on",
        "delivery_place",
        "delivery_by",
        "delivery_method",
    ):
        op.drop_column("households", column)
