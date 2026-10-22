"""vendor briefs

Revision ID: e5a7c9b1d3f4
Revises: d4f6b8a0c2e1
Create Date: 2026-10-22 01:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5a7c9b1d3f4"
down_revision: str | None = "d4f6b8a0c2e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vendor_briefs",
        sa.Column("vendor_id", sa.Uuid(), nullable=False),
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("must", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("avoid", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("people", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("contact", sa.String(length=200), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("content_version", sa.Integer(), nullable=False),
        sa.Column("ack_hash", sa.String(length=64), nullable=True),
        sa.Column("ack_version", sa.Integer(), nullable=True),
        sa.Column("ack_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["vendors.id"],
            name=op.f("fk_vendor_briefs_vendor_id_vendors"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["wedding_id"],
            ["weddings.id"],
            name=op.f("fk_vendor_briefs_wedding_id_weddings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("vendor_id", name=op.f("pk_vendor_briefs")),
    )
    op.create_index(op.f("ix_vendor_briefs_wedding_id"), "vendor_briefs", ["wedding_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_vendor_briefs_wedding_id"), table_name="vendor_briefs")
    op.drop_table("vendor_briefs")
