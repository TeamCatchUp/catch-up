"""add knowledge block verdicts

Revision ID: 01c86d4ae713
Revises: 952f249c36d2
Create Date: 2026-08-09 06:12:06.952353

"""
from typing import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '01c86d4ae713'
down_revision: Union[str, Sequence[str], None] = '952f249c36d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE = "knowledge_block_verdicts"
QUEUE_INDEX = "ix_knowledge_block_verdicts_workspace_proposal"


def upgrade() -> None:
    """블록 단위 판정을 남기는 저널 테이블을 만든다."""
    op.create_table(
        TABLE,
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.Integer, nullable=False),
        sa.Column(
            "proposal_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("block_index", sa.Integer, nullable=False),
        sa.Column("block_content_hash", sa.String(64), nullable=False),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        # claim 후보 테이블과의 순환·수명 결합을 피하려고 FK를 걸지 않는다.
        sa.Column(
            "chosen_winner_claim_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("reviewer", sa.String(255), nullable=False),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["knowledge_artifact_change_proposals.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "proposal_id",
            "block_index",
            name="uq_block_verdict_proposal_block",
        ),
        sa.CheckConstraint(
            "verdict IN ('approved','rejected')",
            name="ck_block_verdict_kind",
        ),
        sa.CheckConstraint(
            "verdict != 'rejected' OR (rejection_reason IS NOT NULL "
            "AND length(trim(rejection_reason)) > 0)",
            name="ck_block_verdict_rejection_reason",
        ),
        sa.CheckConstraint(
            "length(trim(reviewer)) > 0",
            name="ck_block_verdict_reviewer",
        ),
    )
    op.create_index(QUEUE_INDEX, TABLE, ["workspace_id", "proposal_id"])


def downgrade() -> None:
    """판정 저널 테이블을 통째로 되돌린다.

    사람이 남긴 결정 기록이 함께 사라지므로, 되돌리기 전에 보존이
    필요한지 사람이 판단해야 한다.
    """
    op.drop_index(QUEUE_INDEX, table_name=TABLE)
    op.drop_table(TABLE)
