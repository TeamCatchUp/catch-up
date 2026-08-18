"""r1_review_api_schema

Revision ID: eee5acf7ee4f
Revises: 174617949f26
Create Date: 2026-08-18 18:01:54.868725

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "eee5acf7ee4f"
down_revision: Union[str, Sequence[str], None] = "174617949f26"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """정의 folder_id, 채널 목적 테이블, 즐겨찾기 테이블을 만들고 채널의 단일 목적 컬럼을 없앤다."""
    op.add_column(
        "artifact_definitions",
        sa.Column("folder_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_artifact_definitions_folder",
        "artifact_definitions",
        "channel_folders",
        ["folder_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "channel_purposes",
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose_preset", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("channel_id", "purpose_preset"),
    )
    # 기존 채널의 단일 목적을 첫 행으로 옮긴다. 값이 없는 채널은 건너뛴다.
    op.execute(
        """
        INSERT INTO channel_purposes (channel_id, purpose_preset, position)
        SELECT id, purpose_preset, 0
        FROM channels
        WHERE purpose_preset IS NOT NULL
        """
    )
    op.drop_column("channels", "purpose_preset")

    op.create_table(
        "wiki_artifact_favorites",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["artifact_id"], ["knowledge_artifacts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "artifact_id"),
    )
    op.create_index(
        "ix_wiki_artifact_favorites_user_workspace",
        "wiki_artifact_favorites",
        ["user_id", "workspace_id"],
    )


def downgrade() -> None:
    """위 변경을 되돌린다. 채널 목적은 position 0 행만 단일 컬럼으로 복원한다."""
    op.drop_index(
        "ix_wiki_artifact_favorites_user_workspace",
        table_name="wiki_artifact_favorites",
    )
    op.drop_table("wiki_artifact_favorites")

    op.add_column(
        "channels",
        sa.Column("purpose_preset", sa.String(length=64), nullable=True),
    )
    op.execute(
        """
        UPDATE channels c
        SET purpose_preset = p.purpose_preset
        FROM channel_purposes p
        WHERE p.channel_id = c.id AND p.position = 0
        """
    )
    op.drop_table("channel_purposes")

    op.drop_constraint(
        "fk_artifact_definitions_folder", "artifact_definitions", type_="foreignkey"
    )
    op.drop_column("artifact_definitions", "folder_id")
