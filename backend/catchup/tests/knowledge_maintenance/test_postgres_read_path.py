"""읽기 경로 SQL reader를 실 PostgreSQL로 확인한다.

as-of 구간 규칙, alias 정확 일치 규칙, bigm 유사 후보 규칙은 파이썬이
아니라 SQL 술어 안에 산다. fake로는 술어가 틀려도 드러나지 않고
bigm_similarity 점수는 흉내조차 낼 수 없으므로 실 DB에 넣어 본다.
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
from sqlalchemy import event
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
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    query_claims_as_of,
)
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    query_claims_history,
)
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    query_claims_of_node,
)
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    query_claims_of_node_history,
)
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    query_claims_timeline,
)

T_JULY_10 = datetime(2026, 7, 10, tzinfo=timezone.utc)
T_AUG_1 = datetime(2026, 8, 1, tzinfo=timezone.utc)
JULY_1 = datetime(2026, 7, 1, tzinfo=timezone.utc)
JULY_15 = datetime(2026, 7, 15, tzinfo=timezone.utc)
AUG_10 = datetime(2026, 8, 10, tzinfo=timezone.utc)


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


def _entity_node(
    session: Session,
    workspace_id: int,
    name: str,
    *,
    merged_into: uuid.UUID | None = None,
    entity_type: str = "feature",
    node_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """canonical entity 노드를 하나 만든다.

    merged_into를 주면 그 노드로 흡수된 merged 노드가 된다. node_id는
    alias 조회의 id 순 tie-break를 고정해야 할 때 쓴다.
    """
    node = NodeRow(
        id=node_id if node_id is not None else uuid.uuid4(),
        workspace_id=workspace_id,
        node_kind="entity",
        entity_type=entity_type,
        canonical_key=f"test:feature:{uuid.uuid4().hex}",
        display_name=name,
        lifecycle_state="merged" if merged_into is not None else "active",
        merged_into_node_id=merged_into,
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
    statement: str | None = None,
) -> uuid.UUID:
    """유효 구간과 상태를 지정한 claim 후보를 하나 만든다.

    statement를 주지 않으면 `predicate=value` 모양으로 채운다.
    키워드가 statement에만 또는 value에만 있는 경우를 나눠 심어야 할
    때는 명시해 끊는다.
    """
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
        statement=(
            f"{predicate}={value}" if statement is None else statement
        ),
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


def test_find_entity_by_normalized_alias_filters_entity_type(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """entity_type을 주면 다른 type 노드가 앞서도 같은 type을 준다."""
    front, behind = sorted([uuid.uuid4(), uuid.uuid4()])
    with session_factory() as session:
        _entity_node(
            session,
            workspace_id,
            "앞선 노드",
            entity_type="system",
            node_id=front,
        )
        _entity_node(
            session,
            workspace_id,
            "뒤선 노드",
            entity_type="feature",
            node_id=behind,
        )
        session.commit()

    with uow_factory() as uow:
        normalized = f"동명 이type {uuid.uuid4().hex}"
        for node_id in (front, behind):
            uow.knowledge_nodes.add_alias(
                workspace_id=workspace_id,
                node_id=node_id,
                alias=normalized,
                normalized_alias=normalized,
                source="human",
            )

        # 필터가 없으면 id 순 첫 번째, 즉 다른 type 노드가 걸린다.
        assert (
            uow.knowledge_nodes.find_entity_by_normalized_alias(
                workspace_id=workspace_id,
                normalized_alias=normalized,
            ).id
            == front
        )
        typed = uow.knowledge_nodes.find_entity_by_normalized_alias(
            workspace_id=workspace_id,
            normalized_alias=normalized,
            entity_type="feature",
        )
        assert typed is not None
        assert typed.id == behind

        assert (
            uow.knowledge_nodes.find_entity_by_normalized_alias(
                workspace_id=workspace_id,
                normalized_alias=normalized,
                entity_type="없는 type",
            )
            is None
        )


def test_find_entity_candidates_by_similarity(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """이름이 비슷한 active entity만 점수와 함께 돌려준다.

    무관한 노드와 병합된 노드는 후보가 아니다. 병합된 노드를 주면
    이미 흡수된 이름으로 되돌아가는 제안이 생긴다.
    """
    token = uuid.uuid4().hex[:8]
    query = f"autographed baseballs {token}"

    with session_factory() as session:
        target = _entity_node(session, workspace_id, "야구공")
        unrelated = _entity_node(session, workspace_id, "무관")
        live = _entity_node(session, workspace_id, "흡수처")
        merged = _entity_node(session, workspace_id, "병합됨", merged_into=live)
        session.commit()

    with uow_factory() as uow:
        for node_id in (target, merged):
            uow.knowledge_nodes.add_alias(
                workspace_id=workspace_id,
                node_id=node_id,
                alias=f"autographed baseball collection {token}",
                normalized_alias=f"autographed baseball collection {token}",
                source="extractor",
            )
        # 격리 토큰을 질의와 나눠 쓰면 그 토큰의 bigram 겹침만으로
        # 무관 노드가 threshold를 넘길 수 있다. 무관 alias는 질의와
        # 글자를 하나도 공유하지 않는 한글 이름으로 둔다.
        uow.knowledge_nodes.add_alias(
            workspace_id=workspace_id,
            node_id=unrelated,
            alias="분기 매출 보고서",
            normalized_alias="분기 매출 보고서",
            source="extractor",
        )

        found = uow.knowledge_nodes.find_entity_candidates_by_similarity(
            workspace_id=workspace_id,
            normalized_query=query,
            threshold=0.3,
            limit=10,
        )

    by_id = {node.id: score for node, score in found}
    assert target in by_id
    assert by_id[target] > 0.0
    assert merged not in by_id
    assert unrelated not in by_id


def test_find_entity_candidates_by_similarity_honors_threshold(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """threshold보다 낮은 점수는 후보가 아니다."""
    token = uuid.uuid4().hex[:8]

    with session_factory() as session:
        node_id = _entity_node(session, workspace_id, "야구공")
        session.commit()

    with uow_factory() as uow:
        uow.knowledge_nodes.add_alias(
            workspace_id=workspace_id,
            node_id=node_id,
            alias=f"autographed baseball collection {token}",
            normalized_alias=f"autographed baseball collection {token}",
            source="extractor",
        )

        found = uow.knowledge_nodes.find_entity_candidates_by_similarity(
            workspace_id=workspace_id,
            normalized_query=f"autographed baseballs {token}",
            threshold=0.9,
            limit=10,
        )

    assert node_id not in {node.id for node, _ in found}


def test_find_entity_candidates_by_similarity_takes_max_per_node(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """한 노드에 alias가 여럿이면 가장 높은 점수 한 행만 준다.

    alias 수만큼 같은 노드가 반복되면 상위 N 후보가 노드 하나로
    차 버린다.
    """
    token = uuid.uuid4().hex[:8]
    query = f"autographed baseballs {token}"

    with session_factory() as session:
        node_id = _entity_node(session, workspace_id, "야구공")
        session.commit()

    with uow_factory() as uow:
        for alias in (
            f"autographed baseballs {token}",
            f"autographed baseball collection {token}",
        ):
            uow.knowledge_nodes.add_alias(
                workspace_id=workspace_id,
                node_id=node_id,
                alias=alias,
                normalized_alias=alias,
                source="extractor",
            )

        found = uow.knowledge_nodes.find_entity_candidates_by_similarity(
            workspace_id=workspace_id,
            normalized_query=query,
            threshold=0.3,
            limit=10,
        )

    rows = [(node, score) for node, score in found if node.id == node_id]
    assert len(rows) == 1
    assert rows[0][1] == pytest.approx(1.0)


def test_find_entity_candidates_by_similarity_is_ordered(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """점수 내림차순, 동점이면 node id 오름차순으로 준다."""
    token = uuid.uuid4().hex[:8]
    alias = f"autographed baseball collection {token}"

    with session_factory() as session:
        first = _entity_node(session, workspace_id, "A")
        second = _entity_node(session, workspace_id, "B")
        session.commit()

    with uow_factory() as uow:
        for node_id in (first, second):
            uow.knowledge_nodes.add_alias(
                workspace_id=workspace_id,
                node_id=node_id,
                alias=alias,
                normalized_alias=alias,
                source="extractor",
            )

        found = uow.knowledge_nodes.find_entity_candidates_by_similarity(
            workspace_id=workspace_id,
            normalized_query=f"autographed baseballs {token}",
            threshold=0.3,
            limit=10,
        )

    scores = [score for _, score in found]
    assert scores == sorted(scores, reverse=True)
    ours = [node.id for node, _ in found if node.id in {first, second}]
    assert ours == sorted([first, second])


def test_find_entity_candidates_by_similarity_respects_limit(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """limit보다 많은 후보를 돌려주지 않는다."""
    token = uuid.uuid4().hex[:8]

    with session_factory() as session:
        node_ids = [
            _entity_node(session, workspace_id, f"야구공 {index}")
            for index in range(3)
        ]
        session.commit()

    with uow_factory() as uow:
        for node_id in node_ids:
            uow.knowledge_nodes.add_alias(
                workspace_id=workspace_id,
                node_id=node_id,
                alias=f"autographed baseball collection {token}",
                normalized_alias=f"autographed baseball collection {token}",
                source="extractor",
            )

        found = uow.knowledge_nodes.find_entity_candidates_by_similarity(
            workspace_id=workspace_id,
            normalized_query=f"autographed baseballs {token}",
            threshold=0.3,
            limit=2,
        )

    assert len(found) == 2


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


def test_as_of_miss_returns_real_bigm_candidates(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """정확 일치가 없으면 실제 bigm 후보를 동반해 돌려준다.

    후보를 주더라도 subject는 여전히 None이고 claim은 비어 있다 —
    유사도는 제시까지고 확정은 소비자 몫이다.
    """
    token = uuid.uuid4().hex[:8]

    with session_factory() as session:
        node_id = _entity_node(session, workspace_id, "야구공")
        run_id = _extraction_run(session, workspace_id)
        _claim(
            session,
            workspace_id,
            run_id,
            node_id=node_id,
            status="accepted",
            value="A",
        )
        session.commit()

    with uow_factory() as uow:
        uow.knowledge_nodes.add_alias(
            workspace_id=workspace_id,
            node_id=node_id,
            alias=f"autographed baseball collection {token}",
            normalized_alias=f"autographed baseball collection {token}",
            source="extractor",
        )
        uow.commit()

    result = query_claims_as_of(
        workspace_id=workspace_id,
        subject=f"Autographed Baseballs {token}",
        at=T_AUG_1,
        uow=uow_factory(),
    )

    assert result.subject is None
    assert result.claims == ()
    by_id = {item.node_id: item for item in result.similar_candidates}
    assert node_id in by_id
    assert by_id[node_id].display_name == "야구공"
    assert by_id[node_id].entity_type == "feature"
    assert by_id[node_id].score > 0.0


def test_history_miss_returns_real_bigm_candidates(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """history 경로도 같은 fallback을 탄다."""
    token = uuid.uuid4().hex[:8]

    with session_factory() as session:
        node_id = _entity_node(session, workspace_id, "야구공")
        session.commit()

    with uow_factory() as uow:
        uow.knowledge_nodes.add_alias(
            workspace_id=workspace_id,
            node_id=node_id,
            alias=f"autographed baseball collection {token}",
            normalized_alias=f"autographed baseball collection {token}",
            source="extractor",
        )
        uow.commit()

    result = query_claims_history(
        workspace_id=workspace_id,
        subject=f"Autographed Baseballs {token}",
        uow=uow_factory(),
    )

    assert result.subject is None
    assert result.claims == ()
    assert node_id in {item.node_id for item in result.similar_candidates}


def test_exact_match_returns_no_candidates(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """alias 정확 일치로 걸리면 유사 후보를 붙이지 않는다."""
    token = uuid.uuid4().hex[:8]
    alias = f"autographed baseballs {token}"

    with session_factory() as session:
        node_id = _entity_node(session, workspace_id, "야구공")
        neighbor = _entity_node(session, workspace_id, "이웃")
        session.commit()

    with uow_factory() as uow:
        uow.knowledge_nodes.add_alias(
            workspace_id=workspace_id,
            node_id=node_id,
            alias=alias,
            normalized_alias=alias,
            source="extractor",
        )
        uow.knowledge_nodes.add_alias(
            workspace_id=workspace_id,
            node_id=neighbor,
            alias=f"autographed baseball collection {token}",
            normalized_alias=f"autographed baseball collection {token}",
            source="extractor",
        )
        uow.commit()

    result = query_claims_as_of(
        workspace_id=workspace_id,
        subject=f"Autographed Baseballs {token}",
        at=T_AUG_1,
        uow=uow_factory(),
    )

    assert result.subject is not None
    assert result.subject.node_id == node_id
    assert result.similar_candidates == ()


def test_node_read_is_not_hijacked_by_a_shared_alias(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """같은 이름을 가진 다른 노드가 있어도 지목한 노드만 읽는다.

    alias uniqueness는 workspace·node·normalized_alias 조합에만 걸려
    있어 같은 이름이 여러 노드에 살 수 있다. 이름으로 다시 조회하면
    그중 node id가 가장 작은 하나가 나오므로, 유사도가 고른 노드가
    아닌 남의 claim이 답의 근거가 된다. node id 조회는 그 왕복 자체가
    없어야 한다.
    """
    token = uuid.uuid4().hex[:8]
    shared = f"shared name {token}"

    with session_factory() as session:
        first = _entity_node(session, workspace_id, "첫째")
        second = _entity_node(session, workspace_id, "둘째")
        run_id = _extraction_run(session, workspace_id)
        _claim(
            session,
            workspace_id,
            run_id,
            node_id=first,
            status="accepted",
            valid_from=JULY_1,
            value="첫째의 사실",
        )
        _claim(
            session,
            workspace_id,
            run_id,
            node_id=second,
            status="accepted",
            valid_from=JULY_1,
            value="둘째의 사실",
        )
        session.commit()

    with uow_factory() as uow:
        for node_id in (first, second):
            uow.knowledge_nodes.add_alias(
                workspace_id=workspace_id,
                node_id=node_id,
                alias=shared,
                normalized_alias=shared,
                source="extractor",
            )
        uow.commit()

    by_name = query_claims_as_of(
        workspace_id=workspace_id,
        subject=shared,
        at=T_AUG_1,
        uow=uow_factory(),
    )
    loser = second if by_name.subject.node_id == first else first

    by_node = query_claims_of_node(
        workspace_id=workspace_id,
        node_id=loser,
        at=T_AUG_1,
        uow=uow_factory(),
    )
    history = query_claims_of_node_history(
        workspace_id=workspace_id,
        node_id=loser,
        uow=uow_factory(),
    )

    # 이름 조회는 둘 중 하나만 고른다 — 그래서 이름으로 되짚으면 진다.
    assert by_name.subject is not None
    assert by_name.subject.node_id == min(first, second, key=str)
    assert by_node.subject is not None
    assert by_node.subject.node_id == loser
    assert by_node.subject.matched_by == "node_id"
    assert [claim.value for claim in by_node.claims] == [
        "첫째의 사실" if loser == first else "둘째의 사실"
    ]
    assert [claim.value for claim in history.claims] == [
        "첫째의 사실" if loser == first else "둘째의 사실"
    ]


def test_node_read_skips_a_merged_node(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """흡수된 노드를 node id로 지목해도 claim을 읽지 않는다."""
    with session_factory() as session:
        survivor = _entity_node(session, workspace_id, "흡수처")
        merged = _entity_node(
            session, workspace_id, "흡수됨", merged_into=survivor
        )
        run_id = _extraction_run(session, workspace_id)
        _claim(
            session,
            workspace_id,
            run_id,
            node_id=merged,
            status="accepted",
            valid_from=JULY_1,
        )
        session.commit()

    result = query_claims_of_node(
        workspace_id=workspace_id,
        node_id=merged,
        at=T_AUG_1,
        uow=uow_factory(),
    )

    assert result.subject is None
    assert result.claims == ()


def test_timeline_query_collects_by_text_in_time_order(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """키워드가 겹치는 accepted claim을 시간 오름차순으로 모은다.

    statement에만 겹친 claim과 value에만 겹친 claim이 함께 나와야
    한다 — 사건 claim의 키워드가 어느 컬럼에 앉을지는 추출 결과마다
    다르다. 질문 시점 뒤에 발효되는 claim과 rejected는 빠진다.
    """
    keyword = f"workshop{uuid.uuid4().hex[:8]}"

    with session_factory() as session:
        node_id = _entity_node(session, workspace_id, "사용자")
        run_id = _extraction_run(session, workspace_id)

        by_statement = _claim(
            session,
            workspace_id,
            run_id,
            node_id=node_id,
            status="accepted",
            predicate=f"attended_{keyword}",
            value="7월",
            valid_from=JULY_1,
        )
        by_value = _claim(
            session,
            workspace_id,
            run_id,
            node_id=node_id,
            status="accepted",
            predicate="event_note",
            value=f"{keyword} 두 번째 참석",
            statement="사건 기록 하나",
            valid_from=JULY_15,
        )
        future = _claim(
            session,
            workspace_id,
            run_id,
            node_id=node_id,
            status="accepted",
            predicate=f"attended_{keyword}",
            value="8월",
            valid_from=AUG_10,
        )
        rejected = _claim(
            session,
            workspace_id,
            run_id,
            node_id=node_id,
            status="rejected",
            predicate=f"attended_{keyword}",
            value="거절",
            valid_from=JULY_1,
        )
        session.commit()

    result = query_claims_timeline(
        workspace_id=workspace_id,
        query_texts=(keyword,),
        at=T_AUG_1,
        uow=uow_factory(),
    )

    assert result.as_of == T_AUG_1
    assert [claim.claim_id for claim in result.claims] == [
        by_statement,
        by_value,
    ]
    returned = [claim.valid_from for claim in result.claims]
    assert returned == sorted(returned)
    assert all(moment is None or moment <= T_AUG_1 for moment in returned)
    assert future not in {claim.claim_id for claim in result.claims}
    assert rejected not in {claim.claim_id for claim in result.claims}


def test_timeline_query_escapes_like_wildcards(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """키워드의 `%`·`_`가 와일드카드로 새지 않는다.

    escape가 빠지면 "100%" 같은 키워드 하나가 workspace의 claim 전부를
    긁어 온다. 와일드카드로 해석되면 걸릴 claim을 하나 심고 빈 결과를
    확인한다.
    """
    token = uuid.uuid4().hex[:8]

    with session_factory() as session:
        node_id = _entity_node(session, workspace_id, "사용자")
        run_id = _extraction_run(session, workspace_id)
        _claim(
            session,
            workspace_id,
            run_id,
            node_id=node_id,
            status="accepted",
            predicate="event_note",
            value="와일드카드 미끼",
            statement=f"zz-{token}-noXmatch",
            valid_from=JULY_1,
        )
        session.commit()

    result = query_claims_timeline(
        workspace_id=workspace_id,
        query_texts=("zz%no_match",),
        at=T_AUG_1,
        uow=uow_factory(),
    )

    assert result.claims == ()


def test_timeline_query_ignores_blank_keywords(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    workspace_id: int,
) -> None:
    """빈 키워드만 오면 조회하지 않고 빈 결과를 준다.

    빈 문자열로 만든 `%%` 패턴은 모든 행에 걸려, 키워드 없는 질문이
    workspace 전체를 긁어 오는 사고가 된다.
    """
    result = query_claims_timeline(
        workspace_id=workspace_id,
        query_texts=("", "   "),
        at=T_AUG_1,
        uow=uow_factory(),
    )

    assert result.claims == ()


def test_timeline_query_requires_timezone(
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    workspace_id: int,
) -> None:
    """timezone 없는 at은 거부한다."""
    with pytest.raises(ValueError):
        query_claims_timeline(
            workspace_id=workspace_id,
            query_texts=("workshop",),
            at=datetime(2026, 8, 1),
            uow=uow_factory(),
        )


BIGM_INDEX_SQL = """
CREATE INDEX {name} ON knowledge_node_aliases
USING GIN (normalized_alias gin_bigm_ops)
"""
"""서버 초기화가 만드는 `idx_knowledge_node_aliases_bigm`과 같은 인덱스다.

실물은 `CREATE INDEX CONCURRENTLY`라 transaction 안에서 못 만든다.
opclass와 대상 컬럼이 같으면 실행 계획도 같으므로, 테스트는 같은
정의를 non-concurrent로 만들어 트랜잭션과 함께 되돌린다.
"""


def _seed_aliases(connection, workspace_id: int, count: int) -> None:
    """유사 후보 조회가 훑을 alias를 한 번에 채운다."""
    connection.execute(
        text(
            """
            INSERT INTO knowledge_nodes (
                id, workspace_id, node_kind, entity_type,
                canonical_key, display_name, lifecycle_state
            )
            SELECT
                gen_random_uuid(), :ws, 'entity', 'feature',
                'plan:' || i, 'plan alias number ' || i, 'active'
            FROM generate_series(1, :n) AS i
            """
        ),
        {"ws": workspace_id, "n": count},
    )
    connection.execute(
        text(
            """
            INSERT INTO knowledge_node_aliases (
                id, workspace_id, node_id, alias, normalized_alias, source
            )
            SELECT
                gen_random_uuid(), :ws, n.id, n.display_name,
                n.display_name, 'extractor'
            FROM knowledge_nodes n
            WHERE n.workspace_id = :ws
              AND n.canonical_key LIKE 'plan:%'
            """
        ),
        {"ws": workspace_id},
    )


def test_similar_candidate_query_uses_the_bigm_gin_index(
    engine: Engine,
    workspace_id: int,
) -> None:
    """유사 후보 조회가 alias의 bigm GIN 인덱스를 실제로 탄다.

    `=%`가 아니라 함수 집계 술어로 거르면 이 인덱스는 index condition이
    될 수 없어, miss 한 번마다 workspace의 alias 전부에 유사도 함수가
    돈다. 계획을 고정해 두지 않으면 그 형태로 되돌아가도 아무 테스트가
    깨지지 않는다.

    실행 계획은 데이터 크기에 따라 갈리므로 alias를 충분히 넣는다.
    행이 적으면 workspace B-tree가 더 싸서 planner가 그쪽을 고르고,
    그것은 인덱스를 못 타는 것과 다른 이야기다.
    """
    index_name = f"tmp_alias_bigm_{uuid.uuid4().hex[:8]}"
    connection = engine.connect()
    transaction = connection.begin()
    statements: list[tuple[str, object]] = []

    def _record(conn, cursor, statement, parameters, context, many) -> None:
        statements.append((statement, parameters))

    try:
        _seed_aliases(connection, workspace_id, 5000)
        connection.execute(text(BIGM_INDEX_SQL.format(name=index_name)))
        connection.execute(text("ANALYZE knowledge_node_aliases"))
        connection.execute(text("ANALYZE knowledge_nodes"))
        connection.execute(text("SET LOCAL enable_seqscan = off"))

        factory = sessionmaker(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        event.listen(connection, "before_cursor_execute", _record)
        try:
            with KnowledgeMaintenanceUnitOfWork(
                factory, workspace_id=workspace_id
            ) as uow:
                found = uow.knowledge_nodes.find_entity_candidates_by_similarity(
                    workspace_id=workspace_id,
                    normalized_query="plan alias number 4242",
                    threshold=0.1,
                    limit=5,
                )
        finally:
            event.remove(connection, "before_cursor_execute", _record)

        assert [node.display_name for node, _ in found][0] == (
            "plan alias number 4242"
        )

        # 계획을 세울 SQL은 repository가 실제로 보낸 그 문장이어야 한다.
        # 테스트가 SQL을 다시 쓰면 repository가 바뀌어도 계획은 그대로다.
        similarity_sql = [
            item for item in statements if "bigm_similarity" in item[0]
        ]
        assert len(similarity_sql) == 1
        statement, parameters = similarity_sql[0]
        connection.execute(
            text("SELECT set_config('pg_bigm.similarity_limit', '0.1', true)")
        )
        plan = "\n".join(
            row[0]
            for row in connection.exec_driver_sql(
                "EXPLAIN " + statement, parameters
            ).all()
        )
    finally:
        transaction.rollback()
        connection.close()

    assert f"Bitmap Index Scan on {index_name}" in plan
    assert "Index Cond: (normalized_alias =% " in plan


def test_similarity_limit_does_not_leak_out_of_the_transaction(
    engine: Engine,
    workspace_id: int,
) -> None:
    """threshold를 SET LOCAL로 걸어 session에 남기지 않는다.

    `=%`의 판정 기준은 GUC라, 조회가 그 값을 session에 남기면 같은
    connection의 다음 조회가 남의 문턱값으로 돈다. SET LOCAL은
    transaction이 끝나면 되돌아가므로 UnitOfWork 경계가 곧 수명이다.
    """
    connection = engine.connect()
    try:
        with connection.begin():
            before = connection.execute(
                text("SHOW pg_bigm.similarity_limit")
            ).scalar()

        transaction = connection.begin()
        factory = sessionmaker(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        with KnowledgeMaintenanceUnitOfWork(
            factory, workspace_id=workspace_id
        ) as uow:
            uow.knowledge_nodes.find_entity_candidates_by_similarity(
                workspace_id=workspace_id,
                normalized_query="leak probe",
                threshold=0.42,
                limit=5,
            )
            inside = connection.execute(
                text("SHOW pg_bigm.similarity_limit")
            ).scalar()
        transaction.rollback()

        with connection.begin():
            after = connection.execute(
                text("SHOW pg_bigm.similarity_limit")
            ).scalar()
    finally:
        connection.close()

    assert float(inside) == 0.42
    assert after == before
