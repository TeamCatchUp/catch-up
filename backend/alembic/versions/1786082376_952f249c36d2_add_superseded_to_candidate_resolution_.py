"""add superseded to candidate resolution status checks

Revision ID: 952f249c36d2
Revises: 9e1e569e7441
Create Date: 2026-08-07 14:59:36.023089

"""
from typing import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '952f249c36d2'
down_revision: Union[str, Sequence[str], None] = '9e1e569e7441'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (테이블, 제약 이름, 새 조건, 옛 조건)을 한 곳에 모은다.
_CONSTRAINTS = [
    (
        "knowledge_entity_candidates",
        "ck_knowledge_entity_candidates_resolution_status",
        "resolution_status IN "
        "('pending', 'accepted', 'merged', 'rejected', 'superseded')",
        "resolution_status IN ('pending', 'accepted', 'merged', 'rejected')",
    ),
    (
        "knowledge_claim_candidates",
        "ck_knowledge_claim_candidates_resolution_status",
        "resolution_status IN "
        "('pending', 'accepted', 'duplicate', 'rejected', 'superseded')",
        "resolution_status IN ('pending', 'accepted', 'duplicate', 'rejected')",
    ),
    (
        "knowledge_relation_assertion_candidates",
        "ck_knowledge_relation_candidates_resolution_status",
        "resolution_status IN "
        "('pending', 'accepted', 'duplicate', 'rejected', 'superseded')",
        "resolution_status IN ('pending', 'accepted', 'duplicate', 'rejected')",
    ),
]


def upgrade() -> None:
    """후보 세 테이블의 resolution_status CHECK에 superseded를 더한다."""
    for table, name, new_condition, _ in _CONSTRAINTS:
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, new_condition)


def downgrade() -> None:
    """resolution_status CHECK를 superseded 이전 4값으로 되돌린다."""
    for table, name, _, old_condition in _CONSTRAINTS:
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, old_condition)
