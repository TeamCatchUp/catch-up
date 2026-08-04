"""유사 후보 되짚기를 실 PostgreSQL로 확인한다.

되짚기가 무엇을 근거로 싣는지는 파이썬이 아니라 alias 조회 규칙에
달려 있다. 같은 정규화 alias가 여러 노드에 걸릴 수 있다는 사실은 DB
제약이 허용하는 것이고, fake는 그 허용을 흉내 내지 않으면 조용히
통과시킨다. 그래서 노드 둘에 같은 이름을 실제로 달아 본다.
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
from catchup.db.models import KnowledgeExtractionRun as RunRow
from catchup.db.models import KnowledgeNode as NodeRow
from catchup.db.models import KnowledgeOntologySnapshot as SnapshotRow
from catchup.db.models import Workspace
from catchup.evaluation.longmemeval.dataset import OracleQuestion
from catchup.evaluation.longmemeval.qa_service import AnswerResult
from catchup.evaluation.longmemeval.qa_service import SubjectResult
from catchup.evaluation.longmemeval.qa_service import run_question
from catchup.evaluation.longmemeval.run_qa import postgres_lookup
from catchup.evaluation.longmemeval.usage import UsageTotals
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.services.query_knowledge_as_of import (
    query_claims_as_of,
)

QUESTION_DATE = datetime(2026, 8, 1, tzinfo=timezone.utc)
VALID_FROM = datetime(2026, 7, 1, tzinfo=timezone.utc)

RIGHT_ANSWER = "Right Company"
WRONG_ANSWER = "Wrong Company"


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


def _question() -> OracleQuestion:
    """되짚기를 부르는 문항 하나를 만든다."""
    return OracleQuestion(
        question_id="q-similar",
        question_type="knowledge-update",
        question="Where does she work now?",
        answer=RIGHT_ANSWER,
        question_date=QUESTION_DATE,
        sessions=(),
        answer_session_ids=frozenset(),
    )


def _ordered_node_ids() -> tuple[uuid.UUID, uuid.UUID]:
    """node id가 작은 것과 큰 것을 순서대로 만든다.

    alias 정확 일치는 같은 이름이 여럿이면 node id가 가장 작은 하나를
    고른다. 이름 되짚기가 지는 상황을 만들려면 이름이 걸리는 쪽이
    작은 id여야 하므로 무작위에 맡기지 않는다.
    """
    hexes = sorted(uuid.uuid4().hex for _ in range(2))
    return uuid.UUID(hexes[0]), uuid.UUID(hexes[1])


_SYLLABLES = "가나다라마바사아자차카타파하거너더러머버서어저처커터퍼허"


def _hangul_name() -> str:
    """라틴 문자와 bigram이 겹치지 않는 고유한 이름을 만든다.

    실 DB에는 다른 실행이 남긴 alias가 있어 고정 문자열을 쓰면 남의
    노드를 잡는다. 그렇다고 16진수 토큰을 붙이면 질문에 쓴 토큰과
    bigram이 우연히 겹쳐 유사도가 문턱값을 넘을 수 있다.
    """
    return "".join(
        _SYLLABLES[byte % len(_SYLLABLES)] for byte in uuid.uuid4().bytes[:10]
    )


def _entity_node(
    session: Session,
    workspace_id: int,
    *,
    node_id: uuid.UUID,
    display_name: str,
) -> None:
    """지정한 id로 active entity 노드를 만든다."""
    session.add(
        NodeRow(
            id=node_id,
            workspace_id=workspace_id,
            node_kind="entity",
            entity_type="person",
            canonical_key=f"test:person:{node_id.hex}",
            display_name=display_name,
            lifecycle_state="active",
        )
    )
    session.flush()


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
    node_id: uuid.UUID,
    value: str,
) -> None:
    """지금도 유효한 accepted claim 하나를 만든다."""
    session.add(
        ClaimRow(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            extraction_run_id=run_id,
            local_key=f"c-{uuid.uuid4().hex}",
            subject_node_id=node_id,
            predicate="employer",
            value_type="string",
            value=value,
            value_hash=uuid.uuid4().hex + uuid.uuid4().hex,
            statement=f"employer={value}",
            ontology_id="test",
            ontology_version="1",
            extraction_method="llm",
            resolution_status="accepted",
            valid_from=VALID_FROM,
            valid_to=None,
        )
    )
    session.flush()


class _RecordingAnswer:
    """답변 컨텍스트를 그대로 받아 두는 fake 답변기다."""

    def __init__(self) -> None:
        self.contexts: list[str] = []

    def __call__(
        self,
        *,
        question: str,
        question_date: datetime,
        claims_context: str,
    ) -> AnswerResult:
        self.contexts.append(claims_context)
        return AnswerResult(answer=RIGHT_ANSWER, usage=UsageTotals(calls=1))


def test_fallback_loads_only_the_top_candidate_not_its_namesake(
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """되짚기는 유사도 1위 노드의 claim만 싣는다.

    1위 노드의 이름을 다른 노드도 alias로 갖고 있으면, 그 이름으로
    다시 조회하는 순간 node id가 작은 쪽이 답으로 온다. 그때 컨텍스트에
    실리는 것은 유사도가 고른 사실이 아니라 이름만 같은 남의 사실이다.
    """
    token = uuid.uuid4().hex[:8]
    # 공유 이름은 질문과 bigram이 하나도 겹치지 않아야 한다. 겹치면
    # 이름만 가진 노드까지 유사 후보가 되어, 되짚기가 그 노드를 읽은
    # 것이 이름 왕복 탓인지 정상 후보 탓인지 구별할 수 없다.
    shared = _hangul_name()
    near = f"alice kim {token}"
    asked = f"alice kimm {token}"

    namesake_id, winner_id = _ordered_node_ids()

    with session_factory() as session:
        # 이름이 걸리는 쪽(namesake)이 더 작은 id다. 이름으로 되짚으면
        # 유사도 1위가 아니라 이 노드가 나온다.
        _entity_node(
            session,
            workspace_id,
            node_id=namesake_id,
            display_name=_hangul_name(),
        )
        _entity_node(
            session,
            workspace_id,
            node_id=winner_id,
            display_name=shared,
        )
        run_id = _extraction_run(session, workspace_id)
        _claim(
            session,
            workspace_id,
            run_id,
            node_id=namesake_id,
            value=WRONG_ANSWER,
        )
        _claim(
            session,
            workspace_id,
            run_id,
            node_id=winner_id,
            value=RIGHT_ANSWER,
        )
        session.commit()

    uow = KnowledgeMaintenanceUnitOfWork(
        session_factory,
        workspace_id=workspace_id,
    )
    with uow:
        for node_id in (namesake_id, winner_id):
            uow.knowledge_nodes.add_alias(
                workspace_id=workspace_id,
                node_id=node_id,
                alias=shared,
                normalized_alias=shared,
                source="extractor",
            )
        # 질문에 가까운 alias는 1위 노드에만 있다. 유사도는 이것으로
        # 갈리고, 이름 되짚기는 이것을 보지 못한다.
        uow.knowledge_nodes.add_alias(
            workspace_id=workspace_id,
            node_id=winner_id,
            alias=near,
            normalized_alias=near,
            source="extractor",
        )
        uow.commit()

    # 함정이 실제로 놓였는지부터 확인한다. 1위 후보의 이름으로 다시
    # 조회하면 1위가 아니라 id가 작은 동명 노드가 나오고, 그 노드의
    # 사실은 질문과 무관하다. 이 단정이 깨지면 아래 검증은 아무것도
    # 막지 못한 채 통과한다.
    by_name = query_claims_as_of(
        workspace_id=workspace_id,
        subject=shared,
        at=QUESTION_DATE,
        uow=KnowledgeMaintenanceUnitOfWork(
            session_factory,
            workspace_id=workspace_id,
        ),
    )
    assert by_name.subject is not None
    assert by_name.subject.node_id == namesake_id
    assert [claim.value for claim in by_name.claims] == [WRONG_ANSWER]

    answer = _RecordingAnswer()
    outcome = run_question(
        _question(),
        lookup=postgres_lookup(session_factory, workspace_id=workspace_id),
        extract_subjects=lambda question: SubjectResult(
            subjects=(asked,),
            usage=UsageTotals(calls=1),
        ),
        answer=answer,
    )

    # 실 DB에는 다른 실행이 남긴 alias가 있어 후보 목록이 이 둘로
    # 닫히지 않는다. 중요한 것은 1위가 들어오고 동명 노드가 빠지는
    # 것뿐이라, 목록 전체를 고정하지 않는다.
    traced = [item.node_id for item in outcome.similarity_candidates]
    assert outcome.similarity_used is True
    assert winner_id in traced
    assert namesake_id not in traced
    assert RIGHT_ANSWER in outcome.claims_context
    assert WRONG_ANSWER not in outcome.claims_context
    assert answer.contexts == [outcome.claims_context]


def test_lookup_with_similarity_off_asks_the_database_for_no_candidates(
    session_factory: Callable[[], Session],
    workspace_id: int,
) -> None:
    """러너가 되짚기를 끄면 유사 후보 조회가 DB까지 가지 않는다.

    스위치를 QA 쪽에만 두면 후보 SQL은 그대로 돈다. 답변 점수는 같아도
    elapsed time과 DB 부하 기준선이 "되짚기 없는 실행"이 아니게 되어,
    되짚기의 비용을 그 기준선과 비교할 수 없다.
    """
    missing = f"absent subject {uuid.uuid4().hex}"

    on = postgres_lookup(session_factory, workspace_id=workspace_id)
    off = postgres_lookup(
        session_factory,
        workspace_id=workspace_id,
        include_similar=False,
    )

    with session_factory() as session:
        node_id = uuid.uuid4()
        _entity_node(
            session,
            workspace_id,
            node_id=node_id,
            display_name=missing.replace("absent", "present"),
        )
        session.commit()

    uow = KnowledgeMaintenanceUnitOfWork(
        session_factory,
        workspace_id=workspace_id,
    )
    with uow:
        uow.knowledge_nodes.add_alias(
            workspace_id=workspace_id,
            node_id=node_id,
            alias=missing.replace("absent", "present"),
            normalized_alias=missing.replace("absent", "present"),
            source="extractor",
        )
        uow.commit()

    assert on.as_of(missing, QUESTION_DATE).similar_candidates != ()
    assert on.history(missing).similar_candidates != ()
    assert off.as_of(missing, QUESTION_DATE).similar_candidates == ()
    assert off.history(missing).similar_candidates == ()
