"""drop_channel_talk_document_spaces_add_polling

Revision ID: 9c2d1e4f6a8b
Revises: 8f7c6d5e4b3a
Create Date: 2026-05-02 00:00:00.000000

"""
from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c2d1e4f6a8b"
down_revision: Union[str, Sequence[str], None] = "8f7c6d5e4b3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("channel_talk_document_spaces")
    op.add_column(
        "channel_talk_document_credentials",
        sa.Column(
            "polling_cycle_hours",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
            comment="Document Space incremental polling cycle in hours",
        ),
    )
    op.add_column(
        "channel_talk_document_credentials",
        sa.Column(
            "last_incremental_polled_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last completed incremental poll time",
        ),
    )
    op.add_column(
        "channel_talk_document_credentials",
        sa.Column(
            "last_incremental_poll_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last started incremental poll time",
        ),
    )
    op.add_column(
        "channel_talk_document_credentials",
        sa.Column(
            "last_incremental_poll_error",
            sa.Text(),
            nullable=True,
            comment="Last incremental poll error summary",
        ),
    )


def downgrade() -> None:
    op.drop_column("channel_talk_document_credentials", "last_incremental_poll_error")
    op.drop_column(
        "channel_talk_document_credentials",
        "last_incremental_poll_started_at",
    )
    op.drop_column("channel_talk_document_credentials", "last_incremental_polled_at")
    op.drop_column("channel_talk_document_credentials", "polling_cycle_hours")
    op.create_table(
        "channel_talk_document_spaces",
        sa.Column("channel_id", sa.String(length=128), nullable=False),
        sa.Column("space_id", sa.String(length=128), nullable=False),
        sa.Column("space_name", sa.String(length=255), nullable=False),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("channel_id", "space_id"),
    )
