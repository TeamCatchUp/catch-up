"""Add sync_event_missing_records table

Revision ID: 4f2b7c9d8e1a
Revises: 12b4b6a8c9d1
Create Date: 2026-03-26 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4f2b7c9d8e1a"
down_revision: Union[str, Sequence[str], None] = "12b4b6a8c9d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sync_event_missing_records",
        sa.Column(
            "event_id",
            sa.String(length=32),
            sa.ForeignKey("sync_events.event_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("record_type", sa.String(length=32), nullable=False),
        sa.Column("record_id", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "event_id",
            "record_type",
            "record_id",
            name="pk_sync_event_missing_records",
        ),
    )
    op.create_index(
        "idx_sync_event_missing_records_event_id",
        "sync_event_missing_records",
        ["event_id"],
        unique=False,
    )
    op.create_index(
        "idx_sync_event_missing_records_record_type",
        "sync_event_missing_records",
        ["record_type", "record_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_sync_event_missing_records_record_type",
        table_name="sync_event_missing_records",
    )
    op.drop_index(
        "idx_sync_event_missing_records_event_id",
        table_name="sync_event_missing_records",
    )
    op.drop_table("sync_event_missing_records")
