"""Add full sync retry fields

Revision ID: 8f3a2c1d4b5e
Revises: e4c8353eade9
Create Date: 2026-03-23 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f3a2c1d4b5e"
down_revision: Union[str, Sequence[str], None] = "e4c8353eade9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE sync_events
            ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMPTZ NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            ALTER TABLE sync_events
            ADD COLUMN IF NOT EXISTS last_error TEXT NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_sync_events_connector_status_next_retry_at
            ON sync_events (connector, status, next_retry_at)
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DROP INDEX IF EXISTS idx_sync_events_connector_status_next_retry_at
            """
        )
    )
    op.execute(
        sa.text(
            """
            ALTER TABLE sync_events
            DROP COLUMN IF EXISTS last_error
            """
        )
    )
    op.execute(
        sa.text(
            """
            ALTER TABLE sync_events
            DROP COLUMN IF EXISTS next_retry_at
            """
        )
    )
