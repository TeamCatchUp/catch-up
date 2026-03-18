"""Add retry statuses to sync_events

Revision ID: 8c9d2f52d4ab
Revises: 740d7e16753a
Create Date: 2026-03-19 19:10:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "8c9d2f52d4ab"
down_revision: Union[str, Sequence[str], None] = "740d7e16753a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("ck_sync_events_status", "sync_events", type_="check")
    op.create_check_constraint(
        "ck_sync_events_status",
        "sync_events",
        (
            "status IN ("
            "'pending', 'in_progress', 'success', 'failed', 'retrying', "
            "'retry_succeeded', 'retry_failed'"
            ")"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_sync_events_status", "sync_events", type_="check")
    op.create_check_constraint(
        "ck_sync_events_status",
        "sync_events",
        "status IN ('pending', 'in_progress', 'success', 'failed', 'retrying')",
    )
