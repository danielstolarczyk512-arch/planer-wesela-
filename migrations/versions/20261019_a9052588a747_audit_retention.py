"""audit retention

Dziennik audytu nadal jest tylko do dopisywania. Jedyny wyjątek: procedura retencji
(`SET LOCAL wp.audit_retention = 'on'` w tej samej transakcji) może usunąć wpisy starsze
niż 24 miesiące. Aktualizacja wpisów pozostaje zablokowana zawsze.

Revision ID: a9052588a747
Revises: 5c3d744a6aa5
Create Date: 2026-10-19 19:09:58.935229
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a9052588a747"
down_revision: str | None = "5c3d744a6aa5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_log_immutable() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE'
               AND current_setting('wp.audit_retention', true) = 'on'
               AND OLD.occurred_at < now() - interval '24 months' THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'audit_log jest tylko do dopisywania';
        END
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_log_immutable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log jest tylko do dopisywania';
        END
        $$ LANGUAGE plpgsql;
        """
    )
