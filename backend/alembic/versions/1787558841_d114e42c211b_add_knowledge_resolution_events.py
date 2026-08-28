"""add knowledge resolution events

Revision ID: d114e42c211b
Revises: 1e8c3d910d23
Create Date: 2026-08-24 12:07:21.000000

entity 병합과 되돌림이 확정될 때마다 한 건씩 남기는 저널 표를 만든다.
자동으로 붙인 병합이 왜, 무슨 근거로, 어떤 멤버 구성으로 이뤄졌는지는
판정 순간에만 존재해 사후에 다시 만들어 낼 수 없으므로, 그 구성과 근거를
member_snapshot과 basis에 그대로 담아 둔다.

이 표는 덧붙이기만 한다. 병합을 되돌릴 때도 원본 행을 고치지 않고
reverses_event_id로 원본을 가리키는 unmerge 행을 새로 쓴다.

node_id에는 외래 키를 걸지 않는다. 되돌림으로 노드가 물러나도 저널 행은
그 노드를 계속 가리켜야 하고, 저널은 그래프의 현재 상태에 딸린 자료가
아니라 그와 무관하게 남는 기록이기 때문이다.
"""
from typing import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd114e42c211b'
down_revision: Union[str, Sequence[str], None] = '1e8c3d910d23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'knowledge_resolution_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=32), nullable=False),
        sa.Column('decider', sa.String(length=16), nullable=False),
        sa.Column('decider_id', sa.Text(), nullable=True),
        sa.Column('node_id', sa.UUID(), nullable=False),
        sa.Column('member_hash', sa.String(length=64), nullable=False),
        sa.Column(
            'member_snapshot',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            'basis',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column('reverses_event_id', sa.UUID(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['workspace_id'], ['workspaces.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['reverses_event_id'],
            ['knowledge_resolution_events.id'],
            name='fk_knowledge_resolution_events_reverses',
        ),
        sa.CheckConstraint(
            "event_type IN ('merge_create_node', 'merge_into_node', 'unmerge')",
            name='ck_knowledge_resolution_events_type',
        ),
        sa.CheckConstraint(
            "decider IN ('system', 'human')",
            name='ck_knowledge_resolution_events_decider',
        ),
        sa.CheckConstraint(
            "event_type != 'unmerge' OR reverses_event_id IS NOT NULL",
            name='ck_knowledge_resolution_events_unmerge_reversal',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_knowledge_resolution_events_member_hash',
        'knowledge_resolution_events',
        ['workspace_id', 'member_hash'],
    )
    # 한 원본에 되돌림 행은 하나뿐이다. 되돌림 서비스가 미리 읽어 보는
    # 검사는 잠금이 없어 두 운영자가 동시에 되돌리면 둘 다 통과한다.
    op.create_index(
        'uq_knowledge_resolution_events_reversal',
        'knowledge_resolution_events',
        ['reverses_event_id'],
        unique=True,
        postgresql_where=sa.text('reverses_event_id IS NOT NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        'uq_knowledge_resolution_events_reversal',
        table_name='knowledge_resolution_events',
    )
    op.drop_index(
        'ix_knowledge_resolution_events_member_hash',
        table_name='knowledge_resolution_events',
    )
    op.drop_table('knowledge_resolution_events')
