"""아티팩트 정의 조회 포트를 fake와 실 PostgreSQL 양쪽으로 확인한다.

정의 목록은 컴파일의 입구다. 순서가 흔들리면 같은 지식 상태에서도 문서가
다른 차례로 만들어지고, 깨진 선택 규칙이 조용히 빠지면 검토자가 그 정의의
문서를 "지식이 없다"로 오해한다. 그래서 정렬과 fail-closed 두 가지를 실
DB에서도 확인한다.
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
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import ArtifactDefinition
from catchup.db.models import User
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.domain.artifact_definition import RelationPath
from catchup.knowledge_maintenance.domain.artifact_definition import RelationStep
from catchup.knowledge_maintenance.domain.artifact_definition import SelectionSpec
from catchup.knowledge_maintenance.domain.artifact_definition import SelectionSpecError
from catchup.knowledge_maintenance.domain.artifact_definition import (
    deserialize_selection_spec,
)
from catchup.knowledge_maintenance.ports.artifact_definitions import (
    ArtifactDefinitionRepository,
)
from catchup.knowledge_maintenance.ports.artifact_definitions import (
    StoredArtifactDefinition,
)
from catchup.tests.knowledge_maintenance.test_artifact_definition_schema import (
    SELECTION_SPEC,
)
from catchup.tests.knowledge_maintenance.test_artifact_definition_schema import _channel

DEFINITION_KIND = "entity_summary"

# 정렬을 확인하려면 식별자를 우연에 맡길 수 없다. 앞자리만 다른 두 값을
# 두고 큰 쪽을 먼저 넣는다.
FIRST_DEFINITION_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
SECOND_DEFINITION_ID = uuid.UUID("ffffffff-0000-4000-8000-000000000002")


class FakeArtifactDefinitionRepository:
    """정의 조회 저장소를 실 어댑터의 규칙까지 흉내 내어 대신한다.

    실 어댑터는 workspace를 생성 시점에 고정하고 식별자 사전순으로
    돌려주며, 깨진 선택 규칙을 만나면 던진다. 셋 중 하나라도 빠뜨리면
    이 fake를 쓰는 상위 테스트가 실제와 다른 입구를 보게 된다.
    """

    def __init__(
        self,
        rows: list[tuple[uuid.UUID, uuid.UUID, str, dict[str, Any]]],
        channel_styles: dict[uuid.UUID, str] | None = None,
    ) -> None:
        self.rows = list(rows)
        # 채널 문체는 저장된 id 그대로다. 카탈로그 해석은 서비스가 한다.
        self.channel_styles = dict(channel_styles or {})

    def find_channel_style(self, *, channel_id: uuid.UUID) -> str | None:
        """채널에 걸린 문체 preset id를 돌려준다. 없으면 None이다."""
        return self.channel_styles.get(channel_id)

    def list_definitions(self) -> tuple[StoredArtifactDefinition, ...]:
        return tuple(
            StoredArtifactDefinition(
                id=definition_id,
                channel_id=channel_id,
                kind=kind,
                selection_spec=deserialize_selection_spec(raw_spec),
                title_prefix=kind,
            )
            for definition_id, channel_id, kind, raw_spec in sorted(
                self.rows, key=lambda row: str(row[0])
            )
        )


def test_fake_satisfies_repository_protocol() -> None:
    """fake가 조회 포트의 계약을 그대로 만족한다."""
    repository: ArtifactDefinitionRepository = (
        FakeArtifactDefinitionRepository([])
    )

    assert repository.list_definitions() == ()


def test_fake_orders_by_id() -> None:
    """fake도 식별자 사전순으로 돌려준다."""
    channel_id = uuid.uuid4()
    repository = FakeArtifactDefinitionRepository(
        [
            (SECOND_DEFINITION_ID, channel_id, DEFINITION_KIND, SELECTION_SPEC),
            (FIRST_DEFINITION_ID, channel_id, DEFINITION_KIND, SELECTION_SPEC),
        ]
    )

    stored = repository.list_definitions()

    assert [definition.id for definition in stored] == [
        FIRST_DEFINITION_ID,
        SECOND_DEFINITION_ID,
    ]


def test_title_prefix_follows_kind() -> None:
    """제목 앞자리는 정의의 kind를 그대로 따른다.

    title_prefix는 저장되는 칸이라 채우는 쪽이 kind와 다른 값을 넣을 수
    있다. 저장소가 그 칸을 kind로 채운다는 것을 값 생성이 아니라 조회
    결과로 확인한다.
    """
    repository = FakeArtifactDefinitionRepository(
        [
            (
                FIRST_DEFINITION_ID,
                uuid.uuid4(),
                "relation_summary",
                SELECTION_SPEC,
            )
        ]
    )

    stored = repository.list_definitions()

    assert stored[0].title_prefix == "relation_summary"
    assert stored[0].title_prefix == stored[0].kind


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
def seed_workspace_id(engine: Engine) -> int:
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


@pytest.fixture
def workspace_id(
    session_factory: Callable[[], Session],
    seed_workspace_id: int,
) -> int:
    """이 테스트만 쓰는 빈 workspace를 마련한다.

    기존 workspace에는 다른 테스트나 실제 운영이 남긴 정의가 있을 수
    있어 "몇 건이 나오는가"를 셀 수 없다. 테스트 트랜잭션 안에서만
    살고 끝나면 되돌려진다.
    """
    with session_factory() as session:
        company_id = session.execute(
            select(Workspace.company_id).where(
                Workspace.id == seed_workspace_id
            )
        ).scalar_one()
        workspace = Workspace(
            name=f"ws-{uuid.uuid4().hex[:8]}", company_id=company_id
        )
        session.add(workspace)
        session.commit()
        return workspace.id


@pytest.fixture
def uow_factory(
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> Callable[[], KnowledgeMaintenanceUnitOfWork]:
    return lambda: KnowledgeMaintenanceUnitOfWork(
        session_factory, workspace_id=workspace_id
    )


def _seed_definition(
    session_factory: Callable[[], Session],
    workspace_id: int,
    user_id: int,
    *,
    definition_id: uuid.UUID | None = None,
    selection_spec: dict[str, Any] | None = None,
) -> uuid.UUID:
    """채널 하나와 그 아래 정의 하나를 새로 넣는다.

    채널은 정의마다 새로 만든다. 한 채널에 같은 kind 정의는 하나뿐이라
    같은 채널에 둘을 걸면 UNIQUE에 막힌다.
    """
    channel_id = _channel(session_factory, workspace_id, user_id)
    definition_id = definition_id or uuid.uuid4()
    with session_factory() as session:
        session.add(
            ArtifactDefinition(
                id=definition_id,
                workspace_id=workspace_id,
                channel_id=channel_id,
                kind=DEFINITION_KIND,
                selection_spec=(
                    SELECTION_SPEC
                    if selection_spec is None
                    else selection_spec
                ),
                created_by=user_id,
            )
        )
        session.commit()
    return definition_id


def test_list_definitions_returns_deserialized_spec(
    session_factory: Callable[[], Session],
    workspace_id: int,
    user_id: int,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """저장된 JSONB가 선택 규칙 값으로 되돌아온다."""
    spec = {
        "entity_filter": {"entity_types": ["feature_request"]},
        "relation_paths": [{"steps": [{"type": "relates_to", "dir": "out"}]}],
        "predicate_sections": ["depends_on"],
    }
    definition_id = _seed_definition(
        session_factory, workspace_id, user_id, selection_spec=spec
    )

    with uow_factory() as uow:
        stored = uow.artifact_definitions.list_definitions()

    assert len(stored) == 1
    assert stored[0].id == definition_id
    assert stored[0].kind == DEFINITION_KIND
    # 어댑터가 title_prefix 칸을 kind로 채운다. fake만 보면 이 규칙이
    # 실제 어댑터에도 있는지 알 수 없다.
    assert stored[0].title_prefix == DEFINITION_KIND
    assert stored[0].selection_spec == SelectionSpec(
        entity_types=("feature_request",),
        relation_paths=(
            RelationPath(
                steps=(
                    RelationStep(relation_type="relates_to", direction="out"),
                )
            ),
        ),
        predicate_sections=("depends_on",),
    )


def test_list_definitions_orders_by_id(
    session_factory: Callable[[], Session],
    workspace_id: int,
    user_id: int,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """정의는 식별자 사전순으로 나온다.

    입구의 순서가 실행마다 흔들리면 같은 지식 상태에서도 검토 큐에 오는
    차례가 달라진다.
    """
    _seed_definition(
        session_factory,
        workspace_id,
        user_id,
        definition_id=SECOND_DEFINITION_ID,
    )
    _seed_definition(
        session_factory,
        workspace_id,
        user_id,
        definition_id=FIRST_DEFINITION_ID,
    )

    with uow_factory() as uow:
        stored = uow.artifact_definitions.list_definitions()

    assert [definition.id for definition in stored] == [
        FIRST_DEFINITION_ID,
        SECOND_DEFINITION_ID,
    ]


def test_list_definitions_scopes_to_workspace(
    session_factory: Callable[[], Session],
    workspace_id: int,
    seed_workspace_id: int,
    user_id: int,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """다른 workspace의 정의는 보이지 않는다."""
    foreign_definition_id = _seed_definition(
        session_factory, seed_workspace_id, user_id
    )
    own_definition_id = _seed_definition(
        session_factory, workspace_id, user_id
    )

    with uow_factory() as uow:
        stored = uow.artifact_definitions.list_definitions()

    assert [definition.id for definition in stored] == [own_definition_id]
    assert all(
        definition.id != foreign_definition_id for definition in stored
    )


def test_broken_spec_raises_selection_spec_error(
    session_factory: Callable[[], Session],
    workspace_id: int,
    user_id: int,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """스키마 밖 키가 든 정의는 조용히 빠지지 않고 던진다.

    깨진 정의를 건너뛰면 그 정의의 문서만 비고, 검토자는 지식이 없다고
    읽는다. 빈 문서 사고와 같은 종류이므로 목록 전체를 막는다.
    """
    _seed_definition(
        session_factory,
        workspace_id,
        user_id,
        selection_spec={"entity_filter": {"entity_types": ["x"]}, "join": []},
    )

    with uow_factory() as uow:
        with pytest.raises(SelectionSpecError):
            uow.artifact_definitions.list_definitions()
