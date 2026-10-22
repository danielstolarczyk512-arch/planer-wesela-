"""lista prezentów (rezerwacje gości) i komentarze przy zadaniach

Revision ID: 62688b77b348
Revises: 72f6321078e8
Create Date: 2026-10-22 14:58:48.608958
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "62688b77b348"
down_revision: str | None = "72f6321078e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gift_ideas",
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("link", sa.String(length=500), nullable=True),
        sa.Column("reserved_by", sa.Uuid(), nullable=True),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind = 'item' OR reserved_by IS NULL", name=op.f("ck_gift_ideas_fund_not_reserved")
        ),
        sa.CheckConstraint("kind IN ('item', 'fund')", name=op.f("ck_gift_ideas_kind")),
        sa.ForeignKeyConstraint(
            ["reserved_by"],
            ["households.id"],
            name=op.f("fk_gift_ideas_reserved_by_households"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["wedding_id"],
            ["weddings.id"],
            name=op.f("fk_gift_ideas_wedding_id_weddings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gift_ideas")),
    )
    op.create_index("ix_gift_ideas_wedding", "gift_ideas", ["wedding_id", "position"], unique=False)
    op.create_table(
        "task_comments",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=True),
        sa.Column("text", sa.String(length=1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["author_user_id"],
            ["users.id"],
            name=op.f("fk_task_comments_author_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_task_comments_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["wedding_id"],
            ["weddings.id"],
            name=op.f("fk_task_comments_wedding_id_weddings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_comments")),
    )
    op.create_index(op.f("ix_task_comments_task_id"), "task_comments", ["task_id"], unique=False)
    op.add_column(
        "guest_info",
        sa.Column("gifts_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("guest_info", "gifts_enabled")
    op.drop_index(op.f("ix_task_comments_task_id"), table_name="task_comments")
    op.drop_table("task_comments")
    op.drop_index("ix_gift_ideas_wedding", table_name="gift_ideas")
    op.drop_table("gift_ideas")
