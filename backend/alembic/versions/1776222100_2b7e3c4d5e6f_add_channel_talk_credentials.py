"""add channel talk credentials

Revision ID: 2b7e3c4d5e6f
Revises: 1f4f5d6a7b8c
Create Date: 2026-04-15 16:08:20.000000

"""
from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = '2b7e3c4d5e6f'
down_revision: Union[str, Sequence[str], None] = '1f4f5d6a7b8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'channel_talk_credentials',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('channel_id', sa.String(length=128), nullable=False, comment='Validated Channel Talk channel ID'),
        sa.Column('channel_name', sa.String(length=255), nullable=False, comment='Validated Channel Talk channel name'),
        sa.Column('access_key', sa.String(length=512), nullable=False, comment='Channel Talk access key'),
        sa.Column('access_secret', sa.String(length=512), nullable=False, comment='Channel Talk access secret'),
        sa.Column('webhook_token', sa.String(length=1024), nullable=False, comment='CatchUp-managed webhook token'),
        sa.Column('credential_last_verified_at', sa.DateTime(timezone=True), nullable=False, comment='Last successful credential validation time'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('channel_talk_credentials')
