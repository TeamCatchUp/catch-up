"""벤치 workspace가 카드 정의를 갖춘 채 판정을 끝내는지 확인한다.

문서로 무엇을 만들지는 정의가 정한다. 그런데 문항별 workspace는 러너가
찍어 내는 것이라 정의를 넣어 줄 사람이 없다 — 정의가 없으면 컴파일
단계가 매번 실패 한 건으로 끝나고, 오케스트레이터는 exit code만 보므로
회차 전체가 실패로 기록된다.

그래서 씨앗 넣기와 판정 회차를 실 PostgreSQL에서 함께 확인한다. 추출과
LLM은 부르지 않는다 — 재려는 것은 추출 품질이 아니라 "정의가 갖춰진
workspace에서 판정이 실패 없이 끝나는가"이다.
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
from catchup.db.models import ArtifactDefinition as DefinitionRow
from catchup.db.models import Channel as ChannelRow
from catchup.db.models import KnowledgeClaimCandidate as ClaimRow
from catchup.db.models import KnowledgeExtractionRun as RunRow
from catchup.db.models import KnowledgeNode as NodeRow
from catchup.db.models import KnowledgeOntologySnapshot as SnapshotRow
from catchup.db.models import Workspace
from catchup.evaluation.longmemeval.bench_adjudication import AdjudicationSteps
from catchup.evaluation.longmemeval.bench_adjudication import run_adjudication
from catchup.evaluation.longmemeval.run_bench_adjudication import BENCH_DEFINITION_KIND
from catchup.evaluation.longmemeval.run_bench_adjudication import (
    _adjudicate_contradictions,
)
from catchup.evaluation.longmemeval.run_bench_adjudication import _apply_mutations
from catchup.evaluation.longmemeval.run_bench_adjudication import _approve_artifacts
from catchup.evaluation.longmemeval.run_bench_adjudication import _approve_merges
from catchup.evaluation.longmemeval.run_bench_adjudication import _compile_artifacts
from catchup.evaluation.longmemeval.run_bench_adjudication import _detect_conflicts
from catchup.evaluation.longmemeval.run_bench_adjudication import (
    ensure_bench_definition,
)
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import CONTRACT_ID
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.extraction import EntityTypeEntry
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import PredicateEntry
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
from catchup.knowledge_maintenance.domain.observation import NormalizedObservation
from catchup.knowledge_maintenance.domain.observation import ObservationKind
from catchup.knowledge_maintenance.domain.observation import content_hash
from catchup.knowledge_maintenance.domain.source_version import ChangeKind
from catchup.knowledge_maintenance.domain.source_version import SourceIdentity
from catchup.knowledge_maintenance.domain.source_version import SourceVersion

WORKSPACE_ID = 919_995
"""테스트 전용 번호다. 실제 벤치 대역(910000~)과 겹치지 않게 멀리 둔다."""

ONTOLOGY_VERSION = "2"
ENTITY_TYPE = "person"
NOW = datetime(2026, 8, 12, tzinfo=timezone.utc)

VOCABULARY = ExtractionVocabulary(
    snapshot_id=ONTOLOGY_VERSION,
    entity_type_entries=(
        EntityTypeEntry(
            name=ENTITY_TYPE,
            definition="사람 한 명을 가리킨다",
            identity_scope="standalone",
        ),
        EntityTypeEntry(
            name="organization",
            definition="조직 하나를 가리킨다",
            identity_scope="standalone",
        ),
    ),
    predicate_entries=(
        PredicateEntry(
            name="works_at",
            definition="어디에서 일하는지 나타낸다",
            value_type="text",
        ),
    ),
)


@pytest.fixture(scope="module")
def engine() -> Iterator[Engine]:
    engine = create_engine(settings.sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        pytest.skip("PostgreSQL이 없어 통합 테스트를 건너뛴다.")

    if not inspect(engine).has_table(DefinitionRow.__tablename__):
        engine.dispose()
        pytest.skip("정의 테이블이 없다. alembic upgrade head가 필요하다.")

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


def _observation_node(
    session_factory: Callable[[], Session],
) -> uuid.UUID:
    """claim이 매달릴 관찰과 그 노드를 세우고 노드 id를 돌려준다.

    claim 조회는 추출 실행의 입력 노드를 관찰과 원문 판까지 이어 읽는다.
    그 사슬이 없으면 claim이 한 건도 나오지 않아 카드가 빈다.
    """
    document_id = f"BENCH-{uuid.uuid4().hex[:8]}"
    source_version = SourceVersion(
        id=uuid.uuid4(),
        workspace_id=WORKSPACE_ID,
        source_type="bench-definition-seed",
        source_identity=SourceIdentity(
            entity_type="user_chat",
            scope_id="bench",
            target_id="bench",
            external_document_id=document_id,
        ),
        change_kind=ChangeKind.CREATED,
        source_version_key="1",
        title=None,
        canonical_url=None,
        content='{"detail": {}}',
        content_type="application/json",
        content_hash="a" * 64,
        source_updated_at=NOW,
        observed_at=NOW,
        idempotency_key=f"bench:{document_id}",
        payload_hash="b" * 64,
        metadata={},
        created_at=NOW,
    )
    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        uow.source_versions.add(source_version)
        uow.commit()

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        stored = uow.observations.add(
            workspace_id=WORKSPACE_ID,
            source_version_id=source_version.id,
            observation=NormalizedObservation(
                normalizer_id="bench.normalizer",
                normalizer_version="1",
                observation_kind=ObservationKind.DOCUMENT,
                content="김벤치는 결제팀에서 일한다.",
                content_hash=content_hash("김벤치는 결제팀에서 일한다."),
                source_attributes={},
                metadata_entities=(),
                occurred_at=NOW,
            ),
        )
        node = uow.knowledge_nodes.ensure_for_resource(
            workspace_id=WORKSPACE_ID,
            node_kind=NodeKind.OBSERVATION,
            resource_id=stored.id,
        )
        uow.commit()
        return node.id


@pytest.fixture
def bench_workspace(
    session_factory: Callable[[], Session],
    template_workspace_id: int,
) -> int:
    """문항 workspace 하나를 지식과 어휘까지 갖춰 세운다.

    러너가 찍어 내는 workspace를 그대로 흉내 낸다 — 채널도 정의도 없이
    지식과 어휘 스냅샷만 있는 상태다.
    """
    with session_factory() as session:
        company_id = session.execute(
            select(Workspace.company_id).where(
                Workspace.id == template_workspace_id
            )
        ).scalar_one()
        session.add(
            Workspace(
                id=WORKSPACE_ID,
                name=f"bench-seed-{uuid.uuid4().hex[:8]}",
                company_id=company_id,
            )
        )
        session.commit()

    input_node_id = _observation_node(session_factory)

    with session_factory() as session:
        session.add(
            SnapshotRow(
                id=uuid.uuid4(),
                workspace_id=WORKSPACE_ID,
                ontology_id=CONTRACT_ID,
                version=ONTOLOGY_VERSION,
                predicates=list(VOCABULARY.predicates),
                relation_types=[],
            )
        )
        session.flush()
        run_id = uuid.uuid4()
        session.add(
            RunRow(
                id=run_id,
                workspace_id=WORKSPACE_ID,
                input_node_id=input_node_id,
                provider="test",
                extractor_version="1",
                ontology_id=CONTRACT_ID,
                ontology_version=ONTOLOGY_VERSION,
                status="succeeded",
                started_at=NOW,
            )
        )
        entity_node_id = uuid.uuid4()
        session.add(
            NodeRow(
                id=entity_node_id,
                workspace_id=WORKSPACE_ID,
                node_kind="entity",
                entity_type=ENTITY_TYPE,
                canonical_key=f"test:person:{uuid.uuid4().hex}",
                display_name="김벤치",
                lifecycle_state="active",
            )
        )
        session.flush()
        session.add(
            ClaimRow(
                id=uuid.uuid4(),
                workspace_id=WORKSPACE_ID,
                extraction_run_id=run_id,
                local_key=f"c-{uuid.uuid4().hex}",
                subject_node_id=entity_node_id,
                predicate="works_at",
                value_type="text",
                value="결제팀",
                value_hash=uuid.uuid4().hex + uuid.uuid4().hex,
                statement="works_at=결제팀",
                ontology_id=CONTRACT_ID,
                ontology_version=ONTOLOGY_VERSION,
                extraction_method="llm",
                resolution_status="accepted",
            )
        )
        session.commit()

    return WORKSPACE_ID


def _run_adjudication(
    session_factory: Callable[[], Session],
    workspace_id: int,
):
    """러너가 엮는 그대로 판정 한 회차를 돌린다."""
    uow = KnowledgeMaintenanceUnitOfWork(
        session_factory, workspace_id=workspace_id
    )

    def uow_factory() -> KnowledgeMaintenanceUnitOfWork:
        return KnowledgeMaintenanceUnitOfWork(
            session_factory, workspace_id=workspace_id
        )

    steps = AdjudicationSteps(
        approve_merges=lambda: _approve_merges(uow, workspace_id=workspace_id),
        apply_mutations=lambda: _apply_mutations(
            uow_factory, workspace_id=workspace_id
        ),
        detect_conflicts=lambda: _detect_conflicts(
            uow, workspace_id=workspace_id, vocabulary=VOCABULARY
        ),
        adjudicate_contradictions=lambda: _adjudicate_contradictions(
            uow, workspace_id=workspace_id
        ),
        compile_artifacts=lambda: _compile_artifacts(
            uow, workspace_id=workspace_id, vocabulary=VOCABULARY
        ),
        approve_artifacts=lambda: _approve_artifacts(uow),
    )
    return run_adjudication(steps)


def test_seeded_bench_workspace_finishes_without_failures(
    session_factory: Callable[[], Session],
    bench_workspace: int,
) -> None:
    """씨앗을 넣은 workspace는 실패 없이 카드까지 승인된다."""
    ensure_bench_definition(
        session_factory,
        workspace_id=bench_workspace,
        vocabulary=VOCABULARY,
    )

    counts = _run_adjudication(session_factory, bench_workspace)

    assert counts.failures == 0
    assert counts.artifacts_compiled >= 1
    assert counts.artifacts_approved >= 1


def test_definition_covers_every_entity_type_in_the_vocabulary(
    session_factory: Callable[[], Session],
    bench_workspace: int,
) -> None:
    """정의는 어휘의 entity 종류를 하나도 빠뜨리지 않는다.

    옛 컴파일러는 정의 없이 모든 entity를 문서로 만들었다. 종류를
    골라 넣으면 그만큼 카드가 조용히 사라진다.
    """
    ensure_bench_definition(
        session_factory,
        workspace_id=bench_workspace,
        vocabulary=VOCABULARY,
    )

    with session_factory() as session:
        spec = session.execute(
            select(DefinitionRow.selection_spec).where(
                DefinitionRow.workspace_id == bench_workspace
            )
        ).scalar_one()

    assert spec["entity_filter"]["entity_types"] == [
        entry.name for entry in VOCABULARY.entity_type_entries
    ]
    assert spec["relation_paths"] == []
    assert spec["predicate_sections"] is None


def test_seeding_twice_does_not_duplicate(
    session_factory: Callable[[], Session],
    bench_workspace: int,
) -> None:
    """두 번 넣어도 채널과 정의는 한 벌뿐이다."""
    ensure_bench_definition(
        session_factory,
        workspace_id=bench_workspace,
        vocabulary=VOCABULARY,
    )
    ensure_bench_definition(
        session_factory,
        workspace_id=bench_workspace,
        vocabulary=VOCABULARY,
    )

    with session_factory() as session:
        channels = session.execute(
            select(ChannelRow.id).where(
                ChannelRow.workspace_id == bench_workspace
            )
        ).all()
        definitions = session.execute(
            select(DefinitionRow.id, DefinitionRow.kind).where(
                DefinitionRow.workspace_id == bench_workspace
            )
        ).all()

    assert len(channels) == 1
    assert [kind for _, kind in definitions] == [BENCH_DEFINITION_KIND]
