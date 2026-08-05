"""읽기 경로 SQL reader 2개를 실 PostgreSQL로 확인한다.

as-of 구간 규칙과 alias 정확 일치 규칙은 파이썬이 아니라 SQL 술어 안에
산다. fake로는 술어가 틀려도 드러나지 않으므로 실 DB에 넣어 본다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator
from datetime import datetime
from datetime import timezone

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
from catchup.db.models import KnowledgeClaimCandidate as ClaimRow
from catchup.db.models import KnowledgeEntityCandidate as EntityCandidateRow
from catchup.db.models import KnowledgeExtractionRun as RunRow
from catchup.db.models import KnowledgeNode as NodeRow
from catchup.db.models import KnowledgeOntologySnapshot as SnapshotRow
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)

T_JULY_10 = datetime(2026, 7, 10, tzinfo=timezone.utc)
T_AUG_1 = datetime(2026, 8, 1, tzinfo=timezone.utc)
JULY_1 = datetime(2026, 7, 1, tzinfo=timezone.utc)
JULY_15 = datetime(2026, 7, 15, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(ClaimRow.__tablename__):
        engine.dispose()
        pytest.skip("claim 테이블이 없다. alembic upgrade head가 필요하다.")

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


def _entity_node(session: Session, workspace_id: int, name: str) -> uuid.UUID:
    """canonical entity 노드를 하나 만든다."""
    node = NodeRow(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        node_kind="entity",
        entity_type="feature",
        canonical_key=f"test:feature:{uuid.uuid4().hex}",
        display_name=name,
    )
    session.add(node)
    session.flush()
    return node.id


def _extraction_run(session: Session, workspace_id: int) -> uuid.UUID:
    """claim을 매달 추출 실행을 하나 만든다."""
    ontology_version = uuid.uuid4().hex[:8]
    session.add(
        SnapshotRow(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            ontology_id="test",
            version=ontology_version,
            predicates=[],
            relation_types=[],
        )
    )
    session.flush()
    input_node = NodeRow(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        node_kind="observation",
        resource_type="observation",
        resource_id=str(uuid.uuid4()),
    )
    session.add(input_node)
    session.flush()
    run = RunRow(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        input_node_id=input_node.id,
        provider="test",
        model="test",
        extractor_version="1",
        prompt_version="1",
        ontology_id="test",
        ontology_version=ontology_version,
        status="succeeded",
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    session.flush()
    return run.id


def _claim(
    session: Session,
    workspace_id: int,
    run_id: uuid.UUID,
    *,
    node_id: uuid.UUID | None = None,
    candidate_id: uuid.UUID | None = None,
    status: str,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    predicate: str = "release_month",
    value: str = "2026-09",
) -> uuid.UUID:
    """유효 구간과 상태를 지정한 claim 후보를 하나 만든다."""
    row = ClaimRow(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        extraction_run_id=run_id,
        local_key=f"c-{uuid.uuid4().hex}",
        subject_node_id=node_id,
        subject_entity_candidate_id=candidate_id,
        predicate=predicate,
        value_type="string",
        value=value,
        value_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        statement=f"{predicate}={value}",
        ontology_id="test",
        ontology_version="1",
        extraction_method="llm",
        resolution_status=status,
        valid_from=valid_from,
        valid_to=valid_to,
    )
    session.add(row)
    session.flush()
    return row.id


def _resolved_candidate(
    session: Session,
    workspace_id: int,
    run_id: uuid.UUID,
    node_id: uuid.UUID,
) -> uuid.UUID:
    """어떤 노드로 해소를 마친 entity 후보를 하나 만든다."""
    candidate = EntityCandidateRow(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        extraction_run_id=run_id,
        local_key=f"e-{uuid.uuid4().hex}",
        proposed_type="feature",
        proposed_name="결제 기능",
        extraction_method="llm",
        resolution_status="accepted",
        resolved_node_id=node_id,
    )
    session.add(candidate)
    session.flush()
    return candidate.id


def test_find_entity_by_normalized_alias(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """정규화 alias 정확 일치로 노드를 찾고, 미등록이면 None을 준다."""
    with session_factory() as session:
        node_id = _entity_node(session, workspace_id, "오픈 API")
        session.commit()

    with uow_factory() as uow:
        # 실 DB에는 E2E가 남긴 alias가 이미 있다. 고정 문자열을 쓰면
        # 남의 노드를 찾아 놓고 실패한다.
        normalized = f"캐치업 오픈 api {uuid.uuid4().hex}"
        uow.knowledge_nodes.add_alias(
            workspace_id=workspace_id,
            node_id=node_id,
            alias=normalized.upper(),
            normalized_alias=normalized,
            source="human",
        )

        found = uow.knowledge_nodes.find_entity_by_normalized_alias(
            workspace_id=workspace_id,
            normalized_alias=normalized,
        )
        assert found is not None
        assert found.id == node_id

        missing = uow.knowledge_nodes.find_entity_by_normalized_alias(
            workspace_id=workspace_id,
            normalized_alias="없는 이름",
        )
        assert missing is None


def test_find_entity_by_normalized_alias_is_deterministic(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """같은 alias가 두 노드에 걸리면 node id 순 첫 번째를 준다."""
    with session_factory() as session:
        first = _entity_node(session, workspace_id, "A")
        second = _entity_node(session, workspace_id, "B")
        session.commit()

    with uow_factory() as uow:
        normalized = f"중복 alias {uuid.uuid4().hex}"
        for node_id in (first, second):
            uow.knowledge_nodes.add_alias(
                workspace_id=workspace_id,
                node_id=node_id,
                alias=normalized,
                normalized_alias=normalized,
                source="human",
            )

        found = uow.knowledge_nodes.find_entity_by_normalized_alias(
            workspace_id=workspace_id,
            normalized_alias=normalized,
        )
        assert found is not None
        assert found.id == min(first, second)


def test_as_of_returns_interval_matching_accepted_only(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """as-of 구간 안에 있는 accepted claim만 돌려준다."""
    with session_factory() as session:
        node_id = _entity_node(session, workspace_id, "결제")
        run_id = _extraction_run(session, workspace_id)

        claim_a = _claim(
            session,
            workspace_id,
            run_id,
            node_id=node_id,
            status="accepted",
            valid_from=JULY_1,
            value="A",
        )
        claim_b = _claim(
            session,
            workspace_id,
            run_id,
            node_id=node_id,
            status="accepted",
            valid_from=JULY_1,
            valid_to=JULY_15,
            value="B",
        )
        claim_c = _claim(
            session,
            workspace_id,
            run_id,
            node_id=node_id,
            status="accepted",
            value="C",
        )
        _claim(
            session,
            workspace_id,
            run_id,
            node_id=node_id,
            status="pending",
            value="D",
        )
        _claim(
            session,
            workspace_id,
            run_id,
            node_id=node_id,
            status="rejected",
            value="E",
        )
        session.commit()

    with uow_factory() as uow:
        at_august = uow.knowledge_candidates.find_accepted_claims_as_of(
            workspace_id=workspace_id,
            subject_node_id=node_id,
            at=T_AUG_1,
        )
        assert {claim.claim_id for claim in at_august} == {claim_a, claim_c}

        at_july = uow.knowledge_candidates.find_accepted_claims_as_of(
            workspace_id=workspace_id,
            subject_node_id=node_id,
            at=T_JULY_10,
        )
        assert {claim.claim_id for claim in at_july} == {
            claim_a,
            claim_b,
            claim_c,
        }

        by_id = {claim.claim_id: claim for claim in at_july}
        assert by_id[claim_b].valid_from == JULY_1
        assert by_id[claim_b].valid_to == JULY_15
        assert by_id[claim_c].valid_from is None
        assert by_id[claim_a].predicate == "release_month"
        assert by_id[claim_a].value_type == "string"
        assert by_id[claim_a].value == "A"
        assert by_id[claim_a].statement == "release_month=A"


def test_as_of_includes_claims_resolved_to_the_node(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """subject가 그 노드로 해소된 entity 후보인 claim도 포함한다."""
    with session_factory() as session:
        node_id = _entity_node(session, workspace_id, "결제")
        run_id = _extraction_run(session, workspace_id)
        candidate_id = _resolved_candidate(
            session, workspace_id, run_id, node_id
        )
        claim_id = _claim(
            session,
            workspace_id,
            run_id,
            candidate_id=candidate_id,
            status="accepted",
            value="via-candidate",
        )
        session.commit()

    with uow_factory() as uow:
        found = uow.knowledge_candidates.find_accepted_claims_as_of(
            workspace_id=workspace_id,
            subject_node_id=node_id,
            at=T_AUG_1,
        )
        assert [claim.claim_id for claim in found] == [claim_id]


def test_as_of_predicate_filter(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """predicate를 주면 그 predicate의 claim만 돌려준다."""
    with session_factory() as session:
        node_id = _entity_node(session, workspace_id, "결제")
        run_id = _extraction_run(session, workspace_id)
        wanted = _claim(
            session,
            workspace_id,
            run_id,
            node_id=node_id,
            status="accepted",
            predicate="owner",
            value="플랫폼팀",
        )
        _claim(
            session,
            workspace_id,
            run_id,
            node_id=node_id,
            status="accepted",
            predicate="release_month",
            value="2026-09",
        )
        session.commit()

    with uow_factory() as uow:
        found = uow.knowledge_candidates.find_accepted_claims_as_of(
            workspace_id=workspace_id,
            subject_node_id=node_id,
            at=T_AUG_1,
            predicate="owner",
        )
        assert [claim.claim_id for claim in found] == [wanted]


def test_history_includes_closed_accepted_and_excludes_rejected(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """history는 닫힌 accepted까지 싣고 rejected는 계속 뺀다."""
    with session_factory() as session:
        node_id = _entity_node(session, workspace_id, "결제")
        run_id = _extraction_run(session, workspace_id)

        closed = _claim(
            session,
            workspace_id,
            run_id,
            node_id=node_id,
            status="accepted",
            valid_from=JULY_1,
            valid_to=JULY_15,
            value="B",
        )
        live = _claim(
            session,
            workspace_id,
            run_id,
            node_id=node_id,
            status="accepted",
            valid_from=JULY_15,
            value="A",
        )
        undated = _claim(
            session,
            workspace_id,
            run_id,
            node_id=node_id,
            status="accepted",
            value="C",
        )
        _claim(
            session,
            workspace_id,
            run_id,
            node_id=node_id,
            status="pending",
            value="D",
        )
        _claim(
            session,
            workspace_id,
            run_id,
            node_id=node_id,
            status="rejected",
            value="E",
        )
        session.commit()

    with uow_factory() as uow:
        at_august = uow.knowledge_candidates.find_accepted_claims_as_of(
            workspace_id=workspace_id,
            subject_node_id=node_id,
            at=T_AUG_1,
        )
        assert {claim.claim_id for claim in at_august} == {live, undated}

        history = uow.knowledge_candidates.find_accepted_claims_history(
            workspace_id=workspace_id,
            subject_node_id=node_id,
        )
        assert [claim.claim_id for claim in history] == [
            undated,
            closed,
            live,
        ]

        by_id = {claim.claim_id: claim for claim in history}
        assert by_id[closed].valid_from == JULY_1
        assert by_id[closed].valid_to == JULY_15
        assert by_id[live].valid_to is None
        assert by_id[undated].valid_from is None


def test_history_includes_claims_resolved_to_the_node(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """subject가 그 노드로 해소된 후보인 닫힌 claim도 history에 든다."""
    with session_factory() as session:
        node_id = _entity_node(session, workspace_id, "결제")
        run_id = _extraction_run(session, workspace_id)
        candidate_id = _resolved_candidate(
            session, workspace_id, run_id, node_id
        )
        claim_id = _claim(
            session,
            workspace_id,
            run_id,
            candidate_id=candidate_id,
            status="accepted",
            valid_from=JULY_1,
            valid_to=JULY_15,
            value="via-candidate",
        )
        session.commit()

    with uow_factory() as uow:
        found = uow.knowledge_candidates.find_accepted_claims_history(
            workspace_id=workspace_id,
            subject_node_id=node_id,
        )
        assert [claim.claim_id for claim in found] == [claim_id]


def test_history_predicate_filter(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """predicate를 주면 닫힌 claim도 그 predicate만 남는다."""
    with session_factory() as session:
        node_id = _entity_node(session, workspace_id, "결제")
        run_id = _extraction_run(session, workspace_id)
        wanted = _claim(
            session,
            workspace_id,
            run_id,
            node_id=node_id,
            status="accepted",
            predicate="owner",
            valid_from=JULY_1,
            valid_to=JULY_15,
            value="플랫폼팀",
        )
        _claim(
            session,
            workspace_id,
            run_id,
            node_id=node_id,
            status="accepted",
            predicate="release_month",
            value="2026-09",
        )
        session.commit()

    with uow_factory() as uow:
        found = uow.knowledge_candidates.find_accepted_claims_history(
            workspace_id=workspace_id,
            subject_node_id=node_id,
            predicate="owner",
        )
        assert [claim.claim_id for claim in found] == [wanted]
