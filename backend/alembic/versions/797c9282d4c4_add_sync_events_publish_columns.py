"""add_sync_events_publish_columns

Revision ID: 797c9282d4c4
Revises: 163814727125
Create Date: 2026-03-13 08:10:08.942285

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '797c9282d4c4'
down_revision: Union[str, Sequence[str], None] = '163814727125'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "sync_events"
PUBLISH_STATUS_CHECK = "ck_sync_events_publish_status"
PUBLISH_ATTEMPT_CHECK = "ck_sync_events_publish_attempt_non_negative"
PUBLISH_STATUS_INDEX = "idx_sync_events_publish_status_requested_at"


def _column_names() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(TABLE_NAME)}


def _check_constraint_names() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {
        constraint["name"]
        for constraint in inspector.get_check_constraints(TABLE_NAME)
        if constraint["name"]
    }


def _index_names() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {index["name"] for index in inspector.get_indexes(TABLE_NAME)}


def upgrade() -> None:
    """Upgrade schema."""
    columns = _column_names()

    if "publish_status" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column(
                "publish_status",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'pending'"),
            ),
        )
    if "publish_attempt" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column(
                "publish_attempt",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )
    if "published_at" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "stream_message_id" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column("stream_message_id", sa.String(length=64), nullable=True),
        )
    if "publish_error" not in columns:
        op.add_column(
            TABLE_NAME,
            sa.Column("publish_error", sa.Text(), nullable=True),
        )

    check_constraints = _check_constraint_names()
    if PUBLISH_STATUS_CHECK not in check_constraints:
        op.create_check_constraint(
            PUBLISH_STATUS_CHECK,
            TABLE_NAME,
            "publish_status IN ('pending', 'publishing', 'published', 'failed')",
        )
    if PUBLISH_ATTEMPT_CHECK not in check_constraints:
        op.create_check_constraint(
            PUBLISH_ATTEMPT_CHECK,
            TABLE_NAME,
            "publish_attempt >= 0",
        )

    indexes = _index_names()
    if PUBLISH_STATUS_INDEX not in indexes:
        op.create_index(
            PUBLISH_STATUS_INDEX,
            TABLE_NAME,
            ["publish_status", "requested_at"],
            unique=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    raise NotImplementedError(
        "Downgrade is intentionally disabled for this revision because "
        "some environments may already contain these columns outside Alembic."
    )
