"""아티팩트 정의 스키마 제약을 실 PostgreSQL로 확인한다.

정의는 "이 채널의 이 종류 문서를 무엇으로 채울지"를 정하는 행이라, 채널당
중복 정의나 workspace를 넘는 연결이 생기면 컴파일 대상이 갈라진다. fake는
제약을 흉내내는 쪽이므로 실 DB에 직접 넣어 본다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import ArtifactDefinition
from catchup.db.models import Channel
from catchup.db.models import KnowledgeArtifact
from catchup.db.models import KnowledgeNode as NodeRow
from catchup.db.models import User
from catchup.db.models import Workspace
from catchup.tests.knowledge_maintenance.test_artifact_schema import (
    _violated_constraint,
)

ARTIFACT_KIND = "entity_summary"
DEFINITION_KIND = "entity_summary"

# 정의 하나가 담는 선택 규칙의 최소 형태다. 이 테스트가 보는 것은 JSONB
# 컬럼이 값을 받는지이지 규칙의 의미가 아니라 상수 하나로 충분하다.
# 도메인 serialize_selection_spec의 출력 모양과 일치해야 한다.
SELECTION_SPEC: dict[str, Any] = {
    "entity_filter": {"entity_types": ["feature_request"]},
    "relation_paths": [],
    "predicate_sections": None,
}

CHANNEL_CONFIG_COLUMNS = (
    "purpose_preset",
    "purpose_text",
    "style_preset",
    "style_text",
)


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


@pytest.fixture(scope="module")
def workspace_id(engine: Engine) -> int:
    with engine.connect() as connection:
        found = connection.execute(
            select(Workspace.id).order_by(Workspace.id).limit(1)
        ).scalar()

    if found is None:
        pytest.skip("workspace가 없어 통합 테스트를 건너뛴다.")
    return found


@pytest.fixture(scope="module")
def user_id(engine: Engine) -> int:
    with engine.connect() as connection:
        found = connection.execute(
            select(User.id).order_by(User.id).limit(1)
        ).scalar()

    if found is None:
        pytest.skip("user가 없어 통합 테스트를 건너뛴다.")
    return found


@pytest.fixture
def session_factory(engine: Engine) -> Iterator[Callable[[], Session]]:
    connection = engine.connect()
    transaction = connection.begin()

    yield sessionmaker(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )

    transaction.rollback()
    connection.close()


def _other_workspace_id(
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> int:
    """비교용 workspace 하나를 새로 마련한다.

    workspace 경계를 넘는 연결을 시험하려면 서로 다른 workspace 둘이
    필요하다. 테스트 트랜잭션 안에서만 살고 끝나면 되돌려진다.
    """
    with session_factory() as session:
        company_id = session.execute(
            select(Workspace.company_id).where(Workspace.id == workspace_id)
        ).scalar_one()
        other = Workspace(
            name=f"ws-{uuid.uuid4().hex[:8]}", company_id=company_id
        )
        session.add(other)
        session.commit()
        return other.id


def _channel(
    session_factory: Callable[[], Session],
    workspace_id: int,
    user_id: int,
) -> uuid.UUID:
    """채널 한 개를 새로 만든다."""
    channel_id = uuid.uuid4()
    with session_factory() as session:
        session.add(
            Channel(
                id=channel_id,
                workspace_id=workspace_id,
                name=f"채널-{uuid.uuid4().hex[:8]}",
                created_by=user_id,
            )
        )
        session.commit()
    return channel_id


def _definition(
    session_factory: Callable[[], Session],
    workspace_id: int,
    channel_id: uuid.UUID,
    user_id: int,
    kind: str = DEFINITION_KIND,
) -> uuid.UUID:
    """채널 아래 정의 한 개를 새로 만든다."""
    definition_id = uuid.uuid4()
    with session_factory() as session:
        session.add(
            ArtifactDefinition(
                id=definition_id,
                workspace_id=workspace_id,
                channel_id=channel_id,
                kind=kind,
                selection_spec=SELECTION_SPEC,
                created_by=user_id,
            )
        )
        session.commit()
    return definition_id


def _subject_node(
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> uuid.UUID:
    """문서가 다룰 주제 노드 한 개를 새로 만든다."""
    node_id = uuid.uuid4()
    with session_factory() as session:
        session.add(
            NodeRow(
                id=node_id,
                workspace_id=workspace_id,
                node_kind="entity",
                entity_type="feature",
                canonical_key=f"test:feature:{uuid.uuid4().hex}",
                display_name="결제 기능",
            )
        )
        session.commit()
    return node_id


def _artifact(
    session_factory: Callable[[], Session],
    workspace_id: int,
    subject_node_id: uuid.UUID | None = None,
    definition_id: uuid.UUID | None = None,
    kind: str = ARTIFACT_KIND,
) -> uuid.UUID:
    """주제 노드까지 갖춘 문서 한 편을 새로 만든다."""
    if subject_node_id is None:
        subject_node_id = _subject_node(session_factory, workspace_id)

    artifact_id = uuid.uuid4()
    with session_factory() as session:
        session.add(
            KnowledgeArtifact(
                id=artifact_id,
                workspace_id=workspace_id,
                kind=kind,
                subject_node_id=subject_node_id,
                definition_id=definition_id,
                title="결제 기능",
            )
        )
        session.commit()
    return artifact_id


def test_definition_kind_unique_per_channel(
    workspace_id: int,
    user_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """한 채널에 같은 kind 정의가 둘 생기지 않는다.

    정의가 둘이면 같은 종류 문서를 어느 규칙으로 채울지 갈라진다.
    """
    channel_id = _channel(session_factory, workspace_id, user_id)
    _definition(session_factory, workspace_id, channel_id, user_id)

    with pytest.raises(IntegrityError) as excinfo:
        _definition(session_factory, workspace_id, channel_id, user_id)

    assert (
        _violated_constraint(excinfo)
        == "uq_artifact_definitions_channel_kind"
    )


def test_definition_channel_cross_workspace_blocked(
    workspace_id: int,
    user_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """다른 workspace의 채널 아래에는 정의를 만들 수 없다."""
    other_workspace_id = _other_workspace_id(session_factory, workspace_id)
    foreign_channel_id = _channel(
        session_factory, other_workspace_id, user_id
    )

    with pytest.raises(IntegrityError) as excinfo:
        _definition(
            session_factory, workspace_id, foreign_channel_id, user_id
        )

    assert _violated_constraint(excinfo) == "fk_artifact_definitions_channel"


def test_artifact_definition_cross_workspace_blocked(
    workspace_id: int,
    user_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """다른 workspace의 정의는 문서에 걸 수 없다."""
    other_workspace_id = _other_workspace_id(session_factory, workspace_id)
    foreign_channel_id = _channel(
        session_factory, other_workspace_id, user_id
    )
    foreign_definition_id = _definition(
        session_factory, other_workspace_id, foreign_channel_id, user_id
    )

    with pytest.raises(IntegrityError) as excinfo:
        _artifact(
            session_factory,
            workspace_id,
            definition_id=foreign_definition_id,
        )

    assert (
        _violated_constraint(excinfo) == "fk_knowledge_artifacts_definition"
    )


def test_definition_subject_unique(
    workspace_id: int,
    user_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """한 정의가 같은 대상에 문서를 둘 만들지 못한다.

    문서 kind를 달리해 (workspace, kind, subject) 제약을 비켜 둔다. 그래야
    막는 쪽이 정의-대상 제약임이 드러난다.
    """
    channel_id = _channel(session_factory, workspace_id, user_id)
    definition_id = _definition(
        session_factory, workspace_id, channel_id, user_id
    )
    subject_node_id = _subject_node(session_factory, workspace_id)
    _artifact(
        session_factory,
        workspace_id,
        subject_node_id=subject_node_id,
        definition_id=definition_id,
    )

    with pytest.raises(IntegrityError) as excinfo:
        _artifact(
            session_factory,
            workspace_id,
            subject_node_id=subject_node_id,
            definition_id=definition_id,
            kind="relation_summary",
        )

    assert (
        _violated_constraint(excinfo)
        == "uq_knowledge_artifacts_definition_subject"
    )


def test_null_definition_documents_coexist(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """정의가 없는 문서는 같은 대상에도 여럿 남는다.

    PG의 UNIQUE는 NULL을 중복으로 세지 않는다. 정의 기능이 생기기 전에
    만들어진 문서가 마이그레이션만으로 밀려나지 않는 근거다.
    """
    subject_node_id = _subject_node(session_factory, workspace_id)
    _artifact(
        session_factory, workspace_id, subject_node_id=subject_node_id
    )
    _artifact(
        session_factory,
        workspace_id,
        subject_node_id=subject_node_id,
        kind="relation_summary",
    )

    with session_factory() as session:
        rows = session.execute(
            select(KnowledgeArtifact.id).where(
                KnowledgeArtifact.subject_node_id == subject_node_id,
                KnowledgeArtifact.definition_id.is_(None),
            )
        ).all()

    assert len(rows) == 2


def test_channels_config_columns_exist(engine: Engine) -> None:
    """채널이 목적·문체 설정 칸을 갖고 있고 전부 비워 둘 수 있다.

    기존 채널은 설정 없이 만들어졌으므로 NOT NULL이면 마이그레이션이 막힌다.
    """
    columns = {
        column["name"]: column
        for column in inspect(engine).get_columns(Channel.__tablename__)
    }

    for name in CHANNEL_CONFIG_COLUMNS:
        assert name in columns
        assert columns[name]["nullable"] is True
