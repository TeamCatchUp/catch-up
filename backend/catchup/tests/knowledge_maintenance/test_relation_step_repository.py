"""관계 한 걸음 조회를 실 PostgreSQL로 확인한다.

경로 순회는 이 한 걸음을 되풀이해 만들어진다. 방향을 반대로 읽거나,
닫힌 관계를 살려 두거나, 해소되지 않은 끝점을 노드처럼 다루면 그 잘못이
경로 전체로 번져 문서 본문에 실린다. 그래서 방향·생사·해소 세 가지를
실 DB에서 확인한다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator
from datetime import datetime
from datetime import timedelta
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
from catchup.db.models import KnowledgeEntityCandidate
from catchup.db.models import KnowledgeExtractionRun
from catchup.db.models import KnowledgeNode
from catchup.db.models import KnowledgeOntologySnapshot
from catchup.db.models import KnowledgeRelationAssertionCandidate
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.domain.artifact_definition import DIRECTION_ANY
from catchup.knowledge_maintenance.domain.artifact_definition import DIRECTION_IN
from catchup.knowledge_maintenance.domain.artifact_definition import DIRECTION_OUT
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    AssertionResolutionStatus,
)

NOW = datetime(2026, 8, 12, tzinfo=timezone.utc)
RELATION_TYPE = "requested_by"

# 정렬을 확인하려면 식별자를 우연에 맡길 수 없다. 앞자리만 다른 두 값을
# 두고 큰 쪽을 먼저 넣는다.
FIRST_RELATION_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
SECOND_RELATION_ID = uuid.UUID("ffffffff-0000-4000-8000-000000000002")


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    table_name = KnowledgeRelationAssertionCandidate.__tablename__
    if not inspect(engine).has_table(table_name):
        engine.dispose()
        pytest.skip("관계 후보 테이블이 없다. alembic upgrade head가 필요하다.")

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


def _new_workspace(
    session_factory: Callable[[], Session],
    seed_workspace_id: int,
) -> int:
    """이 테스트만 쓰는 빈 workspace를 마련한다.

    기존 workspace에는 다른 테스트나 실제 운영이 남긴 관계가 있을 수
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


class _Graph:
    """관계를 걸 수 있는 최소한의 지식 그래프 한 벌을 들고 있다.

    관계 후보 행은 workspace·추출 실행·노드·entity 후보에 모두 매여
    있다. 테스트마다 그 사슬을 다시 세우면 무엇을 확인하는 테스트인지가
    준비 코드에 묻히므로 한 자리에 모은다.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        workspace_id: int,
    ) -> None:
        self.session_factory = session_factory
        self.workspace_id = workspace_id
        self.node_a = uuid.uuid4()
        self.node_b = uuid.uuid4()
        self.run_id = uuid.uuid4()
        self._seed()

    def _seed(self) -> None:
        input_node_id = uuid.uuid4()
        with self.session_factory() as session:
            session.add(
                KnowledgeOntologySnapshot(
                    id=uuid.uuid4(),
                    workspace_id=self.workspace_id,
                    ontology_id="test-ontology",
                    version="1",
                    predicates=[],
                    relation_types=[RELATION_TYPE],
                )
            )
            session.add(
                KnowledgeNode(
                    id=input_node_id,
                    workspace_id=self.workspace_id,
                    node_kind="observation",
                    resource_type="observation",
                    resource_id=str(uuid.uuid4()),
                )
            )
            for node_id, name in (
                (self.node_a, "노드 A"),
                (self.node_b, "노드 B"),
            ):
                session.add(
                    KnowledgeNode(
                        id=node_id,
                        workspace_id=self.workspace_id,
                        node_kind="entity",
                        entity_type="feature_request",
                        canonical_key=f"key-{node_id}",
                        display_name=name,
                    )
                )
            session.flush()
            session.add(
                KnowledgeExtractionRun(
                    id=self.run_id,
                    workspace_id=self.workspace_id,
                    input_node_id=input_node_id,
                    provider="test",
                    extractor_version="1",
                    ontology_id="test-ontology",
                    ontology_version="1",
                    status="succeeded",
                    started_at=NOW,
                )
            )
            session.commit()

    def add_candidate(self, *, resolved_node_id: uuid.UUID | None) -> uuid.UUID:
        """entity 후보 한 건을 넣고 그 식별자를 돌려준다."""
        candidate_id = uuid.uuid4()
        with self.session_factory() as session:
            session.add(
                KnowledgeEntityCandidate(
                    id=candidate_id,
                    workspace_id=self.workspace_id,
                    extraction_run_id=self.run_id,
                    local_key=f"cand-{candidate_id}",
                    proposed_type="feature_request",
                    proposed_name="후보 이름",
                    extraction_method="llm",
                    resolution_status=(
                        "pending" if resolved_node_id is None else "accepted"
                    ),
                    resolved_node_id=resolved_node_id,
                )
            )
            session.commit()
        return candidate_id

    def add_relation(
        self,
        *,
        relation_id: uuid.UUID | None = None,
        source_node_id: uuid.UUID | None = None,
        source_candidate_id: uuid.UUID | None = None,
        target_node_id: uuid.UUID | None = None,
        target_candidate_id: uuid.UUID | None = None,
        relation_type: str = RELATION_TYPE,
        assertion_text: str | None = "A가 B에게 요청했다",
        valid_to: datetime | None = None,
        resolution_status: str = AssertionResolutionStatus.PENDING.value,
    ) -> uuid.UUID:
        """관계 후보 한 건을 넣고 그 식별자를 돌려준다."""
        relation_id = relation_id or uuid.uuid4()
        with self.session_factory() as session:
            session.add(
                KnowledgeRelationAssertionCandidate(
                    id=relation_id,
                    workspace_id=self.workspace_id,
                    extraction_run_id=self.run_id,
                    local_key=f"rel-{relation_id}",
                    source_node_id=source_node_id,
                    source_entity_candidate_id=source_candidate_id,
                    target_node_id=target_node_id,
                    target_entity_candidate_id=target_candidate_id,
                    relation_type=relation_type,
                    assertion_text=assertion_text,
                    valid_to=valid_to,
                    extraction_method="llm",
                    resolution_status=resolution_status,
                )
            )
            session.commit()
        return relation_id


@pytest.fixture
def graph(
    session_factory: Callable[[], Session],
    seed_workspace_id: int,
) -> _Graph:
    workspace_id = _new_workspace(session_factory, seed_workspace_id)
    return _Graph(session_factory, workspace_id)


@pytest.fixture
def uow_factory(
    session_factory: Callable[[], Session],
    graph: _Graph,
) -> Callable[[], KnowledgeMaintenanceUnitOfWork]:
    return lambda: KnowledgeMaintenanceUnitOfWork(
        session_factory, workspace_id=graph.workspace_id
    )


def test_out_follows_source_side(
    graph: _Graph,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """out은 출발 쪽이 주어진 노드인 간선을 고른다."""
    relation_id = graph.add_relation(
        source_node_id=graph.node_a, target_node_id=graph.node_b
    )

    with uow_factory() as uow:
        edges = uow.relations.find_edges(
            node_ids=[graph.node_a],
            relation_type=RELATION_TYPE,
            direction=DIRECTION_OUT,
            now=NOW,
        )

    assert [
        (edge.id, edge.source_node_id, edge.target_node_id, edge.assertion_text)
        for edge in edges
    ] == [(relation_id, graph.node_a, graph.node_b, "A가 B에게 요청했다")]


def test_out_does_not_follow_target_side(
    graph: _Graph,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """out으로 물으면 도착 쪽에 걸린 간선은 나오지 않는다.

    방향이 뒤집히면 문서가 "A가 요청했다"를 "A에게 요청했다"로 적는다.
    """
    graph.add_relation(
        source_node_id=graph.node_a, target_node_id=graph.node_b
    )

    with uow_factory() as uow:
        edges = uow.relations.find_edges(
            node_ids=[graph.node_b],
            relation_type=RELATION_TYPE,
            direction=DIRECTION_OUT,
            now=NOW,
        )

    assert edges == []


def test_in_follows_target_side(
    graph: _Graph,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """in은 도착 쪽이 주어진 노드인 간선을 고른다."""
    graph.add_relation(
        source_node_id=graph.node_a, target_node_id=graph.node_b
    )

    with uow_factory() as uow:
        edges = uow.relations.find_edges(
            node_ids=[graph.node_b],
            relation_type=RELATION_TYPE,
            direction=DIRECTION_IN,
            now=NOW,
        )

    assert len(edges) == 1
    assert edges[0].source_node_id == graph.node_a


def test_any_takes_both_sides(
    graph: _Graph,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """any는 양쪽 방향의 간선을 합쳐 돌려준다."""
    outgoing = graph.add_relation(
        source_node_id=graph.node_a, target_node_id=graph.node_b
    )
    incoming = graph.add_relation(
        source_node_id=graph.node_b, target_node_id=graph.node_a
    )

    with uow_factory() as uow:
        edges = uow.relations.find_edges(
            node_ids=[graph.node_a],
            relation_type=RELATION_TYPE,
            direction=DIRECTION_ANY,
            now=NOW,
        )

    assert {edge.id for edge in edges} == {outgoing, incoming}


def test_closed_relation_excluded(
    graph: _Graph,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """기준 시각에 이미 닫힌 관계는 나오지 않는다."""
    graph.add_relation(
        source_node_id=graph.node_a,
        target_node_id=graph.node_b,
        valid_to=NOW - timedelta(days=1),
    )

    with uow_factory() as uow:
        edges = uow.relations.find_edges(
            node_ids=[graph.node_a],
            relation_type=RELATION_TYPE,
            direction=DIRECTION_OUT,
            now=NOW,
        )

    assert edges == []


def test_relation_closing_later_is_still_live(
    graph: _Graph,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """기준 시각 뒤에 닫히는 관계는 아직 살아 있다.

    구간이 반개구간이라 valid_to가 기준 시각과 같으면 닫힌 것이고,
    더 뒤면 살아 있다. 경계를 잘못 잡으면 방금 닫힌 관계가 하루 더
    문서에 남는다.
    """
    relation_id = graph.add_relation(
        source_node_id=graph.node_a,
        target_node_id=graph.node_b,
        valid_to=NOW + timedelta(days=1),
    )

    with uow_factory() as uow:
        edges = uow.relations.find_edges(
            node_ids=[graph.node_a],
            relation_type=RELATION_TYPE,
            direction=DIRECTION_OUT,
            now=NOW,
        )

    assert [edge.id for edge in edges] == [relation_id]


def test_unresolved_endpoint_excluded(
    graph: _Graph,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """끝점이 아직 해소되지 않은 후보면 간선이 나오지 않는다.

    어느 노드를 가리키는지 정해지지 않은 끝점은 순회의 다음 출발점이
    될 수 없다.
    """
    candidate_id = graph.add_candidate(resolved_node_id=None)
    graph.add_relation(
        source_node_id=graph.node_a, target_candidate_id=candidate_id
    )

    with uow_factory() as uow:
        edges = uow.relations.find_edges(
            node_ids=[graph.node_a],
            relation_type=RELATION_TYPE,
            direction=DIRECTION_OUT,
            now=NOW,
        )

    assert edges == []


def test_resolved_candidate_endpoint_becomes_node_id(
    graph: _Graph,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """해소된 후보 끝점은 canonical 노드 식별자로 바뀌어 나온다."""
    candidate_id = graph.add_candidate(resolved_node_id=graph.node_b)
    graph.add_relation(
        source_node_id=graph.node_a, target_candidate_id=candidate_id
    )

    with uow_factory() as uow:
        edges = uow.relations.find_edges(
            node_ids=[graph.node_a],
            relation_type=RELATION_TYPE,
            direction=DIRECTION_OUT,
            now=NOW,
        )

    assert [edge.target_node_id for edge in edges] == [graph.node_b]


def test_resolved_candidate_endpoint_matches_node_ids(
    graph: _Graph,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """출발 쪽이 후보라도 해소된 노드로 node_ids와 맞춘다.

    주어진 노드를 원본 칸으로만 맞추면 후보를 거쳐 들어온 간선이
    통째로 빠져 경로가 한 걸음 앞에서 끊긴다.
    """
    candidate_id = graph.add_candidate(resolved_node_id=graph.node_a)
    relation_id = graph.add_relation(
        source_candidate_id=candidate_id, target_node_id=graph.node_b
    )

    with uow_factory() as uow:
        edges = uow.relations.find_edges(
            node_ids=[graph.node_a],
            relation_type=RELATION_TYPE,
            direction=DIRECTION_OUT,
            now=NOW,
        )

    assert [(edge.id, edge.source_node_id) for edge in edges] == [
        (relation_id, graph.node_a)
    ]


def test_endpoint_display_names_come_back(
    graph: _Graph,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """양 끝점의 표시 이름이 간선과 함께 나온다.

    순회는 이 이름으로 이웃을 세우고 상한을 자른다. 이름이 비어 오면
    남는 이웃이 식별자로 정해져 같은 지식에서 다른 문서가 나온다.
    """
    graph.add_relation(
        source_node_id=graph.node_a, target_node_id=graph.node_b
    )

    with uow_factory() as uow:
        edges = uow.relations.find_edges(
            node_ids=[graph.node_a],
            relation_type=RELATION_TYPE,
            direction=DIRECTION_OUT,
            now=NOW,
        )

    assert [
        (edge.source_display_name, edge.target_display_name) for edge in edges
    ] == [("노드 A", "노드 B")]


def test_display_name_follows_the_resolved_endpoint(
    graph: _Graph,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """후보를 거쳐 들어온 끝점도 해소된 노드의 이름을 단다.

    후보의 제안 이름을 그대로 쓰면 같은 노드가 걸음마다 다른 이름으로
    보여 정렬이 흔들린다.
    """
    candidate_id = graph.add_candidate(resolved_node_id=graph.node_b)
    graph.add_relation(
        source_node_id=graph.node_a, target_candidate_id=candidate_id
    )

    with uow_factory() as uow:
        edges = uow.relations.find_edges(
            node_ids=[graph.node_a],
            relation_type=RELATION_TYPE,
            direction=DIRECTION_OUT,
            now=NOW,
        )

    assert [
        (edge.target_node_id, edge.target_display_name) for edge in edges
    ] == [(graph.node_b, "노드 B")]


def test_rejected_relation_excluded(
    graph: _Graph,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """사람이 반려한 관계는 나오지 않는다.

    반려는 "참이었던 적이 없다"는 판정이라, 그 간선을 따라가면 없던
    관계가 문서에 실린다.
    """
    graph.add_relation(
        source_node_id=graph.node_a,
        target_node_id=graph.node_b,
        resolution_status=AssertionResolutionStatus.REJECTED.value,
    )

    with uow_factory() as uow:
        edges = uow.relations.find_edges(
            node_ids=[graph.node_a],
            relation_type=RELATION_TYPE,
            direction=DIRECTION_OUT,
            now=NOW,
        )

    assert edges == []


def test_superseded_relation_excluded(
    graph: _Graph,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """재추출이 대체한 구 배치의 관계는 나오지 않는다.

    새 배치와 함께 실리면 같은 관계가 두 번 문서에 들어간다.
    """
    graph.add_relation(
        source_node_id=graph.node_a,
        target_node_id=graph.node_b,
        resolution_status=AssertionResolutionStatus.SUPERSEDED.value,
    )

    with uow_factory() as uow:
        edges = uow.relations.find_edges(
            node_ids=[graph.node_a],
            relation_type=RELATION_TYPE,
            direction=DIRECTION_OUT,
            now=NOW,
        )

    assert edges == []


def test_pending_and_accepted_relations_included(
    graph: _Graph,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """아직 해소 전인 관계와 승인된 관계는 그대로 나온다.

    상태로 거르는 것은 반려와 대체 둘뿐이다. 이 둘 말고도 걸러 내면
    아직 판정되지 않은 관계까지 조용히 빠져 경로가 끊긴다.
    """
    pending = graph.add_relation(
        relation_id=FIRST_RELATION_ID,
        source_node_id=graph.node_a,
        target_node_id=graph.node_b,
        resolution_status=AssertionResolutionStatus.PENDING.value,
    )
    accepted = graph.add_relation(
        relation_id=SECOND_RELATION_ID,
        source_node_id=graph.node_a,
        target_node_id=graph.node_b,
        resolution_status=AssertionResolutionStatus.ACCEPTED.value,
    )

    with uow_factory() as uow:
        edges = uow.relations.find_edges(
            node_ids=[graph.node_a],
            relation_type=RELATION_TYPE,
            direction=DIRECTION_OUT,
            now=NOW,
        )

    assert [edge.id for edge in edges] == [pending, accepted]


def test_other_relation_type_excluded(
    graph: _Graph,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """관계 종류는 정확히 일치하는 것만 나온다."""
    graph.add_relation(
        source_node_id=graph.node_a,
        target_node_id=graph.node_b,
        relation_type="mentions",
    )

    with uow_factory() as uow:
        edges = uow.relations.find_edges(
            node_ids=[graph.node_a],
            relation_type=RELATION_TYPE,
            direction=DIRECTION_OUT,
            now=NOW,
        )

    assert edges == []


def test_edges_are_ordered_by_id(
    graph: _Graph,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """간선은 관계 식별자 사전순으로 나오고 두 번 물어도 같다."""
    graph.add_relation(
        relation_id=SECOND_RELATION_ID,
        source_node_id=graph.node_a,
        target_node_id=graph.node_b,
    )
    graph.add_relation(
        relation_id=FIRST_RELATION_ID,
        source_node_id=graph.node_a,
        target_node_id=graph.node_b,
    )

    with uow_factory() as uow:
        first = uow.relations.find_edges(
            node_ids=[graph.node_a],
            relation_type=RELATION_TYPE,
            direction=DIRECTION_OUT,
            now=NOW,
        )
        second = uow.relations.find_edges(
            node_ids=[graph.node_a],
            relation_type=RELATION_TYPE,
            direction=DIRECTION_OUT,
            now=NOW,
        )

    assert [edge.id for edge in first] == [
        FIRST_RELATION_ID,
        SECOND_RELATION_ID,
    ]
    assert first == second


def test_empty_node_ids_returns_nothing(
    graph: _Graph,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """출발 노드가 하나도 없으면 간선도 없다."""
    graph.add_relation(
        source_node_id=graph.node_a, target_node_id=graph.node_b
    )

    with uow_factory() as uow:
        edges = uow.relations.find_edges(
            node_ids=[],
            relation_type=RELATION_TYPE,
            direction=DIRECTION_OUT,
            now=NOW,
        )

    assert edges == []


def test_other_workspace_relation_excluded(
    session_factory: Callable[[], Session],
    seed_workspace_id: int,
    graph: _Graph,
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """다른 workspace의 관계는 보이지 않는다."""
    foreign_workspace_id = _new_workspace(session_factory, seed_workspace_id)
    foreign = _Graph(session_factory, foreign_workspace_id)
    foreign.add_relation(
        source_node_id=foreign.node_a, target_node_id=foreign.node_b
    )
    own = graph.add_relation(
        source_node_id=graph.node_a, target_node_id=graph.node_b
    )

    with uow_factory() as uow:
        edges = uow.relations.find_edges(
            node_ids=[graph.node_a, foreign.node_a],
            relation_type=RELATION_TYPE,
            direction=DIRECTION_OUT,
            now=NOW,
        )

    assert [edge.id for edge in edges] == [own]
