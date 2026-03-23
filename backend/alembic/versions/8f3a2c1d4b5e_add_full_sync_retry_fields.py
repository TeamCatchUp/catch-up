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
    op.add_column("sync_events", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sync_events", sa.Column("last_error", sa.Text(), nullable=True))
    op.create_index(
        "idx_sync_events_connector_status_next_retry_at",
        "sync_events",
        ["connector", "status", "next_retry_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_sync_events_connector_status_next_retry_at", table_name="sync_events")
    op.drop_column("sync_events", "last_error")
    op.drop_column("sync_events", "next_retry_at")
