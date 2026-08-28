"""add observations table

Revision ID: 3475ff48126a
Revises: add2c4093ca0
Create Date: 2026-07-28 19:37:10.303368

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3475ff48126a'
down_revision: Union[str, Sequence[str], None] = 'add2c4093ca0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # observations의 composite FK가 이 unique constraint를 참조하므로
    # 테이블보다 먼저 만든다.
    op.create_unique_constraint('uq_source_versions_workspace_id_id', 'source_versions', ['workspace_id', 'id'])
    op.create_table('observations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('workspace_id', sa.Integer(), nullable=False),
    sa.Column('source_version_id', sa.UUID(), nullable=False),
    sa.Column('observation_kind', sa.String(length=32), nullable=False),
    sa.Column('normalized_content', sa.Text(), nullable=True),
    sa.Column('normalized_content_hash', sa.String(length=64), nullable=True),
    sa.Column('normalizer_id', sa.String(length=64), nullable=False),
    sa.Column('normalizer_version', sa.String(length=64), nullable=False),
    sa.Column('source_attributes', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('metadata_entities', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(observation_kind = 'tombstone' AND normalized_content IS NULL AND normalized_content_hash IS NULL) OR (observation_kind = 'document' AND normalized_content IS NOT NULL AND normalized_content_hash IS NOT NULL)", name='ck_observations_content_by_kind'),
    sa.CheckConstraint("observation_kind IN ('document', 'tombstone')", name='ck_observations_observation_kind'),
    sa.CheckConstraint('normalized_content_hash IS NULL OR char_length(normalized_content_hash) = 64', name='ck_observations_content_hash_length'),
    sa.ForeignKeyConstraint(['workspace_id', 'source_version_id'], ['source_versions.workspace_id', 'source_versions.id'], name='fk_observations_source_version', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source_version_id', 'normalizer_id', 'normalizer_version', name='uq_observations_source_version_normalizer')
    )


def downgrade() -> None:
    """Downgrade schema."""
    # FK를 들고 있는 테이블을 먼저 지워야 참조된 unique constraint를 지울 수 있다.
    op.drop_table('observations')
    op.drop_constraint('uq_source_versions_workspace_id_id', 'source_versions', type_='unique')
