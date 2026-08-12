"""add_artifact_definitions

Revision ID: 6c8b2659938b
Revises: c6643084f8b9
Create Date: 2026-08-12 14:46:48.648206

"""
from typing import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6c8b2659938b'
down_revision: Union[str, Sequence[str], None] = 'c6643084f8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ARTIFACTS_TABLE = "knowledge_artifacts"
DEFINITIONS_TABLE = "artifact_definitions"
CHANNELS_TABLE = "channels"


def upgrade() -> None:
    """채널 설정 컬럼과 아티팩트 정의 테이블을 만든다.

    생성 순서가 중요하다. knowledge_artifacts의 복합 FK가 참조하는
    UNIQUE(workspace_id, id)는 artifact_definitions 테이블 정의에 들어
    있으므로, 테이블이 먼저 만들어져야 FK를 걸 수 있다.
    """
    # 목적·문체 프리셋 id와 자연어 입력 자리를 채널에 둔다.
    op.add_column(
        CHANNELS_TABLE,
        sa.Column("purpose_preset", sa.String(length=64), nullable=True),
    )
    op.add_column(
        CHANNELS_TABLE,
        sa.Column("purpose_text", sa.Text(), nullable=True),
    )
    op.add_column(
        CHANNELS_TABLE,
        sa.Column("style_preset", sa.String(length=64), nullable=True),
    )
    op.add_column(
        CHANNELS_TABLE,
        sa.Column("style_text", sa.Text(), nullable=True),
    )

    op.create_table(
        DEFINITIONS_TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column(
            "channel_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column(
            "selection_spec", postgresql.JSONB(), nullable=False
        ),
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
        # ondelete를 주지 않아 RESTRICT다. 정의가 남아 있는 채널은 지워지지
        # 않고, 지우려면 정의를 먼저 정리해야 한다.
        sa.ForeignKeyConstraint(
            ["workspace_id", "channel_id"],
            ["channels.workspace_id", "channels.id"],
            name="fk_artifact_definitions_channel",
        ),
        sa.UniqueConstraint(
            "channel_id", "kind", name="uq_artifact_definitions_channel_kind"
        ),
        # knowledge_artifacts의 복합 FK가 참조할 잉여 UNIQUE다.
        sa.UniqueConstraint(
            "workspace_id",
            "id",
            name="uq_artifact_definitions_workspace_id_id",
        ),
    )

    op.add_column(
        ARTIFACTS_TABLE,
        sa.Column(
            "definition_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
    )
    # 문서와 정의가 같은 workspace임을 DB가 보증한다. ondelete를 주지 않아
    # RESTRICT다. 복합 FK는 참조 컬럼이 NULL이면 검사되지 않으므로 정의
    # 없이 만들어진 문서는 그대로 성립한다.
    op.create_foreign_key(
        "fk_knowledge_artifacts_definition",
        ARTIFACTS_TABLE,
        DEFINITIONS_TABLE,
        ["workspace_id", "definition_id"],
        ["workspace_id", "id"],
    )
    # 정의 하나가 같은 대상에 문서를 둘 만들지 못하게 한다. PG에서 UNIQUE는
    # NULL을 중복으로 세지 않으므로 definition_id가 NULL인 문서는 걸리지
    # 않는다.
    op.create_unique_constraint(
        "uq_knowledge_artifacts_definition_subject",
        ARTIFACTS_TABLE,
        ["definition_id", "subject_node_id"],
    )
    op.create_index(
        "ix_knowledge_artifacts_definition_id",
        ARTIFACTS_TABLE,
        ["definition_id"],
    )


def downgrade() -> None:
    """아티팩트 정의 스키마와 채널 설정 컬럼을 역순으로 없앤다."""
    op.drop_index("ix_knowledge_artifacts_definition_id", ARTIFACTS_TABLE)
    op.drop_constraint(
        "uq_knowledge_artifacts_definition_subject",
        ARTIFACTS_TABLE,
        type_="unique",
    )
    op.drop_constraint(
        "fk_knowledge_artifacts_definition",
        ARTIFACTS_TABLE,
        type_="foreignkey",
    )
    op.drop_column(ARTIFACTS_TABLE, "definition_id")

    op.drop_table(DEFINITIONS_TABLE)

    op.drop_column(CHANNELS_TABLE, "style_text")
    op.drop_column(CHANNELS_TABLE, "style_preset")
    op.drop_column(CHANNELS_TABLE, "purpose_text")
    op.drop_column(CHANNELS_TABLE, "purpose_preset")
