"""add feedback_user to chat_histories

Revision ID: 1f4f5d6a7b8c
Revises: 09a0daaececa
Create Date: 2026-04-14 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1f4f5d6a7b8c'
down_revision: Union[str, Sequence[str], None] = '09a0daaececa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'chat_histories',
        sa.Column(
            'feedback_user',
            sa.Text(),
            nullable=True,
            comment='Slack Bot v0 : 피드백은 답변 생성 요청자 관계 없이 누구나 한번만 피드백을 남길 수 있다.',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chat_histories', 'feedback_user')
