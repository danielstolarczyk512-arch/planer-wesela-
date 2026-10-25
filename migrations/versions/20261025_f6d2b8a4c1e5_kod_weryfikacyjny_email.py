"""kod weryfikacyjny e-mail (6 cyfr)

Revision ID: f6d2b8a4c1e5
Revises: e5c1a7f3b9d4
Create Date: 2026-10-25 19:20:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f6d2b8a4c1e5"
down_revision: str | None = "e5c1a7f3b9d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME = "purpose"


def upgrade() -> None:
    op.drop_constraint(NAME, "one_time_tokens", type_="check")
    op.create_check_constraint(
        NAME, "one_time_tokens", "purpose IN ('verify_email', 'reset_password', 'verify_code')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM one_time_tokens WHERE purpose = 'verify_code'")
    op.drop_constraint(NAME, "one_time_tokens", type_="check")
    op.create_check_constraint(
        NAME, "one_time_tokens", "purpose IN ('verify_email', 'reset_password')"
    )
