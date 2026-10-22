"""aftercare: deliverables and after-wedding checks

Revision ID: e2a4c6d8f0b1
Revises: d1f3b5c7e9a0
Create Date: 2026-10-22 07:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2a4c6d8f0b1"
down_revision: str | None = "d1f3b5c7e9a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "deliverables",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("vendor_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("received_on", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["wedding_id"],
            ["weddings.id"],
            name=op.f("fk_deliverables_wedding_id_weddings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["vendors.id"],
            name=op.f("fk_deliverables_vendor_id_vendors"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deliverables")),
    )
    op.create_index("ix_deliverables_wedding", "deliverables", ["wedding_id", "due_on"])
    op.create_table(
        "after_checks",
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("done_on", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ["wedding_id"],
            ["weddings.id"],
            name=op.f("fk_after_checks_wedding_id_weddings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("wedding_id", "code", name=op.f("pk_after_checks")),
    )


def downgrade() -> None:
    op.drop_table("after_checks")
    op.drop_index("ix_deliverables_wedding", table_name="deliverables")
    op.drop_table("deliverables")
