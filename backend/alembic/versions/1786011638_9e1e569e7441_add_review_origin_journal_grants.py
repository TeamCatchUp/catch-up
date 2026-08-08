"""add review origin journal grants

Revision ID: 9e1e569e7441
Revises: d48fc18e42f7
Create Date: 2026-08-06 19:20:38.654007

"""
from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9e1e569e7441'
down_revision: Union[str, Sequence[str], None] = 'd48fc18e42f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE = "knowledge_artifact_change_proposals"
ORIGIN_CHECK = f"ck_{TABLE}_origin"
JOURNAL_CHECK = f"ck_{TABLE}_decision_journal"
GRANTS_TABLE = "wiki_reviewer_grants"


def upgrade() -> None:
    """origin 컬럼·결정 저널 CHECK·검토자 권한 테이블을 만든다."""
    # 저널 CHECK를 걸기 전에 위반 행이 없는지 확인한다. 위반이 있으면
    # 결정 기록이 훼손된 것이므로 마이그레이션을 멈추고 사람이 본다.
    connection = op.get_bind()
    violating = connection.execute(
        sa.text(
            f"SELECT count(*) FROM {TABLE} "
            "WHERE status IN ('approved', 'rejected') "
            "AND (reviewer IS NULL OR btrim(reviewer) = '' "
            "OR reviewed_at IS NULL)"
        )
    ).scalar()
    if violating:
        raise RuntimeError(
            f"결정 저널이 빈 결정 행이 {violating}건 있다. "
            "데이터 정정 없이 CHECK를 걸 수 없다."
        )

    op.add_column(
        TABLE,
        sa.Column(
            "origin",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'compiled'"),
        ),
    )
    op.create_check_constraint(
        ORIGIN_CHECK,
        TABLE,
        "origin IN ('compiled', 'manual', 'external', 'linked')",
    )
    op.create_check_constraint(
        JOURNAL_CHECK,
        TABLE,
        "status NOT IN ('approved', 'rejected') "
        "OR (reviewer IS NOT NULL AND btrim(reviewer) != '' "
        "AND reviewed_at IS NOT NULL)",
    )
    op.create_table(
        GRANTS_TABLE,
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("workspace_id", sa.Integer, nullable=False),
        sa.Column("granted_by", sa.Integer, nullable=True),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("user_id", "workspace_id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"]),
    )


def downgrade() -> None:
    """origin·저널 CHECK·권한 테이블을 역순으로 되돌린다.

    저널 CHECK는 결정 행이 남아 있어도 떼어낼 수 있다. 제약만 사라지고
    결정 기록 자체는 그대로 남으므로 데이터 손실이 없다.
    """
    op.drop_table(GRANTS_TABLE)
    op.drop_constraint(JOURNAL_CHECK, TABLE, type_="check")
    op.drop_constraint(ORIGIN_CHECK, TABLE, type_="check")
    op.drop_column(TABLE, "origin")
