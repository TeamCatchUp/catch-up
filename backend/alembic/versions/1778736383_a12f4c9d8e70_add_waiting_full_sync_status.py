"""add waiting_full_sync status to incremental records

Revision ID: a12f4c9d8e70
Revises: 649538fd2274
Create Date: 2026-05-14 10:46:23.000000

"""
from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "a12f4c9d8e70"
down_revision: Union[str, Sequence[str], None] = "649538fd2274"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_STATUS_CONSTRAINT = (
    "status IN ('debouncing', 'waiting_full_sync', 'queued', 'processing', "
    "'retry_wait', 'dead', 'synced', 'recovered')"
)
OLD_STATUS_CONSTRAINT = (
    "status IN ('debouncing', 'queued', 'processing', 'retry_wait', "
    "'dead', 'synced', 'recovered')"
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_incremental_record_states_status",
        "incremental_record_states",
        type_="check",
    )
    op.create_check_constraint(
        "ck_incremental_record_states_status",
        "incremental_record_states",
        NEW_STATUS_CONSTRAINT,
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE incremental_record_states
            SET
                status = 'dead',
                attempt = 0,
                next_retry_at = NULL,
                queued_generation = NULL,
                processing_generation = NULL,
                last_error = 'downgraded_waiting_full_sync',
                lease_owner = NULL,
                lease_until = NULL,
                updated_at = NOW()
            WHERE status = 'waiting_full_sync'
            """
        )
    )
    op.drop_constraint(
        "ck_incremental_record_states_status",
        "incremental_record_states",
        type_="check",
    )
    op.create_check_constraint(
        "ck_incremental_record_states_status",
        "incremental_record_states",
        OLD_STATUS_CONSTRAINT,
    )
