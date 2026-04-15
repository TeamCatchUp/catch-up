"""Add slack thread execution lease fields

Revision ID: a8f4d4f2b7c1
Revises: 4f91c2ab7d1e
Create Date: 2026-04-10 16:42:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a8f4d4f2b7c1"
down_revision: Union[str, Sequence[str], None] = "4f91c2ab7d1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "slack_chat_threads",
        sa.Column(
            "is_answer_in_progress",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "slack_chat_threads",
        sa.Column(
            "in_progress_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("slack_chat_threads", "in_progress_started_at")
    op.drop_column("slack_chat_threads", "is_answer_in_progress")
