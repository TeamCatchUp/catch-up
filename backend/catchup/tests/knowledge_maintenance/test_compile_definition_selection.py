"""정의 기반 entity 선택 질의를 fake와 실 PostgreSQL 양쪽으로 확인한다.

정의는 조건이지 인기 순위가 아니다. 그래서 고르는 기준은 entity 종류와
살아 있는지 여부뿐이고, 차례는 이름·식별자 사전순으로 못 박는다. claim
수로 줄을 세우면 같은 정의가 지식이 쌓일 때마다 다른 문서를 낳는다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import KnowledgeArtifact
from catchup.db.models import KnowledgeNode as NodeRow
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.tests.knowledge_maintenance.test_compile_entity_artifacts import (
    FakeArtifactRepository,
)

# 이름이 같을 때의 차례를 확인하려면 식별자를 우연에 맡길 수 없다.
# 앞자리만 다른 두 값을 두고 큰 쪽을 먼저 넣는다.
LATER_ID = uuid.UUID("ffffffff-0000-4000-8000-000000000001")
EARLIER_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(KnowledgeArtifact.__tablename__):
        engine.dispose()
        pytest.skip("artifact 테이블이 없다. alembic upgrade head가 필요하다.")

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


@pytest.fixture
def uow_factory(
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> Callable[[], KnowledgeMaintenanceUnitOfWork]:
    return lambda: KnowledgeMaintenanceUnitOfWork(
        session_factory, workspace_id=workspace_id
    )


def _node(
    session: Session,
    workspace_id: int,
    name: str,
    entity_type: str,
    *,
    lifecycle_state: str = "active",
    node_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """정해진 종류·상태의 canonical entity 노드를 하나 만든다."""
    node = NodeRow(
        id=node_id or uuid.uuid4(),
        workspace_id=workspace_id,
        node_kind="entity",
        entity_type=entity_type,
        canonical_key=f"test:{entity_type}:{uuid.uuid4().hex}",
        display_name=name,
        lifecycle_state=lifecycle_state,
    )
    session.add(node)
    session.flush()
    return node.id


def test_selects_only_matching_active_nodes(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """고른 종류의 살아 있는 노드만 이름순으로 나온다."""
    with session_factory() as session:
        _node(session, workspace_id, "요청 B", "feature_request")
        _node(session, workspace_id, "요청 A", "feature_request")
        _node(
            session,
            workspace_id,
            "접힌 요청",
            "feature_request",
            lifecycle_state="retired",
        )
        _node(session, workspace_id, "결제팀", "team")
        session.commit()

    with uow_factory() as uow:
        found = uow.artifacts.find_entity_nodes_by_types(
            entity_types=["feature_request"]
        )

    assert [source.display_name for source in found] == ["요청 A", "요청 B"]


def test_selection_is_deterministic(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """같은 입력을 두 번 물으면 같은 목록이 나온다."""
    with session_factory() as session:
        _node(session, workspace_id, "결제팀", "team")
        _node(session, workspace_id, "검색팀", "team")
        session.commit()

    with uow_factory() as uow:
        first = uow.artifacts.find_entity_nodes_by_types(
            entity_types=["team"]
        )
    with uow_factory() as uow:
        second = uow.artifacts.find_entity_nodes_by_types(
            entity_types=["team"]
        )

    assert first == second


def test_selection_breaks_name_ties_by_id(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """이름이 같으면 식별자 사전순으로 갈라 차례를 고정한다."""
    with session_factory() as session:
        _node(
            session,
            workspace_id,
            "같은 이름",
            "release",
            node_id=LATER_ID,
        )
        _node(
            session,
            workspace_id,
            "같은 이름",
            "release",
            node_id=EARLIER_ID,
        )
        session.commit()

    with uow_factory() as uow:
        found = uow.artifacts.find_entity_nodes_by_types(
            entity_types=["release"]
        )

    assert [source.node_id for source in found] == [EARLIER_ID, LATER_ID]


def test_selection_accepts_several_types(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """여러 종류를 함께 고르면 종류를 섞어 이름순으로 나온다."""
    with session_factory() as session:
        _node(session, workspace_id, "가 요청", "feature_request")
        _node(session, workspace_id, "나 팀", "team")
        _node(session, workspace_id, "다 릴리스", "release")
        session.commit()

    with uow_factory() as uow:
        found = uow.artifacts.find_entity_nodes_by_types(
            entity_types=["feature_request", "team"]
        )

    assert [source.display_name for source in found] == ["가 요청", "나 팀"]


def test_fake_selects_only_matching_active_nodes() -> None:
    """fake도 종류·상태로 거르고 이름순으로 돌려준다."""
    repository = FakeArtifactRepository(
        nodes=[
            (uuid.uuid4(), "요청 B", "feature_request", "active"),
            (uuid.uuid4(), "요청 A", "feature_request", "active"),
            (uuid.uuid4(), "접힌 요청", "feature_request", "retired"),
            (uuid.uuid4(), "결제팀", "team", "active"),
        ],
    )

    found = repository.find_entity_nodes_by_types(
        entity_types=["feature_request"]
    )

    assert [source.display_name for source in found] == ["요청 A", "요청 B"]


def test_fake_breaks_name_ties_by_id() -> None:
    """fake의 동점 처리도 실 어댑터와 같이 식별자 사전순이다."""
    repository = FakeArtifactRepository(
        nodes=[
            (LATER_ID, "같은 이름", "release", "active"),
            (EARLIER_ID, "같은 이름", "release", "active"),
        ],
    )

    found = repository.find_entity_nodes_by_types(entity_types=["release"])

    assert [source.node_id for source in found] == [EARLIER_ID, LATER_ID]
