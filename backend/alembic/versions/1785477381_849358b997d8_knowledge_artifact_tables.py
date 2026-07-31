"""knowledge artifact tables

Revision ID: 849358b997d8
Revises: c5308d1a3f09
Create Date: 2026-07-31 14:56:21.887118

"""
from typing import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '849358b997d8'
down_revision: Union[str, Sequence[str], None] = 'c5308d1a3f09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'knowledge_artifacts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('subject_node_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
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
            ['workspace_id', 'subject_node_id'],
            ['knowledge_nodes.workspace_id', 'knowledge_nodes.id'],
            name='fk_knowledge_artifacts_subject_node',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'workspace_id',
            'id',
            name='uq_knowledge_artifacts_workspace_id_id',
        ),
        sa.UniqueConstraint(
            'workspace_id',
            'kind',
            'subject_node_id',
            name='uq_knowledge_artifacts_subject',
        ),
    )

    # revisions와 서로 참조하므로 base_revision_id는 뒤에서 붙인다.
    op.create_table(
        'knowledge_artifact_change_proposals',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('artifact_id', sa.UUID(), nullable=False),
        sa.Column(
            'blocks',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            'status',
            sa.String(length=16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('idempotency_key', sa.String(length=255), nullable=False),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewer', sa.String(length=255), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'abandoned')",
            name='ck_knowledge_artifact_change_proposals_status',
        ),
        sa.CheckConstraint(
            "status <> 'rejected' OR rejection_reason IS NOT NULL",
            name='ck_knowledge_artifact_change_proposals_rejection_reason',
        ),
        sa.ForeignKeyConstraint(
            ['workspace_id'], ['workspaces.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['workspace_id', 'artifact_id'],
            ['knowledge_artifacts.workspace_id', 'knowledge_artifacts.id'],
            name='fk_knowledge_artifact_change_proposals_artifact',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'workspace_id',
            'id',
            name='uq_knowledge_artifact_change_proposals_workspace_id_id',
        ),
        sa.UniqueConstraint(
            'workspace_id',
            'idempotency_key',
            name='uq_knowledge_artifact_change_proposals_idempotency_key',
        ),
    )
    op.create_index(
        'ix_knowledge_artifact_change_proposals_review_queue',
        'knowledge_artifact_change_proposals',
        ['workspace_id', 'status', 'created_at'],
        unique=False,
    )

    op.create_table(
        'knowledge_artifact_revisions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('artifact_id', sa.UUID(), nullable=False),
        sa.Column('revision_number', sa.Integer(), nullable=False),
        sa.Column(
            'blocks',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column('source_proposal_id', sa.UUID(), nullable=False),
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
            ['workspace_id', 'artifact_id'],
            ['knowledge_artifacts.workspace_id', 'knowledge_artifacts.id'],
            name='fk_knowledge_artifact_revisions_artifact',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['workspace_id', 'source_proposal_id'],
            [
                'knowledge_artifact_change_proposals.workspace_id',
                'knowledge_artifact_change_proposals.id',
            ],
            name='fk_knowledge_artifact_revisions_source_proposal',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'workspace_id',
            'id',
            name='uq_knowledge_artifact_revisions_workspace_id_id',
        ),
        sa.UniqueConstraint(
            'workspace_id',
            'artifact_id',
            'revision_number',
            name='uq_knowledge_artifact_revisions_number',
        ),
    )

    op.add_column(
        'knowledge_artifact_change_proposals',
        sa.Column('base_revision_id', sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        'fk_knowledge_artifact_change_proposals_base_revision',
        'knowledge_artifact_change_proposals',
        'knowledge_artifact_revisions',
        ['workspace_id', 'base_revision_id'],
        ['workspace_id', 'id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'fk_knowledge_artifact_change_proposals_base_revision',
        'knowledge_artifact_change_proposals',
        type_='foreignkey',
    )
    op.drop_column('knowledge_artifact_change_proposals', 'base_revision_id')
    op.drop_table('knowledge_artifact_revisions')
    op.drop_index(
        'ix_knowledge_artifact_change_proposals_review_queue',
        table_name='knowledge_artifact_change_proposals',
    )
    op.drop_table('knowledge_artifact_change_proposals')
    op.drop_table('knowledge_artifacts')
