"""정의 스키마 마이그레이션의 왕복을 실 PostgreSQL로 확인한다.

downgrade는 옛 전역 UNIQUE(workspace, kind, subject)를 되돌린다. 정의
기능을 정상적으로 쓴 DB에는 채널이 다른 두 정의가 같은 대상을 각각
문서화한 행이 있어, 그대로 두면 UNIQUE 생성이 중복으로 막힌다. 정의 기반
문서를 먼저 걷어내는 파괴적 정리가 실제로 도는지 본다.

경고: 이 테스트는 대상 DB의 정의 기반 문서를 downgrade로 전부 지운다.
정의 데이터가 들어 있는 DB에서 돌리면 그 데이터가 사라진다.

이 테스트는 스키마 자체를 되돌렸다 다시 올린다. 세션 트랜잭션 밖에서
alembic이 제 커넥션으로 돌기 때문에 심는 행도 커밋해야 하고, 끝난 뒤
직접 지운다. 파일을 따로 둔 이유도 다른 테스트와 스키마 상태가 겹치지
않게 하기 위해서다.
"""

from __future__ import annotations

import pathlib
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import delete
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from alembic import command
from alembic import config as alembic_config
from catchup.configs.config import settings
from catchup.db.models import ArtifactDefinition
from catchup.db.models import Channel
from catchup.db.models import KnowledgeArtifact
from catchup.db.models import KnowledgeNode as NodeRow
from catchup.db.models import User
from catchup.db.models import Workspace

# 정의 테이블이 생기기 직전 판이다. downgrade가 멈춰야 할 지점.
PREVIOUS_REVISION = "c6643084f8b9"

ARTIFACT_KIND = "entity_summary"

SELECTION_SPEC = {
    "entity_filter": {"entity_types": ["feature_request"]},
    "relation_paths": [],
    "predicate_sections": None,
}

BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[3]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(ArtifactDefinition.__tablename__):
        engine.dispose()
        pytest.skip("정의 테이블이 없다. alembic upgrade head가 필요하다.")

    yield engine
    engine.dispose()


def _alembic() -> alembic_config.Config:
    """이 저장소의 alembic 설정을 그대로 연다.

    env.py가 settings에서 DB URL을 읽으므로 따로 넘기지 않는다.
    """
    return alembic_config.Config(str(ALEMBIC_INI))


def _seed(session: Session, workspace_id: int, user_id: int) -> dict:
    """정의 기반 문서 둘과 정의 없는 문서 하나를 심는다.

    두 문서는 채널이 다른 두 정의 아래 같은 (kind, 대상)을 쓴다. 옛 전역
    UNIQUE로는 담을 수 없는 상태이며, 이것이 downgrade가 넘어야 할 벽이다.
    """
    channel_ids = [uuid.uuid4(), uuid.uuid4()]
    definition_ids = [uuid.uuid4(), uuid.uuid4()]
    subject_node_id = uuid.uuid4()
    legacy_subject_node_id = uuid.uuid4()
    artifact_ids = [uuid.uuid4(), uuid.uuid4()]
    legacy_artifact_id = uuid.uuid4()

    for channel_id in channel_ids:
        session.add(
            Channel(
                id=channel_id,
                workspace_id=workspace_id,
                name=f"채널-{uuid.uuid4().hex[:8]}",
                created_by=user_id,
            )
        )
    for node_id in (subject_node_id, legacy_subject_node_id):
        session.add(
            NodeRow(
                id=node_id,
                workspace_id=workspace_id,
                node_kind="entity",
                entity_type="feature",
                canonical_key=f"migration:feature:{uuid.uuid4().hex}",
                display_name="결제 기능",
            )
        )
    session.flush()

    for definition_id, channel_id in zip(definition_ids, channel_ids):
        session.add(
            ArtifactDefinition(
                id=definition_id,
                workspace_id=workspace_id,
                channel_id=channel_id,
                kind=ARTIFACT_KIND,
                selection_spec=SELECTION_SPEC,
                created_by=user_id,
            )
        )
    session.flush()

    for artifact_id, definition_id, channel_id in zip(
        artifact_ids, definition_ids, channel_ids
    ):
        session.add(
            KnowledgeArtifact(
                id=artifact_id,
                workspace_id=workspace_id,
                kind=ARTIFACT_KIND,
                channel_id=channel_id,
                definition_id=definition_id,
                subject_node_id=subject_node_id,
                title="결제 기능",
            )
        )
    session.add(
        KnowledgeArtifact(
            id=legacy_artifact_id,
            workspace_id=workspace_id,
            kind=ARTIFACT_KIND,
            subject_node_id=legacy_subject_node_id,
            title="정의 이전 문서",
        )
    )
    session.commit()

    return {
        "channel_ids": channel_ids,
        "node_ids": [subject_node_id, legacy_subject_node_id],
        "artifact_ids": artifact_ids,
        "legacy_artifact_id": legacy_artifact_id,
    }


def _cleanup(session: Session, seeded: dict) -> None:
    """심어 둔 행을 FK 의존 역순으로 지운다."""
    session.execute(
        delete(KnowledgeArtifact).where(
            KnowledgeArtifact.id.in_(
                [*seeded["artifact_ids"], seeded["legacy_artifact_id"]]
            )
        )
    )
    session.execute(
        delete(ArtifactDefinition).where(
            ArtifactDefinition.channel_id.in_(seeded["channel_ids"])
        )
    )
    session.execute(
        delete(NodeRow).where(NodeRow.id.in_(seeded["node_ids"]))
    )
    session.execute(
        delete(Channel).where(Channel.id.in_(seeded["channel_ids"]))
    )
    session.commit()


def test_downgrade_clears_definition_backed_artifacts(
    engine: Engine,
) -> None:
    """정의 기반 문서가 있어도 downgrade가 끝까지 돈다.

    정의 기반 문서는 옛 스키마에 존재할 수 없으므로 지워지고, 정의 없는
    문서는 그대로 남는다.
    """
    with Session(engine) as session:
        workspace_id = session.execute(
            select(Workspace.id).order_by(Workspace.id).limit(1)
        ).scalar()
        user_id = session.execute(
            select(User.id).order_by(User.id).limit(1)
        ).scalar()

    if workspace_id is None or user_id is None:
        pytest.skip("workspace·user가 없어 통합 테스트를 건너뛴다.")

    config = _alembic()
    with Session(engine) as session:
        seeded = _seed(session, workspace_id, user_id)

    try:
        command.downgrade(config, PREVIOUS_REVISION)

        assert not inspect(engine).has_table(
            ArtifactDefinition.__tablename__
        )
        with engine.connect() as connection:
            surviving = set(
                connection.execute(
                    text(
                        "SELECT id FROM knowledge_artifacts"
                        " WHERE id = ANY(:ids)"
                    ).bindparams(
                        ids=[
                            *seeded["artifact_ids"],
                            seeded["legacy_artifact_id"],
                        ]
                    )
                ).scalars()
            )

        assert surviving == {seeded["legacy_artifact_id"]}
    finally:
        command.upgrade(config, "head")
        with Session(engine) as session:
            _cleanup(session, seeded)
