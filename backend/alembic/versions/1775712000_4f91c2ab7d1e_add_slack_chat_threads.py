"""Add slack_chat_threads

Revision ID: 4f91c2ab7d1e
Revises: 60c21457ca11
Create Date: 2026-04-09 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "4f91c2ab7d1e"
down_revision: Union[str, Sequence[str], None] = "60c21457ca11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "slack_chat_threads",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.String(length=20), nullable=False),
        sa.Column("channel_id", sa.String(length=20), nullable=False),
        sa.Column("thread_ts", sa.String(length=32), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chat_room_id", sa.BigInteger(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("slack_user_id", sa.String(length=20), nullable=False),
        sa.Column("last_raw_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["chat_room_id"], ["chat_rooms.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
        sa.UniqueConstraint("team_id", "channel_id", "thread_ts", name="uq_slack_chat_threads_thread"),
    )
    op.create_index(op.f("ix_slack_chat_threads_chat_room_id"), "slack_chat_threads", ["chat_room_id"], unique=False)
    op.create_index(op.f("ix_slack_chat_threads_session_id"), "slack_chat_threads", ["session_id"], unique=True)
    op.create_index(op.f("ix_slack_chat_threads_user_id"), "slack_chat_threads", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_slack_chat_threads_user_id"), table_name="slack_chat_threads")
    op.drop_index(op.f("ix_slack_chat_threads_session_id"), table_name="slack_chat_threads")
    op.drop_index(op.f("ix_slack_chat_threads_chat_room_id"), table_name="slack_chat_threads")
    op.drop_table("slack_chat_threads")
