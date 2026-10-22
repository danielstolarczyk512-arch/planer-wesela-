"""funders (portfel sponsorów) i rola sponsor

Revision ID: f6b8d0a2c4e5
Revises: e5a7c9b1d3f4
Create Date: 2026-10-22 02:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6b8d0a2c4e5"
down_revision: str | None = "e5a7c9b1d3f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_MEMBER = "role IN ('owner', 'coorganizer', 'viewer', 'coordinator')"
NEW_MEMBER = "role IN ('owner', 'coorganizer', 'viewer', 'coordinator', 'sponsor')"
OLD_INVITE = "role IN ('coorganizer', 'viewer', 'coordinator')"
NEW_INVITE = "role IN ('coorganizer', 'viewer', 'coordinator', 'sponsor')"


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "funders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("pledged_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "side IN ('bride', 'groom', 'both', 'other')", name=op.f("ck_funders_side")
        ),
        sa.CheckConstraint(
            "pledged_amount IS NULL OR pledged_amount >= 0", name=op.f("ck_funders_pledged")
        ),
        sa.ForeignKeyConstraint(
            ["wedding_id"],
            ["weddings.id"],
            name=op.f("fk_funders_wedding_id_weddings"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_funders")),
    )
    op.create_index("ix_funders_wedding", "funders", ["wedding_id", "position"])
    op.create_table(
        "funder_contributions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("wedding_id", sa.Uuid(), nullable=False),
        sa.Column("funder_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("received_on", sa.Date(), nullable=True),
        sa.Column("note", sa.String(length=300), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("amount > 0", name=op.f("ck_funder_contributions_amount_positive")),
        sa.ForeignKeyConstraint(
            ["wedding_id"],
            ["weddings.id"],
            name=op.f("fk_funder_contributions_wedding_id_weddings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["funder_id"],
            ["funders.id"],
            name=op.f("fk_funder_contributions_funder_id_funders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_funder_contributions")),
    )
    op.create_index(
        op.f("ix_funder_contributions_funder_id"), "funder_contributions", ["funder_id"]
    )
    for table in ("payments", "wedding_members", "wedding_invitations"):
        op.add_column(table, sa.Column("funder_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(
            op.f(f"fk_{table}_funder_id_funders"),
            table,
            "funders",
            ["funder_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(op.f("ix_payments_funder_id"), "payments", ["funder_id"])
    op.drop_constraint(op.f("ck_wedding_members_role"), "wedding_members", type_="check")
    op.create_check_constraint(op.f("ck_wedding_members_role"), "wedding_members", NEW_MEMBER)
    op.drop_constraint(op.f("ck_wedding_invitations_role"), "wedding_invitations", type_="check")
    op.create_check_constraint(
        op.f("ck_wedding_invitations_role"), "wedding_invitations", NEW_INVITE
    )


def downgrade() -> None:
    op.execute("DELETE FROM wedding_members WHERE role = 'sponsor'")
    op.execute("DELETE FROM wedding_invitations WHERE role = 'sponsor'")
    op.drop_constraint(op.f("ck_wedding_invitations_role"), "wedding_invitations", type_="check")
    op.create_check_constraint(
        op.f("ck_wedding_invitations_role"), "wedding_invitations", OLD_INVITE
    )
    op.drop_constraint(op.f("ck_wedding_members_role"), "wedding_members", type_="check")
    op.create_check_constraint(op.f("ck_wedding_members_role"), "wedding_members", OLD_MEMBER)
    op.drop_index(op.f("ix_payments_funder_id"), table_name="payments")
    for table in ("wedding_invitations", "wedding_members", "payments"):
        op.drop_constraint(op.f(f"fk_{table}_funder_id_funders"), table, type_="foreignkey")
        op.drop_column(table, "funder_id")
    op.drop_index(op.f("ix_funder_contributions_funder_id"), table_name="funder_contributions")
    op.drop_table("funder_contributions")
    op.drop_index("ix_funders_wedding", table_name="funders")
    op.drop_table("funders")
