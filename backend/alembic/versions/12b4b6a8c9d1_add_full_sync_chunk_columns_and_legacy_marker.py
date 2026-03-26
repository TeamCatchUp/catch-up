"""Add full sync chunk columns and legacy marker

Revision ID: 12b4b6a8c9d1
Revises: 95e7a47233a9
Create Date: 2026-03-25 15:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from catchup.configs.constants import LEGACY_FULL_SYNC_EVENT_SCHEMA_VERSION
from catchup.configs.constants import LEGACY_FULL_SYNC_IGNORED_REASON
from catchup.configs.constants import LEGACY_FULL_SYNC_LAST_ERROR


# revision identifiers, used by Alembic.
revision: str = "12b4b6a8c9d1"
down_revision: Union[str, Sequence[str], None] = "95e7a47233a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    legacy_schema_version = str(LEGACY_FULL_SYNC_EVENT_SCHEMA_VERSION)

    op.add_column("sync_events", sa.Column("stage", sa.String(length=64), nullable=True))
    op.add_column("sync_events", sa.Column("range_start", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sync_events", sa.Column("range_end", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sync_events", sa.Column("chunk_index", sa.Integer(), nullable=True))
    op.add_column("sync_events", sa.Column("chunk_total", sa.Integer(), nullable=True))
    op.add_column("sync_events", sa.Column("range_watermark", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE sync_events AS se
            SET
                resource_metadata = jsonb_set(
                    COALESCE(se.resource_metadata, '{}'::jsonb),
                    '{event_schema_version}',
                    to_jsonb(:legacy_schema_version::int),
                    true
                ),
                updated_at = NOW()
            FROM sync_jobs AS sj
            WHERE
                se.job_id = sj.job_id
                AND sj.sync_type = 'full'
            """
        ).bindparams(legacy_schema_version=legacy_schema_version)
    )

    op.execute(
        sa.text(
            """
            UPDATE sync_events AS se
            SET
                resource_metadata = jsonb_set(
                    COALESCE(se.resource_metadata, '{}'::jsonb),
                    '{ignored_reason}',
                    to_jsonb(:legacy_ignored_reason::text),
                    true
                ),
                status = 'failed',
                publish_status = 'failed',
                next_retry_at = NULL,
                last_error = :legacy_last_error,
                updated_at = NOW(),
                failed_at = COALESCE(se.failed_at, NOW())
            FROM sync_jobs AS sj
            WHERE
                se.job_id = sj.job_id
                AND sj.sync_type = 'full'
                AND se.status <> 'success'
            """
        ).bindparams(
            legacy_ignored_reason=LEGACY_FULL_SYNC_IGNORED_REASON,
            legacy_last_error=LEGACY_FULL_SYNC_LAST_ERROR,
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE sync_jobs AS sj
            SET
                status = 'failed',
                failed_at = COALESCE(sj.failed_at, NOW()),
                succeeded_at = NULL,
                updated_at = NOW()
            WHERE
                sj.sync_type = 'full'
                AND sj.status <> 'success'
            """
        )
    )


def downgrade() -> None:
    op.drop_column("sync_events", "range_watermark")
    op.drop_column("sync_events", "chunk_total")
    op.drop_column("sync_events", "chunk_index")
    op.drop_column("sync_events", "range_end")
    op.drop_column("sync_events", "range_start")
    op.drop_column("sync_events", "stage")
