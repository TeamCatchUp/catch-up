"""mutation proposal decision columns

Revision ID: d48fc18e42f7
Revises: 849358b997d8
Create Date: 2026-07-31 17:35:41.101928

"""
from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd48fc18e42f7'
down_revision: Union[str, Sequence[str], None] = '849358b997d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE = "knowledge_mutation_proposals"
STATUS_CHECK = "ck_knowledge_mutation_proposals_status"
REASON_CHECK = "ck_knowledge_mutation_proposals_rejection_reason"
JOURNAL_CHECK = "ck_knowledge_mutation_proposals_decision_journal"


def upgrade() -> None:
    """결정 저널 컬럼을 더하고 status에 결정 상태를 허용한다."""
    op.add_column(
        TABLE, sa.Column("reviewer", sa.String(length=255), nullable=True)
    )
    op.add_column(
        TABLE,
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        TABLE, sa.Column("rejection_reason", sa.Text(), nullable=True)
    )
    op.drop_constraint(STATUS_CHECK, TABLE, type_="check")
    op.create_check_constraint(
        STATUS_CHECK,
        TABLE,
        "status IN ('pending', 'approved', 'applied', "
        "'rejected', 'stale', 'abandoned')",
    )
    op.create_check_constraint(
        REASON_CHECK,
        TABLE,
        "status != 'rejected' OR rejection_reason IS NOT NULL",
    )
    op.create_check_constraint(
        JOURNAL_CHECK,
        TABLE,
        "status NOT IN ('approved', 'rejected', 'applied') "
        "OR (reviewer IS NOT NULL AND btrim(reviewer) != '' "
        "AND reviewed_at IS NOT NULL)",
    )


def downgrade() -> None:
    """결정 컬럼을 되돌린다.

    approved나 rejected 행이 남아 있으면 원래 CHECK 복원이 실패한다.
    결정 기록이 있는 DB를 되돌리는 것은 데이터 손실이므로 실패가 맞다.
    """
    op.drop_constraint(JOURNAL_CHECK, TABLE, type_="check")
    op.drop_constraint(REASON_CHECK, TABLE, type_="check")
    op.drop_constraint(STATUS_CHECK, TABLE, type_="check")
    op.create_check_constraint(
        STATUS_CHECK,
        TABLE,
        "status IN ('pending', 'applied', 'stale', 'abandoned')",
    )
    op.drop_column(TABLE, "rejection_reason")
    op.drop_column(TABLE, "reviewed_at")
    op.drop_column(TABLE, "reviewer")
