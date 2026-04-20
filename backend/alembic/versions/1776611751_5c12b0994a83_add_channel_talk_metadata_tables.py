"""add channel talk metadata tables

Revision ID: 5c12b0994a83
Revises: 6d2c4b7e8f90
Create Date: 2026-04-20 00:15:51.720115

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '5c12b0994a83'
down_revision: Union[str, Sequence[str], None] = '6d2c4b7e8f90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('channel_talk_channels',
    sa.Column('channel_id', sa.String(length=128), nullable=False, comment='Channel Talk channel ID'),
    sa.Column('channel_name', sa.String(length=255), nullable=False, comment='Channel Talk channel name'),
    sa.Column('description', sa.String(length=2000), nullable=True, comment='Channel description'),
    sa.Column('bot_name', sa.String(length=255), nullable=True, comment='Default bot display name'),
    sa.Column('homepage_url', sa.String(length=500), nullable=True, comment='Channel homepage URL'),
    sa.Column('domain', sa.String(length=255), nullable=True, comment='Channel custom domain'),
    sa.Column('subdomain', sa.String(length=255), nullable=True, comment='Channel subdomain'),
    sa.Column('avatar_url', sa.String(length=500), nullable=True, comment='Channel avatar URL'),
    sa.Column('country', sa.String(length=64), nullable=True, comment='Channel country code or country label'),
    sa.Column('time_zone', sa.String(length=100), nullable=True, comment='Channel time zone'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Metadata row creation time'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Metadata row last update time'),
    sa.PrimaryKeyConstraint('channel_id')
    )
    op.create_table('channel_talk_groups',
    sa.Column('channel_id', sa.String(length=128), nullable=False, comment='Owning Channel Talk channel ID'),
    sa.Column('group_id', sa.String(length=128), nullable=False, comment='Channel Talk group ID'),
    sa.Column('group_name', sa.String(length=255), nullable=False, comment='Group name'),
    sa.Column('scope', sa.String(length=50), nullable=True, comment='Group scope returned by Channel Talk'),
    sa.Column('description', sa.String(length=2000), nullable=True, comment='Group description'),
    sa.Column('icon_url', sa.String(length=500), nullable=True, comment='Group icon URL'),
    sa.Column('active', sa.Boolean(), nullable=True, comment='Whether the group is active'),
    sa.Column('remote_created_at', sa.DateTime(timezone=True), nullable=True, comment='Group created timestamp from Channel Talk'),
    sa.Column('remote_updated_at', sa.DateTime(timezone=True), nullable=True, comment='Group updated timestamp from Channel Talk'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Metadata row creation time'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Metadata row last update time'),
    sa.PrimaryKeyConstraint('channel_id', 'group_id')
    )
    op.create_table('channel_talk_managers',
    sa.Column('channel_id', sa.String(length=128), nullable=False, comment='Owning Channel Talk channel ID'),
    sa.Column('manager_id', sa.String(length=128), nullable=False, comment='Channel Talk manager ID'),
    sa.Column('account_id', sa.String(length=128), nullable=True, comment='Account ID linked to the manager'),
    sa.Column('name', sa.String(length=255), nullable=True, comment='Manager display name'),
    sa.Column('description', sa.String(length=2000), nullable=True, comment='Manager description'),
    sa.Column('email', sa.String(length=255), nullable=True, comment='Manager email address'),
    sa.Column('mobile_number', sa.String(length=64), nullable=True, comment='Manager mobile number'),
    sa.Column('role', sa.String(length=50), nullable=True, comment='Manager role such as owner or member'),
    sa.Column('removed', sa.Boolean(), nullable=True, comment='Whether the manager has been removed'),
    sa.Column('display_as_channel', sa.Boolean(), nullable=True, comment='Whether the manager is displayed as the channel'),
    sa.Column('avatar_url', sa.String(length=500), nullable=True, comment='Manager avatar URL'),
    sa.Column('remote_created_at', sa.DateTime(timezone=True), nullable=True, comment='Manager created timestamp from Channel Talk'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Metadata row creation time'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Metadata row last update time'),
    sa.PrimaryKeyConstraint('channel_id', 'manager_id')
    )
    op.create_index(op.f('ix_channel_talk_managers_email'), 'channel_talk_managers', ['email'], unique=False)
    op.create_table('channel_talk_group_managers',
    sa.Column('channel_id', sa.String(length=128), nullable=False, comment='Owning Channel Talk channel ID'),
    sa.Column('group_id', sa.String(length=128), nullable=False, comment='Channel Talk group ID'),
    sa.Column('manager_id', sa.String(length=128), nullable=False, comment='Channel Talk manager ID'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Relation row creation time'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Relation row last update time'),
    sa.PrimaryKeyConstraint('channel_id', 'group_id', 'manager_id')
    )
    op.create_table('channel_talk_users',
    sa.Column('channel_id', sa.String(length=128), nullable=False, comment='Owning Channel Talk channel ID'),
    sa.Column('external_user_id', sa.String(length=128), nullable=False, comment='Channel Talk userId'),
    sa.Column('veil_id', sa.String(length=128), nullable=True, comment='Veil ID returned by Channel Talk'),
    sa.Column('unified_id', sa.String(length=128), nullable=True, comment='Unified ID returned by Channel Talk'),
    sa.Column('member_id', sa.String(length=255), nullable=True, comment='External memberId tied to the customer'),
    sa.Column('user_type', sa.String(length=50), nullable=True, comment='Channel Talk user type such as member'),
    sa.Column('name', sa.String(length=255), nullable=True, comment='Customer display name'),
    sa.Column('email', sa.String(length=255), nullable=True, comment='Customer email address'),
    sa.Column('mobile_number', sa.String(length=64), nullable=True, comment='Customer mobile number'),
    sa.Column('avatar_url', sa.String(length=500), nullable=True, comment='Customer avatar URL'),
    sa.Column('blocked', sa.Boolean(), nullable=True, comment='Whether the user is blocked'),
    sa.Column('language', sa.String(length=50), nullable=True, comment='Preferred language'),
    sa.Column('country', sa.String(length=64), nullable=True, comment='Country'),
    sa.Column('city', sa.String(length=128), nullable=True, comment='City'),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True, comment='Last seen timestamp from Channel Talk'),
    sa.Column('remote_created_at', sa.DateTime(timezone=True), nullable=True, comment='User created timestamp from Channel Talk'),
    sa.Column('remote_updated_at', sa.DateTime(timezone=True), nullable=True, comment='User updated timestamp from Channel Talk'),
    sa.Column('profile', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Raw or normalized customer profile payload'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Metadata row creation time'),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Metadata row last update time'),
    sa.PrimaryKeyConstraint('channel_id', 'external_user_id')
    )
    op.create_index(op.f('ix_channel_talk_users_email'), 'channel_talk_users', ['email'], unique=False)
    op.create_index(op.f('ix_channel_talk_users_member_id'), 'channel_talk_users', ['member_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_channel_talk_users_member_id'), table_name='channel_talk_users')
    op.drop_index(op.f('ix_channel_talk_users_email'), table_name='channel_talk_users')
    op.drop_table('channel_talk_users')
    op.drop_table('channel_talk_group_managers')
    op.drop_index(op.f('ix_channel_talk_managers_email'), table_name='channel_talk_managers')
    op.drop_table('channel_talk_managers')
    op.drop_table('channel_talk_groups')
    op.drop_table('channel_talk_channels')
