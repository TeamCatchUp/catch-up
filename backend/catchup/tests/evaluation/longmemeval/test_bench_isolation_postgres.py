"""manifest 격리가 실 PostgreSQL 조회까지 이어지는지 확인한다.

오케스트레이터가 workspace마다 지식을 만들어 두면, QA는 문항마다 자기
workspace만 읽어야 한다. 한 칸이라도 어긋나면 abstention 문항이 남의
기억으로 답하고 점수만 오른다 — 오류는 어디에도 나지 않는다. 그래서
"각자 자기 claim만 본다"를 실 DB에서 못 박는다.

지식은 repository로 직접 넣는다. 추출과 판정은 LLM에 달려 있고, 이
테스트가 재려는 것은 추출 품질이 아니라 조회의 격리다. LLM은 부르지
않는다.
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
from catchup.evaluation.longmemeval.run_ingestion import ensure_workspace
from catchup.evaluation.longmemeval.run_qa import SHARED_WORKSPACE_EVENT
from catchup.evaluation.longmemeval.run_qa import manifest_lookup_for
from catchup.evaluation.longmemeval.workspace_manifest import WorkspaceAssignment
from catchup.evaluation.longmemeval.workspace_manifest import resolve_workspace_for
from catchup.evaluation.longmemeval.workspace_manifest import workspace_name
from catchup.evaluation.longmemeval.workspace_manifest import write_manifest
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.domain.entity_resolution import normalize_name

QUESTION_A = "bench-iso-a"
QUESTION_B = "bench-iso-b"
WORKSPACE_A = 919_997
WORKSPACE_B = 919_996
"""테스트 전용 번호다. 실제 벤치 대역(910000~)과 겹치지 않게 멀리 둔다."""

ASKED_AT = datetime(2026, 8, 1, tzinfo=timezone.utc)


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
def template_workspace_id(engine: Engine) -> int:
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


def _accepted_claim(
    session_factory: Callable[[], Session],
    *,
    workspace_id: int,
    subject: str,
    value: str,
) -> None:
    """어느 workspace에 accepted claim 하나를 심는다.

    조회는 canonical key 아니면 정규화 alias로만 대상을 찾으므로 alias를
    함께 남긴다. 두 workspace에 같은 이름을 쓰는 것이 핵심이다 — 이름이
    다르면 격리가 아니라 이름 덕에 안 섞이는 것이 된다.
    """
    with session_factory() as session:
        run_id = _extraction_run(session, workspace_id)
        node = NodeRow(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            node_kind="entity",
            entity_type="person",
            canonical_key=f"test:person:{uuid.uuid4().hex}",
            display_name=subject,
        )
        session.add(node)
        session.flush()
        session.add(
            ClaimRow(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                extraction_run_id=run_id,
                local_key=f"c-{uuid.uuid4().hex}",
                subject_node_id=node.id,
                predicate="works_at",
                value_type="string",
                value=value,
                value_hash=uuid.uuid4().hex + uuid.uuid4().hex,
                statement=f"works_at={value}",
                ontology_id="test",
                ontology_version="1",
                extraction_method="llm",
                resolution_status="accepted",
            )
        )
        session.commit()
        node_id = node.id

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        uow.knowledge_nodes.add_alias(
            workspace_id=workspace_id,
            node_id=node_id,
            alias=subject,
            normalized_alias=normalize_name(subject),
            source="human",
        )
        uow.commit()


def test_each_question_reads_only_its_own_workspace(
    tmp_path,
    session_factory: Callable[[], Session],
    template_workspace_id: int,
) -> None:
    """manifest를 따라간 조회가 자기 workspace의 claim만 본다."""
    subject = f"벤치 격리 대상 {uuid.uuid4().hex}"

    with session_factory() as session:
        for workspace_id, question_id in (
            (WORKSPACE_A, QUESTION_A),
            (WORKSPACE_B, QUESTION_B),
        ):
            ensure_workspace(
                session,
                workspace_id=workspace_id,
                name=workspace_name(question_id),
                template_workspace_id=template_workspace_id,
            )

    _accepted_claim(
        session_factory,
        workspace_id=WORKSPACE_A,
        subject=subject,
        value="A사",
    )
    _accepted_claim(
        session_factory,
        workspace_id=WORKSPACE_B,
        subject=subject,
        value="B사",
    )

    manifest = tmp_path / "workspace_manifest.json"
    write_manifest(
        manifest,
        (
            WorkspaceAssignment(
                question_id=QUESTION_A,
                workspace_id=WORKSPACE_A,
                session_ids=(),
            ),
            WorkspaceAssignment(
                question_id=QUESTION_B,
                workspace_id=WORKSPACE_B,
                session_ids=(),
            ),
        ),
    )

    workspace_for = resolve_workspace_for(
        manifest,
        (QUESTION_A, QUESTION_B),
        event=SHARED_WORKSPACE_EVENT,
    )
    assert workspace_for == {
        QUESTION_A: WORKSPACE_A,
        QUESTION_B: WORKSPACE_B,
    }

    lookup_for = manifest_lookup_for(
        session_factory,
        workspace_for=workspace_for,
    )

    values: dict[str, list[str]] = {}
    for question_id in (QUESTION_A, QUESTION_B):
        lookup = lookup_for(_stub_question(question_id))
        found = lookup.as_of(subject, ASKED_AT)
        values[question_id] = [claim.value for claim in found.claims]

    assert values[QUESTION_A] == ["A사"]
    assert values[QUESTION_B] == ["B사"]


class _StubQuestion:
    """조회 경로가 보는 것은 question_id 하나뿐이라 그것만 담는다."""

    def __init__(self, question_id: str) -> None:
        self.question_id = question_id


def _stub_question(question_id: str) -> _StubQuestion:
    return _StubQuestion(question_id)
