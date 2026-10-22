"""logistics: transport runs and lodging rooms

Revision ID: d1f3b5c7e9a0
Revises: c9e1a3b5d7f8
Create Date: 2026-10-22 06:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1f3b5c7e9a0"
down_revision: str | None = "c9e1a3b5d7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def _fk(table: str, column: str, target: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column],
        [f"{target}.id"],
        name=op.f(f"fk_{table}_{column}_{target}"),
        ondelete=ondelete,
    )


def upgrade() -> None:
    op.create_table(
        "transport_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("vendor_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("departs_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("from_place", sa.String(length=120), nullable=True),
        sa.Column("to_place", sa.String(length=120), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "kind IN ('there', 'back', 'other')", name=op.f("ck_transport_runs_kind")
        ),
        sa.CheckConstraint("capacity BETWEEN 1 AND 500", name=op.f("ck_transport_runs_capacity")),
        _fk("transport_runs", "wedding_id", "weddings", "CASCADE"),
        _fk("transport_runs", "vendor_id", "vendors", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transport_runs")),
    )
    op.create_index("ix_transport_runs_wedding", "transport_runs", ["wedding_id", "departs_at"])
    op.create_table(
        "transport_seats",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("guest_id", sa.Uuid(), nullable=False),
        _fk("transport_seats", "run_id", "transport_runs", "CASCADE"),
        _fk("transport_seats", "guest_id", "guests", "CASCADE"),
        sa.PrimaryKeyConstraint("run_id", "guest_id", name=op.f("pk_transport_seats")),
    )
    op.create_index(op.f("ix_transport_seats_guest_id"), "transport_seats", ["guest_id"])
    op.create_table(
        "lodging_rooms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("place", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("beds", sa.Integer(), nullable=False),
        sa.Column("check_in", sa.Date(), nullable=True),
        sa.Column("check_out", sa.Date(), nullable=True),
        sa.Column("paid_by", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("beds BETWEEN 1 AND 20", name=op.f("ck_lodging_rooms_beds")),
        sa.CheckConstraint(
            "check_in IS NULL OR check_out IS NULL OR check_out > check_in",
            name=op.f("ck_lodging_rooms_nights"),
        ),
        _fk("lodging_rooms", "wedding_id", "weddings", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lodging_rooms")),
    )
    op.create_index("ix_lodging_rooms_wedding", "lodging_rooms", ["wedding_id", "place"])
    op.create_table(
        "room_guests",
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("guest_id", sa.Uuid(), nullable=False),
        _fk("room_guests", "room_id", "lodging_rooms", "CASCADE"),
        _fk("room_guests", "guest_id", "guests", "CASCADE"),
        sa.PrimaryKeyConstraint("guest_id", name=op.f("pk_room_guests")),
    )
    op.create_index(op.f("ix_room_guests_room_id"), "room_guests", ["room_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_room_guests_room_id"), table_name="room_guests")
    op.drop_table("room_guests")
    op.drop_index("ix_lodging_rooms_wedding", table_name="lodging_rooms")
    op.drop_table("lodging_rooms")
    op.drop_index(op.f("ix_transport_seats_guest_id"), table_name="transport_seats")
    op.drop_table("transport_seats")
    op.drop_index("ix_transport_runs_wedding", table_name="transport_runs")
    op.drop_table("transport_runs")
