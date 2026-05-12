"""Add indexes for Redis stream message cleanup lookups

Revision ID: 7d3c2a1b9e4f
Revises: 3b8a1f2c9d0e
Create Date: 2026-05-13 03:00:00.000000

"""
from typing import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7d3c2a1b9e4f"
down_revision: Union[str, Sequence[str], None] = "3b8a1f2c9d0e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "idx_sync_events_stream_message_id",
        "sync_events",
        ["stream_message_id"],
        unique=False,
    )
    op.create_index(
        "idx_incremental_stream_outbox_stream_message_id",
        "incremental_stream_outbox",
        ["stream_message_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "idx_incremental_stream_outbox_stream_message_id",
        table_name="incremental_stream_outbox",
    )
    op.drop_index("idx_sync_events_stream_message_id", table_name="sync_events")
