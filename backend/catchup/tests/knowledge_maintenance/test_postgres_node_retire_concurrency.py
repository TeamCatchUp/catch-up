"""노드 퇴역과 후보 부착이 서로를 기다리는지 실 PostgreSQL로 확인한다.

되돌림은 후보가 전부 떠난 노드를 물리고, 해소는 후보를 노드에 붙인다. 두
경로가 동시에 돌면 "남은 후보가 없다"를 확인한 직후에 후보가 붙을 수 있고,
그 후보는 퇴역한 노드를 가리키게 된다.

그래서 두 경로 모두 노드 행을 SELECT ... FOR UPDATE로 잠근다. 잠금은 한
트랜잭션이 commit할 때까지 상대를 기다리게 하고, 기다린 쪽은 잠금을 얻은 뒤
값을 다시 읽는다. 이것은 트랜잭션 두 개가 실제로 겹쳐야 드러나므로 가짜
저장소로는 확인할 수 없다.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import delete
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import KnowledgeEntityCandidate as EntityCandidateRow
from catchup.db.models import KnowledgeExtractionRun as ExtractionRunRow
from catchup.db.models import KnowledgeNode as NodeRow
from catchup.db.models import KnowledgeOntologySnapshot as OntologySnapshotRow
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyKnowledgeCandidateRepository,
)
from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemyKnowledgeNodeRepository,
)
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    EntityResolutionStatus,
)
from catchup.knowledge_maintenance.domain.knowledge_node import NodeLifecycleState

# 부착이 잠금을 얻지 못하고 기다리는지 보는 시간이다. 이 시간 안에 끝나지
# 않으면 기다리고 있다고 본다.
BLOCKED_SECONDS = 1.0
# 잠금이 풀린 뒤 부착이 끝나기를 기다리는 시간이다. 넉넉히 준다.
RELEASED_SECONDS = 10.0


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(EntityCandidateRow.__tablename__):
        engine.dispose()
        pytest.skip("candidate 테이블이 없다. alembic upgrade head가 필요하다.")

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


@dataclass(frozen=True)
class _Fixture:
    """두 트랜잭션이 함께 건드릴 노드와 후보를 담는다."""

    node_id: uuid.UUID
    candidate_id: uuid.UUID


@pytest.fixture
def session_factory(engine: Engine) -> Callable[[], Session]:
    """트랜잭션이 실제로 갈라지도록 연결마다 새 session을 준다.

    다른 통합 테스트처럼 바깥 트랜잭션 하나를 두고 끝에 되돌리면, 두
    session이 같은 연결을 나눠 쓰게 되어 잠금이 부딪히지 않는다. 여기서는
    진짜로 commit하고 정리는 뒷정리에서 지운다.
    """
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def seeded(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> Iterator[_Fixture]:
    """entity 노드 하나와 아직 해소되지 않은 후보 하나를 실제로 적어 둔다."""
    input_node_id = uuid.uuid4()
    node_id = uuid.uuid4()
    run_id = uuid.uuid4()
    candidate_id = uuid.uuid4()
    ontology_id = "test.retire-lock"
    ontology_version = uuid.uuid4().hex[:8]

    with session_factory() as session:
        session.add(
            NodeRow(
                id=input_node_id,
                workspace_id=workspace_id,
                node_kind="observation",
                resource_type="test-retire-lock",
                resource_id=str(input_node_id),
            )
        )
        session.add(
            NodeRow(
                id=node_id,
                workspace_id=workspace_id,
                node_kind="entity",
                entity_type="feature",
                display_name="결제 기능",
            )
        )
        session.add(
            OntologySnapshotRow(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                ontology_id=ontology_id,
                version=ontology_version,
                predicates=[],
                relation_types=[],
            )
        )
        session.flush()
        session.add(
            ExtractionRunRow(
                id=run_id,
                workspace_id=workspace_id,
                input_node_id=input_node_id,
                provider="test",
                extractor_version="test.retire-lock/0",
                ontology_id=ontology_id,
                ontology_version=ontology_version,
                status="succeeded",
                started_at=datetime.now(UTC),
            )
        )
        session.flush()
        session.add(
            EntityCandidateRow(
                id=candidate_id,
                workspace_id=workspace_id,
                extraction_run_id=run_id,
                local_key="e1",
                proposed_type="feature",
                proposed_name="결제 기능",
                extraction_method="llm",
                resolution_status="pending",
            )
        )
        session.commit()

    yield _Fixture(node_id=node_id, candidate_id=candidate_id)

    with session_factory() as cleanup:
        # 외래 키 역순으로 지운다.
        cleanup.execute(
            delete(EntityCandidateRow).where(EntityCandidateRow.id == candidate_id)
        )
        cleanup.execute(delete(ExtractionRunRow).where(ExtractionRunRow.id == run_id))
        cleanup.execute(
            delete(OntologySnapshotRow).where(
                OntologySnapshotRow.workspace_id == workspace_id,
                OntologySnapshotRow.ontology_id == ontology_id,
                OntologySnapshotRow.version == ontology_version,
            )
        )
        cleanup.execute(delete(NodeRow).where(NodeRow.id.in_((node_id, input_node_id))))
        cleanup.commit()


def test_attach_waits_for_retire_and_then_refuses_the_retired_node(
    workspace_id: int,
    session_factory: Callable[[], Session],
    seeded: _Fixture,
) -> None:
    """퇴역이 잡은 잠금 동안 부착은 기다리고, 풀린 뒤에는 거부당한다.

    잠금이 없으면 부착은 기다리지 않고 그대로 성공해, 후보가 곧 퇴역할
    노드를 가리킨 채 남는다.
    """
    attach_error: list[BaseException | None] = []
    attach_started = threading.Event()

    def attach() -> None:
        with session_factory() as session:
            repository = SqlAlchemyKnowledgeCandidateRepository(session)
            attach_started.set()
            try:
                repository.mark_entity_resolved(
                    candidate_id=seeded.candidate_id,
                    status=EntityResolutionStatus.MERGED,
                    resolved_node_id=seeded.node_id,
                )
                session.commit()
                attach_error.append(None)
            except BaseException as error:  # noqa: BLE001
                session.rollback()
                attach_error.append(error)

    retire_session = session_factory()
    try:
        retired = SqlAlchemyKnowledgeNodeRepository(retire_session).retire_entity_node(
            workspace_id=workspace_id,
            node_id=seeded.node_id,
        )
        assert retired is True

        worker = threading.Thread(target=attach, daemon=True)
        worker.start()
        assert attach_started.wait(timeout=RELEASED_SECONDS)
        # 아직 commit하지 않았으므로 노드 행 잠금은 이쪽이 쥐고 있다.
        worker.join(timeout=BLOCKED_SECONDS)
        assert worker.is_alive(), "부착이 노드 행 잠금을 기다리지 않았다"

        retire_session.commit()
    finally:
        retire_session.close()

    worker.join(timeout=RELEASED_SECONDS)
    assert not worker.is_alive()
    assert len(attach_error) == 1
    error = attach_error[0]
    assert isinstance(error, ValueError)
    assert str(seeded.node_id) in str(error)

    with session_factory() as session:
        candidate = session.get(EntityCandidateRow, seeded.candidate_id)
        assert candidate is not None
        assert candidate.resolved_node_id is None
        node = session.get(NodeRow, seeded.node_id)
        assert node is not None
        assert node.lifecycle_state == NodeLifecycleState.RETIRED.value


def test_retire_gives_up_when_a_candidate_was_attached_first(
    workspace_id: int,
    session_factory: Callable[[], Session],
    seeded: _Fixture,
) -> None:
    """먼저 붙은 후보가 commit돼 있으면 퇴역은 노드를 그대로 둔다.

    퇴역은 잠금을 얻은 뒤 남은 후보를 다시 세므로, 그 사이에 commit된 부착도
    보인다.
    """
    with session_factory() as attach_session:
        SqlAlchemyKnowledgeCandidateRepository(attach_session).mark_entity_resolved(
            candidate_id=seeded.candidate_id,
            status=EntityResolutionStatus.MERGED,
            resolved_node_id=seeded.node_id,
        )
        attach_session.commit()

    with session_factory() as retire_session:
        retired = SqlAlchemyKnowledgeNodeRepository(retire_session).retire_entity_node(
            workspace_id=workspace_id,
            node_id=seeded.node_id,
        )
        retire_session.commit()

    assert retired is False

    with session_factory() as session:
        node = session.get(NodeRow, seeded.node_id)
        assert node is not None
        assert node.lifecycle_state == NodeLifecycleState.ACTIVE.value
