from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator
from datetime import datetime
from datetime import timezone

import pytest
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import func
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import KnowledgeNode as KnowledgeNodeRow
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.mappers import (
    knowledge_node_to_row,
)
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.source_change import SourceChangeEnvelope
from catchup.knowledge_maintenance.domain.knowledge_node import KnowledgeNode
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
from catchup.knowledge_maintenance.domain.knowledge_node import NodeLifecycleState
from catchup.knowledge_maintenance.domain.knowledge_node import resource_ref_for
from catchup.knowledge_maintenance.domain.observation import NormalizedObservation
from catchup.knowledge_maintenance.domain.observation import ObservationKind
from catchup.knowledge_maintenance.domain.observation import content_hash
from catchup.knowledge_maintenance.domain.source_version import SourceVersion
from catchup.knowledge_maintenance.services.ingest_source_version import (
    ingest_source_change,
)
from catchup.knowledge_maintenance.services.normalize_source_version import (
    normalize_source_version,
)

NOW = datetime(2026, 7, 28, 9, 0, tzinfo=timezone.utc)
SOURCE_TYPE = "test-knowledge-maintenance"
NORMALIZED_CONTENT = "고객: 결제 기능은 언제 나오나요?"


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(KnowledgeNodeRow.__tablename__):
        engine.dispose()
        pytest.skip("knowledge_nodes 테이블이 없다. alembic upgrade head가 필요하다.")

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
) -> Callable[[], KnowledgeMaintenanceUnitOfWork]:
    return lambda: KnowledgeMaintenanceUnitOfWork(session_factory)


class _StubNormalizer:
    normalizer_id = "test.normalizer"
    normalizer_version = "1"

    def normalize(self, source_version: SourceVersion) -> NormalizedObservation:
        return NormalizedObservation(
            normalizer_id=self.normalizer_id,
            normalizer_version=self.normalizer_version,
            observation_kind=ObservationKind.DOCUMENT,
            content=NORMALIZED_CONTENT,
            content_hash=content_hash(NORMALIZED_CONTENT),
        )


def _envelope(workspace_id: int, **overrides: object) -> SourceChangeEnvelope:
    document_id = f"CAM-{uuid.uuid4().hex[:8]}"
    values: dict[str, object] = {
        "schema_version": 1,
        "event_id": f"event-{document_id}",
        "workspace_id": workspace_id,
        "source_type": SOURCE_TYPE,
        "source_identity": {
            "entity_type": "user_chat",
            "scope_id": "ch-test",
            "target_id": "ch-test",
            "external_document_id": document_id,
        },
        "change_kind": "created",
        "source_version_key": "1",
        "title": "결제 기능 문의",
        "canonical_url": None,
        "content": '{"detail": {}}',
        "content_type": "application/vnd.channel-talk.user-chat+json",
        "source_updated_at": NOW,
        "observed_at": NOW,
        "idempotency_key": f"test:{document_id}",
        "metadata": {},
    }
    values.update(overrides)
    return SourceChangeEnvelope.model_validate(values)


def _node_count(session_factory: Callable[[], Session], workspace_id: int) -> int:
    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        session = uow.knowledge_nodes._session  # noqa: SLF001
        return session.scalar(
            select(func.count())
            .select_from(KnowledgeNodeRow)
            .where(KnowledgeNodeRow.workspace_id == workspace_id)
        )


def test_ingesting_a_source_version_gives_it_a_node(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """원문이 저장되면 graph에서 그것을 가리킬 수 있어야 한다."""
    result = ingest_source_change(_envelope(workspace_id), uow=uow_factory())

    with KnowledgeMaintenanceUnitOfWork(session_factory) as reader:
        node = reader.knowledge_nodes.get_for_resource(
            workspace_id=workspace_id,
            node_kind=NodeKind.SOURCE_VERSION,
            resource_id=result.source_version_id,
        )

    assert node is not None
    assert node.node_kind == NodeKind.SOURCE_VERSION
    assert node.resource.resource_id == str(result.source_version_id)
    assert node.lifecycle_state == NodeLifecycleState.ACTIVE


def test_normalizing_gives_the_observation_a_node(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """ExtractionRun이 가리킬 대상은 Observation node다."""
    ingested = ingest_source_change(_envelope(workspace_id), uow=uow_factory())
    with KnowledgeMaintenanceUnitOfWork(session_factory) as reader:
        source_version = reader.source_versions.get_by_idempotency_key(
            workspace_id=workspace_id,
            idempotency_key=_stored_idempotency_key(reader, ingested.source_version_id),
        )

    normalized = normalize_source_version(
        source_version,
        normalizer=_StubNormalizer(),
        uow=uow_factory(),
    )

    with KnowledgeMaintenanceUnitOfWork(session_factory) as reader:
        node = reader.knowledge_nodes.get_for_resource(
            workspace_id=workspace_id,
            node_kind=NodeKind.OBSERVATION,
            resource_id=normalized.observation.id,
        )

    assert node is not None
    assert node.node_kind == NodeKind.OBSERVATION


def _stored_idempotency_key(
    uow: KnowledgeMaintenanceUnitOfWork,
    source_version_id: uuid.UUID,
) -> str:
    from catchup.db.models import SourceVersion as SourceVersionRow

    session = uow.source_versions._session  # noqa: SLF001
    return session.scalar(
        select(SourceVersionRow.idempotency_key).where(
            SourceVersionRow.id == source_version_id
        )
    )


def test_reingesting_does_not_make_a_second_node(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """같은 원문이 graph에서 서로 다른 대상으로 보이면 안 된다."""
    envelope = _envelope(workspace_id)
    before = _node_count(session_factory, workspace_id)

    first = ingest_source_change(envelope, uow=uow_factory())
    after_first = _node_count(session_factory, workspace_id)
    second = ingest_source_change(envelope, uow=uow_factory())
    after_second = _node_count(session_factory, workspace_id)

    assert first.source_version_id == second.source_version_id
    assert after_first == before + 1
    assert after_second == after_first


def test_renormalizing_does_not_make_a_second_node(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """재정규화가 Observation node를 늘리지 않는다."""
    ingested = ingest_source_change(_envelope(workspace_id), uow=uow_factory())
    with KnowledgeMaintenanceUnitOfWork(session_factory) as reader:
        source_version = reader.source_versions.get_by_idempotency_key(
            workspace_id=workspace_id,
            idempotency_key=_stored_idempotency_key(reader, ingested.source_version_id),
        )

    normalizer = _StubNormalizer()
    normalize_source_version(source_version, normalizer=normalizer, uow=uow_factory())
    after_first = _node_count(session_factory, workspace_id)
    normalize_source_version(source_version, normalizer=normalizer, uow=uow_factory())

    assert _node_count(session_factory, workspace_id) == after_first


def test_one_resource_cannot_have_two_nodes(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """partial unique index가 중복 node를 막는다.

    `ensure_for_resource`의 '있으면 재사용'이 경합에 져도 DB가 마지막으로
    막아 준다.
    """
    resource_id = uuid.uuid4()

    def _row() -> KnowledgeNodeRow:
        return knowledge_node_to_row(
            KnowledgeNode(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                node_kind=NodeKind.OBSERVATION,
                resource=resource_ref_for(NodeKind.OBSERVATION, resource_id),
            )
        )

    with pytest.raises(IntegrityError):
        with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
            session = uow.knowledge_nodes._session  # noqa: SLF001
            session.add(_row())
            session.add(_row())
            uow.commit()


def test_a_node_without_a_resource_is_allowed(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """원문에서 나온 Entity는 자기 테이블이 없어 resource 참조를 갖지 않는다.

    partial index가 `resource_type IS NOT NULL`을 조건으로 두는 이유이며,
    그렇지 않으면 이런 node가 둘 이상 생길 수 없다.
    """
    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        session = uow.knowledge_nodes._session  # noqa: SLF001
        for name in ("결제 기능", "인증 시스템"):
            session.add(
                knowledge_node_to_row(
                    KnowledgeNode(
                        id=uuid.uuid4(),
                        workspace_id=workspace_id,
                        node_kind=NodeKind.ENTITY,
                        entity_type="feature",
                        canonical_key=f"feature:{name}",
                        display_name=name,
                    )
                )
            )
        uow.commit()


def test_two_entities_cannot_share_a_canonical_key(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """canonical_key가 같으면 같은 대상이므로 node가 둘일 수 없다."""
    with pytest.raises(IntegrityError):
        with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
            session = uow.knowledge_nodes._session  # noqa: SLF001
            for _ in range(2):
                session.add(
                    knowledge_node_to_row(
                        KnowledgeNode(
                            id=uuid.uuid4(),
                            workspace_id=workspace_id,
                            node_kind=NodeKind.ENTITY,
                            entity_type="feature",
                            canonical_key="feature:결제 기능",
                            display_name="결제 기능",
                        )
                    )
                )
            uow.commit()


def test_merged_node_must_point_at_its_target() -> None:
    """병합된 node는 어디로 흡수됐는지 밝혀야 한다."""
    with pytest.raises(ValueError, match="merged"):
        KnowledgeNode(
            id=uuid.uuid4(),
            workspace_id=1,
            node_kind=NodeKind.ENTITY,
            lifecycle_state=NodeLifecycleState.MERGED,
        )


def test_a_live_node_must_not_point_at_another() -> None:
    with pytest.raises(ValueError, match="merged"):
        KnowledgeNode(
            id=uuid.uuid4(),
            workspace_id=1,
            node_kind=NodeKind.ENTITY,
            merged_into_node_id=uuid.uuid4(),
        )


def test_resource_type_must_match_node_kind() -> None:
    """Observation node가 SourceVersion을 가리키면 graph가 거짓말을 한다."""
    with pytest.raises(ValueError, match="resource_type"):
        KnowledgeNode(
            id=uuid.uuid4(),
            workspace_id=1,
            node_kind=NodeKind.OBSERVATION,
            resource=resource_ref_for(NodeKind.SOURCE_VERSION, uuid.uuid4()),
        )


def test_ensure_returns_the_same_node_when_called_twice(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """같은 record에 두 번 불러도 node는 하나다.

    서비스는 새 record일 때만 이것을 부르지만, 백필이나 재처리처럼 이미
    node가 있는 상태에서 부르는 호출자가 있다. port가 '만들거나 이미 있는
    것을 돌려준다'고 약속한 것이 이 경우다.
    """
    resource_id = uuid.uuid4()

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        first = uow.knowledge_nodes.ensure_for_resource(
            workspace_id=workspace_id,
            node_kind=NodeKind.OBSERVATION,
            resource_id=resource_id,
        )
        second = uow.knowledge_nodes.ensure_for_resource(
            workspace_id=workspace_id,
            node_kind=NodeKind.OBSERVATION,
            resource_id=resource_id,
        )
        uow.commit()

    assert first.id == second.id

    with KnowledgeMaintenanceUnitOfWork(session_factory) as reader:
        session = reader.knowledge_nodes._session  # noqa: SLF001
        count = session.scalar(
            select(func.count())
            .select_from(KnowledgeNodeRow)
            .where(
                KnowledgeNodeRow.workspace_id == workspace_id,
                KnowledgeNodeRow.resource_id == str(resource_id),
            )
        )
    assert count == 1


def test_lookup_does_not_cross_node_kinds(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """같은 식별자를 다른 종류로 물으면 찾지 못해야 한다.

    resource_id만 보고 답하면 SourceVersion node를 Observation node라고
    답하게 되고, ExtractionRun이 원문을 입력으로 삼는 잘못이 생긴다.
    """
    resource_id = uuid.uuid4()

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        uow.knowledge_nodes.ensure_for_resource(
            workspace_id=workspace_id,
            node_kind=NodeKind.SOURCE_VERSION,
            resource_id=resource_id,
        )
        uow.commit()

    with KnowledgeMaintenanceUnitOfWork(session_factory) as reader:
        as_observation = reader.knowledge_nodes.get_for_resource(
            workspace_id=workspace_id,
            node_kind=NodeKind.OBSERVATION,
            resource_id=resource_id,
        )
        as_source_version = reader.knowledge_nodes.get_for_resource(
            workspace_id=workspace_id,
            node_kind=NodeKind.SOURCE_VERSION,
            resource_id=resource_id,
        )

    assert as_observation is None
    assert as_source_version is not None
