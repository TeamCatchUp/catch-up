"""add recovered status to incremental record states

Revision ID: 6d2c4b7e8f90
Revises: 1f4f5d6a7b8c
Create Date: 2026-04-16 17:40:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = '6d2c4b7e8f90'
down_revision: Union[str, Sequence[str], None] = '1f4f5d6a7b8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        'ck_incremental_record_states_status',
        'incremental_record_states',
        type_='check',
    )
    op.create_check_constraint(
        'ck_incremental_record_states_status',
        'incremental_record_states',
        "status IN ('debouncing', 'queued', 'processing', 'retry_wait', 'dead', 'synced', 'recovered')",
    )


def downgrade() -> None:
    op.drop_constraint(
        'ck_incremental_record_states_status',
        'incremental_record_states',
        type_='check',
    )
    op.create_check_constraint(
        'ck_incremental_record_states_status',
        'incremental_record_states',
        "status IN ('debouncing', 'queued', 'processing', 'retry_wait', 'dead', 'synced')",
    )
