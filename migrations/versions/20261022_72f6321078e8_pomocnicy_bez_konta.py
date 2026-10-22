"""pomocnicy bez konta (zadania dla bliskich na linku)

Revision ID: 72f6321078e8
Revises: 6a908b84bb85
Create Date: 2026-10-22 12:55:41.649358
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "72f6321078e8"
down_revision: str | None = "6a908b84bb85"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "helpers",
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["wedding_id"],
            ["weddings.id"],
            name=op.f("fk_helpers_wedding_id_weddings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_helpers")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_helpers_token_hash")),
    )
    op.create_index("ix_helpers_wedding", "helpers", ["wedding_id"], unique=False)
    op.add_column("tasks", sa.Column("helper_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_tasks_helper_id"), "tasks", ["helper_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_tasks_helper_id_helpers"),
        "tasks",
        "helpers",
        ["helper_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_tasks_helper_id_helpers"), "tasks", type_="foreignkey")
    op.drop_index(op.f("ix_tasks_helper_id"), table_name="tasks")
    op.drop_column("tasks", "helper_id")
    op.drop_index("ix_helpers_wedding", table_name="helpers")
    op.drop_table("helpers")
