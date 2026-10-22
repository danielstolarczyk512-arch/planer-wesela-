"""muzyka (utwory na momenty, propozycje gości) i zdjęcia grupowe dla fotografa

Revision ID: 5534deb69bf7
Revises: b5d7f9a1c3e4
Create Date: 2026-10-22 12:00:25.181177
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5534deb69bf7"
down_revision: str | None = "b5d7f9a1c3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "photo_groups",
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("extra", sa.String(length=200), nullable=True),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False),
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
        sa.CheckConstraint("minutes BETWEEN 1 AND 60", name=op.f("ck_photo_groups_minutes")),
        sa.ForeignKeyConstraint(
            ["wedding_id"],
            ["weddings.id"],
            name=op.f("fk_photo_groups_wedding_id_weddings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_photo_groups")),
    )
    op.create_index(
        "ix_photo_groups_wedding", "photo_groups", ["wedding_id", "position"], unique=False
    )
    op.create_table(
        "music_entries",
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("moment", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("artist", sa.String(length=120), nullable=True),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=True),
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
            "moment IN ('ceremony', 'entrance', 'first_dance', 'parents', 'cake', 'oczepiny', 'last_dance', 'must', 'avoid', 'other')",
            name=op.f("ck_music_entries_moment"),
        ),
        sa.CheckConstraint(
            "status IN ('approved', 'suggested', 'rejected')", name=op.f("ck_music_entries_status")
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["households.id"],
            name=op.f("fk_music_entries_household_id_households"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["wedding_id"],
            ["weddings.id"],
            name=op.f("fk_music_entries_wedding_id_weddings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_music_entries")),
    )
    op.create_index(
        "ix_music_entries_wedding",
        "music_entries",
        ["wedding_id", "moment", "position"],
        unique=False,
    )
    op.create_table(
        "photo_group_guests",
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("guest_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["photo_groups.id"],
            name=op.f("fk_photo_group_guests_group_id_photo_groups"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["guest_id"],
            ["guests.id"],
            name=op.f("fk_photo_group_guests_guest_id_guests"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("group_id", "guest_id", name=op.f("pk_photo_group_guests")),
    )
    op.create_index(
        op.f("ix_photo_group_guests_guest_id"), "photo_group_guests", ["guest_id"], unique=False
    )
    op.add_column(
        "guest_info",
        sa.Column("song_requests", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("guest_info", "song_requests")
    op.drop_index(op.f("ix_photo_group_guests_guest_id"), table_name="photo_group_guests")
    op.drop_table("photo_group_guests")
    op.drop_index("ix_music_entries_wedding", table_name="music_entries")
    op.drop_table("music_entries")
    op.drop_index("ix_photo_groups_wedding", table_name="photo_groups")
    op.drop_table("photo_groups")
