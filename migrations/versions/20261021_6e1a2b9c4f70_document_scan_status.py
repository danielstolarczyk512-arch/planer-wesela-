"""document scan status

Revision ID: 6e1a2b9c4f70
Revises: 3b7e9f2c5d18
Create Date: 2026-10-21 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6e1a2b9c4f70"
down_revision: str | None = "3b7e9f2c5d18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Pliki wgrane przed wdrożeniem skanera: „not_scanned” (worker sprawdzi je, gdy skaner działa).
    op.add_column(
        "document_versions",
        sa.Column(
            "scan_status", sa.String(length=16), nullable=False, server_default="not_scanned"
        ),
    )
    op.add_column(
        "document_versions", sa.Column("scan_signature", sa.String(length=200), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_document_versions_scan_status"),
        "document_versions",
        "scan_status IN ('not_scanned', 'pending', 'clean', 'infected')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_document_versions_scan_status"), "document_versions", type_="check")
    op.drop_column("document_versions", "scan_signature")
    op.drop_column("document_versions", "scan_status")
