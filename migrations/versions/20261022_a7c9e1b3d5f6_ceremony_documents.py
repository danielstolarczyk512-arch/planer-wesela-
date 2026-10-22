"""ceremony documents (licznik ważności dokumentów do ślubu)

Revision ID: a7c9e1b3d5f6
Revises: f6b8d0a2c4e5
Create Date: 2026-10-22 03:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c9e1b3d5f6"
down_revision: str | None = "f6b8d0a2c4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ceremony_documents",
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("issued_on", sa.Date(), nullable=True),
        sa.Column("done", sa.Boolean(), nullable=False),
        sa.Column("valid_months", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "valid_months IS NULL OR valid_months BETWEEN 1 AND 24",
            name=op.f("ck_ceremony_documents_valid_months"),
        ),
        sa.ForeignKeyConstraint(
            ["wedding_id"],
            ["weddings.id"],
            name=op.f("fk_ceremony_documents_wedding_id_weddings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("wedding_id", "code", name=op.f("pk_ceremony_documents")),
    )


def downgrade() -> None:
    op.drop_table("ceremony_documents")
