"""add_channel_roles_drop_reviewer_grants

Revision ID: c6643084f8b9
Revises: 01c86d4ae713
Create Date: 2026-08-10 20:18:06.128837

"""
from typing import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c6643084f8b9'
down_revision: Union[str, Sequence[str], None] = '01c86d4ae713'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ARTIFACTS_TABLE = "knowledge_artifacts"
GRANTS_TABLE = "wiki_reviewer_grants"


def upgrade() -> None:
    """채널·폴더·역할 테이블을 만들고 검토자 권한 테이블을 없앤다.

    생성 순서가 중요하다. 하위 테이블이 (workspace_id, id) 복합 FK로
    상위를 참조하므로, 참조 대상 UNIQUE를 가진 테이블이 먼저 있어야
    한다.
    """
    op.create_table(
        "channels",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True
        ),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.UniqueConstraint(
            "workspace_id", "name", name="uq_channels_workspace_name"
        ),
        # 하위 테이블의 (workspace_id, channel_id) 복합 FK가 참조할
        # 잉여 UNIQUE다.
        sa.UniqueConstraint(
            "workspace_id", "id", name="uq_channels_workspace_id_id"
        ),
    )
    op.create_table(
        "channel_folders",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True
        ),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column(
            "channel_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        # 폴더가 다른 workspace의 채널에 붙는 배치를 DB가 막는다.
        sa.ForeignKeyConstraint(
            ["workspace_id", "channel_id"],
            ["channels.workspace_id", "channels.id"],
            name="fk_channel_folders_channel",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "channel_id", "name", name="uq_channel_folders_channel_name"
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "id",
            name="uq_channel_folders_workspace_id_id",
        ),
    )
    op.create_table(
        "channel_admins",
        sa.Column(
            "channel_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("user_id", sa.Integer(), primary_key=True),
        sa.Column("granted_by", sa.Integer(), nullable=True),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["channel_id"], ["channels.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"]),
    )
    op.create_index(
        "ix_channel_admins_user_id", "channel_admins", ["user_id"]
    )
    op.create_table(
        "artifact_owners",
        sa.Column(
            "artifact_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("user_id", sa.Integer(), primary_key=True),
        sa.Column("granted_by", sa.Integer(), nullable=True),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            [f"{ARTIFACTS_TABLE}.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"]),
    )
    op.create_index(
        "ix_artifact_owners_user_id", "artifact_owners", ["user_id"]
    )

    op.add_column(
        ARTIFACTS_TABLE,
        sa.Column(
            "channel_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
    )
    op.add_column(
        ARTIFACTS_TABLE,
        sa.Column(
            "folder_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
    )
    # ondelete를 주지 않아 RESTRICT다. 문서가 남은 채널·폴더는 지워지지
    # 않는다. 복합 FK는 참조 컬럼이 NULL이면 검사되지 않으므로
    # 미분류(NULL)는 그대로 성립한다.
    op.create_foreign_key(
        "fk_knowledge_artifacts_channel",
        ARTIFACTS_TABLE,
        "channels",
        ["workspace_id", "channel_id"],
        ["workspace_id", "id"],
    )
    op.create_foreign_key(
        "fk_knowledge_artifacts_folder",
        ARTIFACTS_TABLE,
        "channel_folders",
        ["workspace_id", "folder_id"],
        ["workspace_id", "id"],
    )
    op.create_index(
        "ix_knowledge_artifacts_channel_id",
        ARTIFACTS_TABLE,
        ["channel_id"],
    )
    op.create_index(
        "ix_knowledge_artifacts_folder_id",
        ARTIFACTS_TABLE,
        ["folder_id"],
    )

    op.drop_table(GRANTS_TABLE)


def downgrade() -> None:
    """검토자 권한 테이블을 되살리고 채널·역할 스키마를 역순으로 없앤다."""
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

    op.drop_index("ix_knowledge_artifacts_folder_id", ARTIFACTS_TABLE)
    op.drop_index("ix_knowledge_artifacts_channel_id", ARTIFACTS_TABLE)
    op.drop_constraint(
        "fk_knowledge_artifacts_folder",
        ARTIFACTS_TABLE,
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_knowledge_artifacts_channel",
        ARTIFACTS_TABLE,
        type_="foreignkey",
    )
    op.drop_column(ARTIFACTS_TABLE, "folder_id")
    op.drop_column(ARTIFACTS_TABLE, "channel_id")

    op.drop_index("ix_artifact_owners_user_id", "artifact_owners")
    op.drop_table("artifact_owners")
    op.drop_index("ix_channel_admins_user_id", "channel_admins")
    op.drop_table("channel_admins")
    op.drop_table("channel_folders")
    op.drop_table("channels")
