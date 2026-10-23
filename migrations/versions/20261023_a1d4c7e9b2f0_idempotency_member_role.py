"""idempotencja: rola członka wesela przy pierwszym żądaniu (kontrola przy odtworzeniu)

Revision ID: a1d4c7e9b2f0
Revises: 62688b77b348
Create Date: 2026-10-23 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1d4c7e9b2f0"
down_revision: str | None = "62688b77b348"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Zapisane wcześniej odpowiedzi dla ścieżek wesela nie mają roli, więc nie zostaną odtworzone
    # (403 idempotency.context_changed); i tak wygasają po 24 h.
    op.add_column("idempotency_keys", sa.Column("member_role", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("idempotency_keys", "member_role")
