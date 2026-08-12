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
PROPOSALS_TABLE = "knowledge_artifact_change_proposals"
REVISIONS_TABLE = "knowledge_artifact_revisions"
VERDICTS_TABLE = "knowledge_block_verdicts"

# 정의 기반 문서를 고르는 부분식이다. 아래 파괴적 정리가 이 범위 밖은
# 건드리지 않는다.
DEFINITION_ARTIFACT_IDS = (
    f"SELECT id FROM {ARTIFACTS_TABLE} WHERE definition_id IS NOT NULL"
)
DEFINITION_PROPOSAL_IDS = (
    f"SELECT id FROM {PROPOSALS_TABLE}"
    f" WHERE artifact_id IN ({DEFINITION_ARTIFACT_IDS})"
)


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
        # 문서 kind 컬럼과 길이가 같아야 정의 kind가 문서에 그대로 실린다.
        sa.Column("kind", sa.String(length=32), nullable=False),
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
        # 문서가 "정의와 같은 채널·같은 kind"임을 DB로 붙들 복합 FK의
        # 참조 지반이다.
        sa.UniqueConstraint(
            "workspace_id",
            "id",
            "channel_id",
            "kind",
            name="uq_artifact_definitions_identity",
        ),
    )

    op.add_column(
        ARTIFACTS_TABLE,
        sa.Column(
            "definition_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
    )
    # 문서가 딛고 선 정의와 같은 workspace·채널·kind임을 DB가 보증한다.
    # ondelete를 주지 않아 RESTRICT다. 복합 FK는 참조 컬럼이 NULL이면
    # 검사되지 않으므로 정의 없이 만들어진 문서는 그대로 성립한다.
    op.create_foreign_key(
        "fk_knowledge_artifacts_definition",
        ARTIFACTS_TABLE,
        DEFINITIONS_TABLE,
        ["workspace_id", "definition_id", "channel_id", "kind"],
        ["workspace_id", "id", "channel_id", "kind"],
    )
    # definition_id만 채우고 channel_id를 비우면 위 복합 FK가 통째로 풀린다.
    # 그 우회를 막는다. kind는 NOT NULL이라 따로 막을 필요가 없다.
    op.create_check_constraint(
        "ck_knowledge_artifacts_definition_channel",
        ARTIFACTS_TABLE,
        "definition_id IS NULL OR channel_id IS NOT NULL",
    )
    # 옛 (workspace, kind, subject) 전역 UNIQUE는 정의 기반 identity와
    # 충돌한다 — 채널이 다른 두 정의가 같은 대상을 문서화하는 일이 정상인데
    # 두 번째 INSERT가 막힌다. 정의 이전 문서(definition_id NULL)에만 옛
    # 의미를 남기는 부분 유니크 인덱스로 바꾼다.
    op.drop_constraint(
        "uq_knowledge_artifacts_subject", ARTIFACTS_TABLE, type_="unique"
    )
    op.create_index(
        "uq_knowledge_artifacts_subject",
        ARTIFACTS_TABLE,
        ["workspace_id", "kind", "subject_node_id"],
        unique=True,
        postgresql_where=sa.text("definition_id IS NULL"),
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


def _delete_definition_backed_artifacts() -> None:
    """정의 기반 문서와 거기서 파생된 행을 FK 의존 역순으로 지운다.

    옛 스키마에는 (workspace, kind, subject) 전역 UNIQUE가 있어, 채널이
    다른 두 정의가 같은 대상을 각각 문서화한 상태를 담을 수 없다. 정의
    기능을 쓴 DB를 되돌리려면 옛 스키마에 존재할 수 없는 행을 먼저
    걷어내야 한다.

    proposal과 revision은 서로를 참조하고 그 두 FK에는 ondelete가 없어
    삭제 순서만으로는 풀리지 않는다. proposal의 base_revision을 먼저
    끊고 revision·proposal 차례로 지운다. artifact_owners는 ondelete
    CASCADE라 문서 삭제에 딸려 간다.
    """
    op.execute(
        sa.text(
            f"UPDATE {PROPOSALS_TABLE} SET base_revision_id = NULL"
            f" WHERE artifact_id IN ({DEFINITION_ARTIFACT_IDS})"
        )
    )
    op.execute(
        sa.text(
            f"DELETE FROM {VERDICTS_TABLE}"
            f" WHERE proposal_id IN ({DEFINITION_PROPOSAL_IDS})"
        )
    )
    op.execute(
        sa.text(
            f"DELETE FROM {REVISIONS_TABLE}"
            f" WHERE artifact_id IN ({DEFINITION_ARTIFACT_IDS})"
        )
    )
    op.execute(
        sa.text(
            f"DELETE FROM {PROPOSALS_TABLE}"
            f" WHERE artifact_id IN ({DEFINITION_ARTIFACT_IDS})"
        )
    )
    op.execute(
        sa.text(
            f"DELETE FROM {ARTIFACTS_TABLE} WHERE definition_id IS NOT NULL"
        )
    )


def downgrade() -> None:
    """아티팩트 정의 스키마와 채널 설정 컬럼을 역순으로 없앤다.

    파괴적 롤백이다. 정의를 딛고 만들어진 문서와 그 파생 행(검수 판정·
    변경 제안·판본·담당자)을 지운 뒤에야 옛 전역 UNIQUE를 되돌릴 수
    있다. 정의 없는 문서(definition_id NULL)는 그대로 남는다.
    """
    _delete_definition_backed_artifacts()

    op.drop_index("ix_knowledge_artifacts_definition_id", ARTIFACTS_TABLE)
    # 부분 인덱스를 걷고 849358b997d8이 만든 전역 UNIQUE를 되돌린다.
    op.drop_index("uq_knowledge_artifacts_subject", ARTIFACTS_TABLE)
    op.create_unique_constraint(
        "uq_knowledge_artifacts_subject",
        ARTIFACTS_TABLE,
        ["workspace_id", "kind", "subject_node_id"],
    )
    op.drop_constraint(
        "ck_knowledge_artifacts_definition_channel",
        ARTIFACTS_TABLE,
        type_="check",
    )
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
