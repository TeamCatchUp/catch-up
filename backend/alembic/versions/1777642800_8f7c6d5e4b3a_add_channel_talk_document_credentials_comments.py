"""add_channel_talk_document_credentials_comments

Revision ID: 8f7c6d5e4b3a
Revises: 4d2f9a8b7c6e
Create Date: 2026-05-02 00:00:00.000000

"""
from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f7c6d5e4b3a"
down_revision: Union[str, Sequence[str], None] = "4d2f9a8b7c6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "channel_talk_document_credentials",
        "channel_id",
        existing_type=sa.String(length=128),
        existing_nullable=False,
        comment="Locally associated Channel Talk channel ID",
        existing_comment=None,
    )
    op.alter_column(
        "channel_talk_document_credentials",
        "space_id",
        existing_type=sa.String(length=128),
        existing_nullable=False,
        comment="Validated Channel Talk Documents space ID",
        existing_comment=None,
    )
    op.alter_column(
        "channel_talk_document_credentials",
        "space_name",
        existing_type=sa.String(length=255),
        existing_nullable=False,
        comment="Validated Channel Talk Documents space name",
        existing_comment=None,
    )
    op.alter_column(
        "channel_talk_document_credentials",
        "access_key",
        existing_type=sa.String(length=512),
        existing_nullable=False,
        comment="Channel Talk Documents access key",
        existing_comment=None,
    )
    op.alter_column(
        "channel_talk_document_credentials",
        "access_secret",
        existing_type=sa.String(length=512),
        existing_nullable=False,
        comment="Channel Talk Documents access secret",
        existing_comment=None,
    )
    op.alter_column(
        "channel_talk_document_credentials",
        "credential_last_verified_at",
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
        comment="Last successful Documents credential validation time",
        existing_comment=None,
    )
    op.alter_column(
        "channel_talk_document_credentials",
        "association_status",
        existing_type=sa.String(length=32),
        existing_nullable=False,
        comment="api_verified/local_trusted/unverified/failed",
        existing_comment=None,
    )


def downgrade() -> None:
    op.alter_column(
        "channel_talk_document_credentials",
        "association_status",
        existing_type=sa.String(length=32),
        existing_nullable=False,
        comment=None,
        existing_comment="api_verified/local_trusted/unverified/failed",
    )
    op.alter_column(
        "channel_talk_document_credentials",
        "credential_last_verified_at",
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
        comment=None,
        existing_comment="Last successful Documents credential validation time",
    )
    op.alter_column(
        "channel_talk_document_credentials",
        "access_secret",
        existing_type=sa.String(length=512),
        existing_nullable=False,
        comment=None,
        existing_comment="Channel Talk Documents access secret",
    )
    op.alter_column(
        "channel_talk_document_credentials",
        "access_key",
        existing_type=sa.String(length=512),
        existing_nullable=False,
        comment=None,
        existing_comment="Channel Talk Documents access key",
    )
    op.alter_column(
        "channel_talk_document_credentials",
        "space_name",
        existing_type=sa.String(length=255),
        existing_nullable=False,
        comment=None,
        existing_comment="Validated Channel Talk Documents space name",
    )
    op.alter_column(
        "channel_talk_document_credentials",
        "space_id",
        existing_type=sa.String(length=128),
        existing_nullable=False,
        comment=None,
        existing_comment="Validated Channel Talk Documents space ID",
    )
    op.alter_column(
        "channel_talk_document_credentials",
        "channel_id",
        existing_type=sa.String(length=128),
        existing_nullable=False,
        comment=None,
        existing_comment="Locally associated Channel Talk channel ID",
    )
