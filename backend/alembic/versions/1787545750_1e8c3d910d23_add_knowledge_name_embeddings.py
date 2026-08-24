"""add knowledge name embeddings

Revision ID: 1e8c3d910d23
Revises: eee5acf7ee4f
Create Date: 2026-08-21 17:51:37.298016

해소가 라운드마다 같은 이름을 다시 임베딩하지 않도록 정규화 이름 단위로
벡터를 담아 두는 표를 만든다. 다시 만들 수 있는 사본이라 통째로 비워도
다음 라운드가 임베딩을 다시 불러 같은 값을 채운다.

벡터는 pgvector 컬럼이 아니라 JSONB 실수 배열로 담고 HNSW 색인도 두지
않는다. 여기서 하는 일은 이름으로 정확히 찾아오는 조회지 가까운 벡터를
훑는 ANN 검색이 아니어서, 조회 경로 하나를 UNIQUE 제약이 그대로 덮는다.
"""
from typing import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1e8c3d910d23'
down_revision: Union[str, Sequence[str], None] = '1a0035d4b292'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'knowledge_name_embeddings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('normalized_name', sa.Text(), nullable=False),
        sa.Column('model_id', sa.String(length=255), nullable=False),
        sa.Column(
            'vector',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['workspace_id'], ['workspaces.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'workspace_id',
            'model_id',
            'normalized_name',
            name='uq_knowledge_name_embeddings_name',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('knowledge_name_embeddings')
