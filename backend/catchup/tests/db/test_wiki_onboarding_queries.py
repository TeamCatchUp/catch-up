"""온보딩 흐름이 쓰는 채널·정의 쿼리 함수를 실 PostgreSQL로 확인한다.

preset id 저장과 selection_spec JSONB 왕복, 그리고 (channel_id, kind)
UNIQUE는 전부 DB 사실이라 대역으로는 재현되지 않는다. 그래서 실 연결을
빌려 테스트마다 되감는다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator

import pytest
from sqlalchemy import Connection
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
from catchup.db import wiki as wiki_queries
from catchup.db.models import ArtifactDefinition
from catchup.db.models import User
from catchup.db.models import UserStatus
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.domain.artifact_definition import (
    deserialize_selection_spec,
)
from catchup.knowledge_maintenance.domain.artifact_definition import (
    serialize_selection_spec,
)
from catchup.knowledge_maintenance.domain.preset_catalog import (
    _feature_request_status_spec,
)

# ======================= 실 DB fixture =======================


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
def workspace_ids(engine: Engine) -> tuple[int, int]:
    """실 DB에 있는 workspace 두 개를 빌린다."""
    with engine.connect() as connection:
        found = (
            connection.execute(
                select(Workspace.id).order_by(Workspace.id).limit(2)
            )
            .scalars()
            .all()
        )

    if len(found) < 2:
        pytest.skip("workspace가 둘 이상 없어 통합 테스트를 건너뛴다.")
    return found[0], found[1]


@pytest.fixture
def connection(engine: Engine) -> Iterator[Connection]:
    """테스트마다 되감는 연결 하나를 만든다."""
    connection = engine.connect()
    transaction = connection.begin()

    yield connection

    transaction.rollback()
    connection.close()


@pytest.fixture
def session_factory(connection: Connection) -> Callable[[], Session]:
    """같은 트랜잭션 위에 세션을 여는 factory를 만든다."""
    return sessionmaker(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )


@pytest.fixture
def db(session_factory: Callable[[], Session]) -> Iterator[Session]:
    """행을 넣고 읽을 세션을 만든다."""
    session = session_factory()

    yield session

    session.close()


def _make_user(db: Session, *, email: str) -> User:
    """테스트용 사용자 한 명을 만든다."""
    user = User(
        email=email,
        name="구성원",
        provider="keycloak",
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.flush()
    return user


# ======================= 테스트 =======================


def test_add_channel_stores_preset_ids(db, workspace_ids) -> None:
    """preset id가 채널 행에 그대로 저장된다."""
    workspace_id, _ = workspace_ids
    user = _make_user(db, email="onboard@example.com")
    channel = wiki_queries.add_channel(
        db,
        workspace_id=workspace_id,
        name=f"voc-{uuid.uuid4().hex[:8]}",
        created_by=user.id,
        purpose_preset="voc.top_requests",
        style_preset="style.report_summary",
    )
    db.flush()
    assert channel.purpose_preset == "voc.top_requests"
    assert channel.style_preset == "style.report_summary"


def test_add_channel_without_presets_leaves_them_empty(
    db, workspace_ids
) -> None:
    """preset을 주지 않은 기존 호출자는 그대로 동작한다."""
    workspace_id, _ = workspace_ids
    user = _make_user(db, email="onboard0@example.com")
    channel = wiki_queries.add_channel(
        db,
        workspace_id=workspace_id,
        name=f"voc-{uuid.uuid4().hex[:8]}",
        created_by=user.id,
    )
    db.flush()
    assert channel.purpose_preset is None
    assert channel.style_preset is None


def test_add_artifact_definition_roundtrips_the_spec(
    db, workspace_ids
) -> None:
    """직렬화한 선택 규칙이 JSONB를 왕복해도 같은 값으로 돌아온다."""
    workspace_id, _ = workspace_ids
    user = _make_user(db, email="onboard2@example.com")
    channel = wiki_queries.add_channel(
        db,
        workspace_id=workspace_id,
        name=f"voc-{uuid.uuid4().hex[:8]}",
        created_by=user.id,
    )
    db.flush()
    spec = _feature_request_status_spec()
    definition = wiki_queries.add_artifact_definition(
        db,
        workspace_id=workspace_id,
        channel_id=channel.id,
        kind="feature_request_status",
        selection_spec=serialize_selection_spec(spec),
        created_by=user.id,
    )
    db.flush()
    db.expire(definition)
    assert deserialize_selection_spec(definition.selection_spec) == spec


def test_list_definitions_by_channel_orders_by_kind(db, workspace_ids) -> None:
    """그 채널의 정의만 kind 사전순으로 돌려준다."""
    workspace_id, _ = workspace_ids
    user = _make_user(db, email="onboard3@example.com")
    channel = wiki_queries.add_channel(
        db,
        workspace_id=workspace_id,
        name=f"voc-{uuid.uuid4().hex[:8]}",
        created_by=user.id,
    )
    other = wiki_queries.add_channel(
        db,
        workspace_id=workspace_id,
        name=f"voc-{uuid.uuid4().hex[:8]}",
        created_by=user.id,
    )
    db.flush()
    spec = serialize_selection_spec(_feature_request_status_spec())
    for kind in ("request_priority", "feature_request_status"):
        wiki_queries.add_artifact_definition(
            db,
            workspace_id=workspace_id,
            channel_id=channel.id,
            kind=kind,
            selection_spec=spec,
            created_by=user.id,
        )
    wiki_queries.add_artifact_definition(
        db,
        workspace_id=workspace_id,
        channel_id=other.id,
        kind="aaa_other_channel",
        selection_spec=spec,
        created_by=user.id,
    )
    db.flush()

    found = wiki_queries.list_definitions_by_channel(db, channel_id=channel.id)

    assert [definition.kind for definition in found] == [
        "feature_request_status",
        "request_priority",
    ]


def test_duplicate_kind_in_a_channel_violates_the_unique(
    db, workspace_ids
) -> None:
    """같은 채널에 같은 kind 정의를 두 번 넣으면 DB가 막는다."""
    workspace_id, _ = workspace_ids
    user = _make_user(db, email="onboard4@example.com")
    channel = wiki_queries.add_channel(
        db,
        workspace_id=workspace_id,
        name=f"voc-{uuid.uuid4().hex[:8]}",
        created_by=user.id,
    )
    db.flush()
    spec = serialize_selection_spec(_feature_request_status_spec())
    for _ in range(2):
        wiki_queries.add_artifact_definition(
            db,
            workspace_id=workspace_id,
            channel_id=channel.id,
            kind="feature_request_status",
            selection_spec=spec,
            created_by=user.id,
        )

    with pytest.raises(IntegrityError):
        db.flush()
