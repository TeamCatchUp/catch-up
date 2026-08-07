from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from decimal import Decimal

import pytest
from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import func
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.db.models import KnowledgeCandidateEvidenceLink as EvidenceLinkRow
from catchup.db.models import KnowledgeClaimCandidate as ClaimCandidateRow
from catchup.db.models import KnowledgeEntityCandidate as EntityCandidateRow
from catchup.db.models import KnowledgeExtractionRun as ExtractionRunRow
from catchup.db.models import KnowledgeRelationAssertionCandidate as RelationRow
from catchup.db.models import Workspace
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.extraction import ClaimCandidateDraft
from catchup.knowledge_maintenance.contracts.extraction import EntityCandidateDraft
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import KnowledgeCandidateBatch
from catchup.knowledge_maintenance.contracts.extraction import PredicateEntry
from catchup.knowledge_maintenance.contracts.extraction import (
    RelationAssertionCandidateDraft,
)
from catchup.knowledge_maintenance.contracts.extraction import RelationTypeEntry
from catchup.knowledge_maintenance.contracts.vocabulary_convergence import (
    SynonymAbsorption,
)
from catchup.knowledge_maintenance.domain.evidence import Locator
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    EntityResolutionStatus,
)
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionMethod
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionRunSpec
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
from catchup.knowledge_maintenance.domain.observation import MetadataEntity
from catchup.knowledge_maintenance.domain.observation import NormalizedObservation
from catchup.knowledge_maintenance.domain.observation import ObservationKind
from catchup.knowledge_maintenance.domain.observation import StoredObservation
from catchup.knowledge_maintenance.domain.observation import content_hash
from catchup.knowledge_maintenance.domain.source_version import ChangeKind
from catchup.knowledge_maintenance.domain.source_version import SourceIdentity
from catchup.knowledge_maintenance.domain.source_version import SourceVersion
from catchup.knowledge_maintenance.ports.ontology import OntologySnapshotConflict
from catchup.knowledge_maintenance.services.converge_vocabulary import (
    ConvergenceGuardResult,
)
from catchup.knowledge_maintenance.services.converge_vocabulary import GuardRejection
from catchup.knowledge_maintenance.services.converge_vocabulary import (
    publish_converged_vocabulary,
)
from catchup.knowledge_maintenance.services.store_knowledge_candidates import (
    ObservationNodeMissing,
)
from catchup.knowledge_maintenance.services.store_knowledge_candidates import (
    record_failed_extraction,
)
from catchup.knowledge_maintenance.services.store_knowledge_candidates import (
    store_knowledge_candidates,
)

NOW = datetime(2026, 7, 28, 9, 0, tzinfo=timezone.utc)
SOURCE_TYPE = "test-knowledge-maintenance"
NORMALIZED_CONTENT = "고객: 결제 기능은 언제 나오나요?\n상담원: 9월 예정입니다."

SPEC = ExtractionRunSpec(
    provider="aws_bedrock",
    extractor_version="catchup.knowledge_candidates/0",
    ontology_id="catchup.knowledge_candidates",
    vocabulary=ExtractionVocabulary(
        snapshot_id="test-round-1",
        predicates=("release_month",),
        relation_types=("depends_on", "asked_about"),
    ),
    model="claude-test",
    prompt_version="extract_knowledge_candidates/1",
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

    if not inspect(engine).has_table(ExtractionRunRow.__tablename__):
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


def _observation(**overrides: object) -> NormalizedObservation:
    values: dict[str, object] = {
        "normalizer_id": "test.normalizer",
        "normalizer_version": "1",
        "observation_kind": ObservationKind.DOCUMENT,
        "content": NORMALIZED_CONTENT,
        "content_hash": content_hash(NORMALIZED_CONTENT),
        "source_attributes": {"state": "closed"},
        "metadata_entities": (
            MetadataEntity(
                entity_type="channel_talk_user",
                external_key="user-abc",
                display_name="사용자 008",
            ),
            MetadataEntity(
                entity_type="channel_talk_manager",
                external_key="manager-xyz",
                display_name="캐치업 팀",
                attributes={"is_assignee": True},
            ),
        ),
        "occurred_at": NOW,
    }
    values.update(overrides)
    return NormalizedObservation(**values)  # type: ignore[arg-type]


def _stored_observation(
    workspace_id: int,
    session_factory: Callable[[], Session],
    *,
    with_node: bool = True,
    source_updated_at: datetime | None = NOW,
    source_observed_at: datetime = NOW,
    **overrides: object,
) -> StoredObservation:
    """Observation과 그 node까지 실제로 저장한다.

    원문 변경 시각과 수집 시각을 따로 받는다 — 기준 시각 사슬의
    각 단계를 테스트가 하나씩 비워볼 수 있어야 한다.
    """
    document_id = f"CAM-{uuid.uuid4().hex[:8]}"
    source_version = SourceVersion(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        source_type=SOURCE_TYPE,
        source_identity=SourceIdentity(
            entity_type="user_chat",
            scope_id="ch-test",
            target_id="ch-test",
            external_document_id=document_id,
        ),
        change_kind=ChangeKind.CREATED,
        source_version_key="1",
        title=None,
        canonical_url=None,
        content='{"detail": {}}',
        content_type="application/vnd.channel-talk.user-chat+json",
        content_hash="a" * 64,
        source_updated_at=source_updated_at,
        observed_at=source_observed_at,
        idempotency_key=f"test:{document_id}",
        payload_hash="b" * 64,
        metadata={},
        created_at=NOW,
    )

    # Observation의 composite FK가 보려면 원문이 먼저 확정되어야 한다.
    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        uow.source_versions.add(source_version)
        uow.commit()

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        stored = uow.observations.add(
            workspace_id=workspace_id,
            source_version_id=source_version.id,
            observation=_observation(**overrides),
        )
        if with_node:
            uow.knowledge_nodes.ensure_for_resource(
                workspace_id=workspace_id,
                node_kind=NodeKind.OBSERVATION,
                resource_id=stored.id,
            )
        uow.commit()
    return stored


def _batch() -> KnowledgeCandidateBatch:
    """metadata Entity를 끝점으로 삼는 관계가 든 batch를 만든다."""
    return KnowledgeCandidateBatch(
        entities=[
            EntityCandidateDraft(
                local_key="e1",
                proposed_type="feature",
                proposed_name="결제 기능",
            ),
            EntityCandidateDraft(
                local_key="e2",
                proposed_type="system",
                proposed_name="인증 시스템",
            ),
        ],
        claims=[
            ClaimCandidateDraft(
                local_key="c1",
                subject_local_key="e1",
                predicate="release_month",
                value_type="text",
                value="2026-09",
                statement="9월 예정입니다.",
            )
        ],
        relation_assertions=[
            RelationAssertionCandidateDraft(
                local_key="r1",
                source_local_key="e1",
                target_local_key="e2",
                relation_type="depends_on",
                assertion_text="결제 기능은 인증 시스템에 의존한다.",
            ),
            # 레이어 1이 뽑은 고객이 한쪽 끝이다. 이 관계가 저장되는지가 핵심이다.
            RelationAssertionCandidateDraft(
                local_key="r2",
                source_local_key="m1",
                target_local_key="e1",
                relation_type="asked_about",
                assertion_text="고객이 결제 기능에 대해 물었다.",
            ),
        ],
    )


def _count(session_factory: Callable[[], Session], model, run_id: uuid.UUID) -> int:
    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        session = uow.knowledge_candidates._session  # noqa: SLF001
        return session.scalar(
            select(func.count())
            .select_from(model)
            .where(model.extraction_run_id == run_id)
        )


def test_candidates_are_stored_with_issued_identifiers(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """local_key가 실제 식별자로 바뀌고 지도가 돌아온다."""
    observation = _stored_observation(workspace_id, session_factory)

    result = store_knowledge_candidates(
        observation,
        _batch(),
        spec=SPEC,
        uow=uow_factory(),
    )

    stored = result.batch
    assert not result.reused
    # entity 4개 = metadata 2 + LLM 2
    assert set(stored.entity_ids) == {"m1", "m2", "e1", "e2"}
    assert set(stored.claim_ids) == {"c1"}
    assert set(stored.relation_ids) == {"r1", "r2"}
    assert stored.candidate_count == 7
    assert stored.evidence_link_count == 7


def test_metadata_entities_become_deterministic_candidates(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """레이어 1이 뽑은 Entity는 추론이 아니므로 출처가 다르게 남는다."""
    observation = _stored_observation(workspace_id, session_factory)

    result = store_knowledge_candidates(
        observation,
        _batch(),
        spec=SPEC,
        uow=uow_factory(),
    )

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        session = uow.knowledge_candidates._session  # noqa: SLF001
        rows = session.scalars(
            select(EntityCandidateRow)
            .where(EntityCandidateRow.extraction_run_id == result.batch.run_id)
            .order_by(EntityCandidateRow.local_key)
        ).all()
        by_key = {
            row.local_key: {
                "extraction_method": row.extraction_method,
                "confidence": row.confidence,
                "proposed_name": row.proposed_name,
                "raw_payload": row.raw_payload,
            }
            for row in rows
        }

    assert by_key["m1"]["extraction_method"] == ExtractionMethod.DETERMINISTIC.value
    assert by_key["m1"]["confidence"] == Decimal("1.0")
    assert by_key["m1"]["proposed_name"] == "사용자 008"
    assert by_key["m1"]["raw_payload"]["attributes"]["external_key"] == "user-abc"

    assert by_key["e1"]["extraction_method"] == ExtractionMethod.LLM.value
    assert by_key["e1"]["confidence"] is None


def test_relation_can_point_at_a_metadata_entity(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """'고객이 무엇을 물었는가'가 실제 FK로 저장된다.

    레이어 1을 둔 이유가 이것이다. metadata Entity가 행으로 먼저 들어가야
    관계의 끝점이 걸린다.
    """
    observation = _stored_observation(workspace_id, session_factory)

    result = store_knowledge_candidates(
        observation,
        _batch(),
        spec=SPEC,
        uow=uow_factory(),
    )

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        session = uow.knowledge_candidates._session  # noqa: SLF001
        relation = session.scalar(
            select(RelationRow).where(
                RelationRow.extraction_run_id == result.batch.run_id,
                RelationRow.local_key == "r2",
            )
        )
        source = session.get(EntityCandidateRow, relation.source_entity_candidate_id)
        found = {
            "relation_type": relation.relation_type,
            "source_id": relation.source_entity_candidate_id,
            "target_id": relation.target_entity_candidate_id,
            "source_method": source.extraction_method,
            "source_name": source.proposed_name,
        }

    assert found["relation_type"] == "asked_about"
    assert found["source_id"] == result.batch.entity_ids["m1"]
    assert found["target_id"] == result.batch.entity_ids["e1"]
    assert found["source_method"] == ExtractionMethod.DETERMINISTIC.value
    assert found["source_name"] == "사용자 008"


def test_claim_subject_points_at_the_stored_entity(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    observation = _stored_observation(workspace_id, session_factory)

    result = store_knowledge_candidates(
        observation,
        _batch(),
        spec=SPEC,
        uow=uow_factory(),
    )

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        session = uow.knowledge_candidates._session  # noqa: SLF001
        row = session.scalar(
            select(ClaimCandidateRow).where(
                ClaimCandidateRow.extraction_run_id == result.batch.run_id
            )
        )
        claim = {
            "subject_entity_candidate_id": row.subject_entity_candidate_id,
            "subject_node_id": row.subject_node_id,
            "predicate": row.predicate,
            "value": row.value,
            "value_hash": row.value_hash,
            "ontology_id": row.ontology_id,
            "ontology_version": row.ontology_version,
        }

    assert claim["subject_entity_candidate_id"] == result.batch.entity_ids["e1"]
    assert claim["subject_node_id"] is None
    assert claim["predicate"] == "release_month"
    assert claim["value"] == "2026-09"
    assert len(claim["value_hash"]) == 64
    assert claim["ontology_id"] == SPEC.ontology_id
    assert claim["ontology_version"] == SPEC.ontology_version


def test_every_candidate_is_linked_to_its_observation(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """모든 후보에 근거가 남는다. Claim에는 인용 문구까지 남는다."""
    observation = _stored_observation(workspace_id, session_factory)

    result = store_knowledge_candidates(
        observation,
        _batch(),
        spec=SPEC,
        uow=uow_factory(),
    )

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        session = uow.knowledge_candidates._session  # noqa: SLF001
        links = [
            {
                "evidence_node_id": row.evidence_node_id,
                "claim_candidate_id": row.claim_candidate_id,
                "excerpt": row.excerpt,
            }
            for row in session.scalars(
                select(EvidenceLinkRow).where(
                    EvidenceLinkRow.extraction_run_id == result.batch.run_id
                )
            ).all()
        ]
        node_id = uow.knowledge_nodes.get_for_resource(
            workspace_id=workspace_id,
            node_kind=NodeKind.OBSERVATION,
            resource_id=observation.id,
        ).id

    assert len(links) == 7
    assert {link["evidence_node_id"] for link in links} == {node_id}

    claim_links = [link for link in links if link["claim_candidate_id"] is not None]
    assert len(claim_links) == 1
    assert claim_links[0]["excerpt"] == "9월 예정입니다."


def _claim_locator(
    session_factory: Callable[[], Session],
    run_id: uuid.UUID,
) -> dict:
    """저장된 Claim evidence의 locator를 읽는다."""
    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        session = uow.knowledge_candidates._session  # noqa: SLF001
        return session.scalars(
            select(EvidenceLinkRow).where(
                EvidenceLinkRow.extraction_run_id == run_id,
                EvidenceLinkRow.claim_candidate_id.is_not(None),
            )
        ).one().locator


def test_claim_evidence_carries_codepoint_offset_locator(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """본문에서 다시 찾은 인용은 code point offset으로 위치가 남는다."""
    observation = _stored_observation(workspace_id, session_factory)

    result = store_knowledge_candidates(
        observation,
        _batch(),
        spec=SPEC,
        uow=uow_factory(),
    )

    locator = _claim_locator(session_factory, result.batch.run_id)
    assert locator["kind"] == "codepoint_offset"
    sliced = NORMALIZED_CONTENT[locator["start"] : locator["end"]]
    assert sliced == "9월 예정입니다."
    assert result.batch.located_claim_count == 1
    assert result.batch.demoted_not_found_count == 0
    assert result.batch.demoted_ambiguous_count == 0


def test_claim_evidence_carries_its_own_utterance_time(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """위치가 확정된 claim은 자기 발화의 시각을 locator에 함께 얻는다."""
    statement = "9월 예정입니다."
    start = NORMALIZED_CONTENT.index(statement)
    line_start = NORMALIZED_CONTENT.index("상담원:")
    observation = _stored_observation(
        workspace_id,
        session_factory,
        source_attributes={
            "utterance_spans": [
                {
                    "start": 0,
                    "end": line_start - 1,
                    "at": "2026-08-01T10:00:00+00:00",
                },
                {
                    "start": line_start,
                    "end": len(NORMALIZED_CONTENT),
                    "at": "2026-08-10T11:30:00+00:00",
                },
            ]
        },
    )

    result = store_knowledge_candidates(
        observation,
        _batch(),
        spec=SPEC,
        uow=uow_factory(),
    )

    locator = _claim_locator(session_factory, result.batch.run_id)
    assert line_start <= start
    # 문서 시작(8/1)이 아니라 그 문장을 말한 발화(8/10)의 시각이어야 한다.
    assert locator["event_at"] == "2026-08-10T11:30:00+00:00"


def test_claim_evidence_has_no_time_when_the_position_is_lost(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """위치를 잃은 claim은 시각도 얻지 않는다 — 남의 발화 시각을 붙이지 않는다."""
    observation = _stored_observation(
        workspace_id,
        session_factory,
        source_attributes={
            "utterance_spans": [
                {
                    "start": 0,
                    "end": len(NORMALIZED_CONTENT),
                    "at": "2026-08-10T11:30:00+00:00",
                }
            ]
        },
    )
    batch = _batch().model_copy(
        update={
            "claims": (
                ClaimCandidateDraft(
                    local_key="c1",
                    subject_local_key="e1",
                    predicate="release_month",
                    value_type="text",
                    value="2026-09",
                    statement="12월로 미뤄졌습니다.",
                ),
            )
        }
    )

    result = store_knowledge_candidates(
        observation,
        batch,
        spec=SPEC,
        uow=uow_factory(),
    )

    assert _claim_locator(session_factory, result.batch.run_id) == {}


def test_claim_evidence_has_no_time_outside_every_utterance_span(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """발화 구간 밖의 인용은 시각 없이 위치만 남는다."""
    observation = _stored_observation(
        workspace_id,
        session_factory,
        source_attributes={
            "utterance_spans": [
                {"start": 0, "end": 3, "at": "2026-08-01T10:00:00+00:00"}
            ]
        },
    )

    result = store_knowledge_candidates(
        observation,
        _batch(),
        spec=SPEC,
        uow=uow_factory(),
    )

    locator = _claim_locator(session_factory, result.batch.run_id)
    assert locator["kind"] == "codepoint_offset"
    assert "event_at" not in locator


def test_claim_evidence_is_demoted_when_statement_is_fabricated(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """본문에 없는 인용은 위치 없이 문서 단위 근거로 낮아진다."""
    observation = _stored_observation(workspace_id, session_factory)
    batch = _batch().model_copy(
        update={
            "claims": (
                ClaimCandidateDraft(
                    local_key="c1",
                    subject_local_key="e1",
                    predicate="release_month",
                    value_type="text",
                    value="2026-09",
                    statement="12월로 미뤄졌습니다.",
                ),
            )
        }
    )

    result = store_knowledge_candidates(
        observation,
        batch,
        spec=SPEC,
        uow=uow_factory(),
    )

    assert _claim_locator(session_factory, result.batch.run_id) == {}
    assert result.batch.located_claim_count == 0
    assert result.batch.demoted_not_found_count == 1
    assert result.batch.demoted_ambiguous_count == 0


def test_claim_evidence_is_demoted_when_statement_is_ambiguous(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """본문에 두 번 나오는 인용은 위치를 단정하지 않고 사유를 구분해 센다."""
    repeated = "고객: 9월 예정입니다.\n상담원: 9월 예정입니다."
    observation = _stored_observation(
        workspace_id,
        session_factory,
        content=repeated,
        content_hash=content_hash(repeated),
    )

    result = store_knowledge_candidates(
        observation,
        _batch(),
        spec=SPEC,
        uow=uow_factory(),
    )

    assert _claim_locator(session_factory, result.batch.run_id) == {}
    assert result.batch.located_claim_count == 0
    assert result.batch.demoted_not_found_count == 0
    assert result.batch.demoted_ambiguous_count == 1


def test_find_claim_candidates_carries_citation_verified(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """locator 확정·강등·evidence 없음이 각각 True/False/None으로 온다."""
    observation = _stored_observation(workspace_id, session_factory)

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        node_id = uow.knowledge_nodes.get_for_resource(
            workspace_id=workspace_id,
            node_kind=NodeKind.OBSERVATION,
            resource_id=observation.id,
        ).id
        uow.ontology.ensure(
            workspace_id=workspace_id,
            ontology_id=SPEC.ontology_id,
            vocabulary=SPEC.vocabulary,
        )
        run = uow.knowledge_candidates.start_run(
            workspace_id=workspace_id,
            input_node_id=node_id,
            spec=SPEC,
            started_at=NOW,
        )
        entity_id = uow.knowledge_candidates.add_entity_candidate(
            workspace_id=workspace_id,
            run_id=run.id,
            draft=EntityCandidateDraft(
                local_key="e1",
                proposed_type="feature",
                proposed_name="결제 기능",
            ),
            extraction_method=ExtractionMethod.LLM,
        )
        verified_id = uow.knowledge_candidates.add_claim_candidate(
            workspace_id=workspace_id,
            run_id=run.id,
            draft=ClaimCandidateDraft(
                local_key="c1",
                subject_local_key="e1",
                predicate="release_month",
                value_type="text",
                value="2026-09",
                statement="9월 예정입니다.",
            ),
            subject_candidate_id=entity_id,
            spec=SPEC,
            extraction_method=ExtractionMethod.LLM,
        )
        demoted_id = uow.knowledge_candidates.add_claim_candidate(
            workspace_id=workspace_id,
            run_id=run.id,
            draft=ClaimCandidateDraft(
                local_key="c2",
                subject_local_key="e1",
                predicate="release_month",
                value_type="text",
                value="2026-12",
                statement="12월로 미뤄졌습니다.",
            ),
            subject_candidate_id=entity_id,
            spec=SPEC,
            extraction_method=ExtractionMethod.LLM,
        )
        no_evidence_id = uow.knowledge_candidates.add_claim_candidate(
            workspace_id=workspace_id,
            run_id=run.id,
            draft=ClaimCandidateDraft(
                local_key="c3",
                subject_local_key="e1",
                predicate="release_month",
                value_type="text",
                value="2026-06",
                statement="6월이라는 말도 있었습니다.",
            ),
            subject_candidate_id=entity_id,
            spec=SPEC,
            extraction_method=ExtractionMethod.LLM,
        )
        start = NORMALIZED_CONTENT.index("9월 예정입니다.")
        uow.knowledge_candidates.add_evidence_link(
            workspace_id=workspace_id,
            run_id=run.id,
            evidence_node_id=node_id,
            claim_candidate_id=verified_id,
            excerpt="9월 예정입니다.",
            locator=Locator(
                kind="codepoint_offset",
                start=start,
                end=start + len("9월 예정입니다."),
            ),
        )
        uow.knowledge_candidates.add_evidence_link(
            workspace_id=workspace_id,
            run_id=run.id,
            evidence_node_id=node_id,
            claim_candidate_id=demoted_id,
            excerpt="12월로 미뤄졌습니다.",
            locator=None,
        )
        uow.commit()

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        candidates = uow.knowledge_candidates.find_claim_candidates(
            workspace_id=workspace_id,
        )

    by_id = {candidate.id: candidate for candidate in candidates}
    assert by_id[verified_id].citation_verified is True
    assert by_id[demoted_id].citation_verified is False
    assert by_id[no_evidence_id].citation_verified is None


def test_find_claim_candidates_excludes_rejected(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """rejected는 빠지고 pending·accepted·닫힌 accepted는 실린다."""
    observation = _stored_observation(workspace_id, session_factory)

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        node_id = uow.knowledge_nodes.get_for_resource(
            workspace_id=workspace_id,
            node_kind=NodeKind.OBSERVATION,
            resource_id=observation.id,
        ).id
        uow.ontology.ensure(
            workspace_id=workspace_id,
            ontology_id=SPEC.ontology_id,
            vocabulary=SPEC.vocabulary,
        )
        run = uow.knowledge_candidates.start_run(
            workspace_id=workspace_id,
            input_node_id=node_id,
            spec=SPEC,
            started_at=NOW,
        )
        entity_id = uow.knowledge_candidates.add_entity_candidate(
            workspace_id=workspace_id,
            run_id=run.id,
            draft=EntityCandidateDraft(
                local_key="e1",
                proposed_type="feature",
                proposed_name="결제 기능",
            ),
            extraction_method=ExtractionMethod.LLM,
        )
        claim_ids = {
            local_key: uow.knowledge_candidates.add_claim_candidate(
                workspace_id=workspace_id,
                run_id=run.id,
                draft=ClaimCandidateDraft(
                    local_key=local_key,
                    subject_local_key="e1",
                    predicate="release_month",
                    value_type="text",
                    value=value,
                    statement=f"{value} 예정입니다.",
                ),
                subject_candidate_id=entity_id,
                spec=SPEC,
                extraction_method=ExtractionMethod.LLM,
            )
            for local_key, value in (
                ("pending", "2026-09"),
                ("live", "2026-10"),
                ("closed", "2026-11"),
                ("rejected", "2026-12"),
            )
        }
        uow.knowledge_candidates.accept_claims(
            claim_ids=[claim_ids["live"], claim_ids["closed"]],
        )
        uow.knowledge_candidates.close_claim(
            claim_id=claim_ids["closed"],
            valid_to=NOW + timedelta(days=1),
        )
        uow.knowledge_candidates.reject_claim(claim_id=claim_ids["rejected"])
        uow.commit()

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        candidates = uow.knowledge_candidates.find_claim_candidates(
            workspace_id=workspace_id,
        )

    found = {candidate.id for candidate in candidates}
    assert claim_ids["rejected"] not in found
    assert claim_ids["pending"] in found
    assert claim_ids["live"] in found
    # 닫힌 accepted는 "한때 참이었다"의 재료라 계속 실려야 한다.
    assert claim_ids["closed"] in found
    by_id = {candidate.id: candidate for candidate in candidates}
    assert by_id[claim_ids["closed"]].valid_to is not None
    assert by_id[claim_ids["live"]].valid_to is None
    # 구간의 시작도 함께 실린다. as-of 조회가 읽을 재료다.
    assert by_id[claim_ids["live"]].valid_from is not None
    # 확정되지 않은 후보는 구간이 열리지 않았으므로 시작이 없다.
    assert by_id[claim_ids["pending"]].valid_from is None


def _chat_with_one_utterance(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    *,
    statement: str,
    opened_at: datetime,
    spoken_at: datetime,
) -> uuid.UUID:
    """상담 하나를 저장하고 그 발화에서 나온 claim의 id를 돌려준다.

    상담이 열린 시각과 발화 시각을 따로 받는다 — 둘이 다를 때 어느 쪽이
    claim의 시간이 되는지가 이 회귀의 관심사다.
    """
    line = f"[{spoken_at:%Y-%m-%d %H:%M}] 상담원: {statement}"
    observation = _stored_observation(
        workspace_id,
        session_factory,
        content=line,
        content_hash=content_hash(line),
        occurred_at=opened_at,
        source_updated_at=opened_at,
        source_observed_at=opened_at,
        source_attributes={
            "utterance_spans": [
                {
                    "start": 0,
                    "end": len(line),
                    "at": spoken_at.isoformat(),
                }
            ]
        },
    )
    batch = KnowledgeCandidateBatch(
        entities=[
            EntityCandidateDraft(
                local_key="e1",
                proposed_type="feature",
                proposed_name="결제 기능",
            )
        ],
        claims=[
            ClaimCandidateDraft(
                local_key="c1",
                subject_local_key="e1",
                predicate="release_month",
                value_type="text",
                value="2026-09",
                statement=statement,
            )
        ],
        relation_assertions=[],
    )
    result = store_knowledge_candidates(
        observation,
        batch,
        spec=SPEC,
        uow=uow_factory(),
    )
    return result.batch.claim_ids["c1"]


def test_observed_at_follows_the_utterance_not_the_chat_opening(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """상담 시작 순서가 아니라 발화 순서로 claim의 선후가 정해진다.

    8/1에 열린 상담의 8/10 발화는 8/5에 열린 상담의 8/5 발화보다 나중이다.
    문서 시각만 보면 이 선후가 뒤집혀 모순 판정의 승자가 바뀐다.
    """
    opened_early = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
    late_utterance = datetime(2026, 8, 10, 11, 30, tzinfo=timezone.utc)
    opened_later = datetime(2026, 8, 5, 9, 0, tzinfo=timezone.utc)

    first_chat_claim = _chat_with_one_utterance(
        workspace_id,
        session_factory,
        uow_factory,
        statement="결제 기능은 10월로 미뤄졌습니다.",
        opened_at=opened_early,
        spoken_at=late_utterance,
    )
    second_chat_claim = _chat_with_one_utterance(
        workspace_id,
        session_factory,
        uow_factory,
        statement="결제 기능은 9월 예정입니다.",
        opened_at=opened_later,
        spoken_at=opened_later,
    )

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        candidates = uow.knowledge_candidates.find_claim_candidates(
            workspace_id=workspace_id,
        )

    by_id = {candidate.id: candidate for candidate in candidates}
    assert by_id[first_chat_claim].observed_at == late_utterance
    assert by_id[second_chat_claim].observed_at == opened_later
    assert by_id[first_chat_claim].observed_at > by_id[second_chat_claim].observed_at


def _claim_observed_at(
    workspace_id: int,
    session_factory: Callable[[], Session],
    observation: StoredObservation,
) -> datetime:
    """관찰 하나에 claim을 달고 reader가 준 관찰 시각을 돌려준다."""
    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        node_id = uow.knowledge_nodes.get_for_resource(
            workspace_id=workspace_id,
            node_kind=NodeKind.OBSERVATION,
            resource_id=observation.id,
        ).id
        uow.ontology.ensure(
            workspace_id=workspace_id,
            ontology_id=SPEC.ontology_id,
            vocabulary=SPEC.vocabulary,
        )
        run = uow.knowledge_candidates.start_run(
            workspace_id=workspace_id,
            input_node_id=node_id,
            spec=SPEC,
            started_at=NOW,
        )
        entity_id = uow.knowledge_candidates.add_entity_candidate(
            workspace_id=workspace_id,
            run_id=run.id,
            draft=EntityCandidateDraft(
                local_key="e1",
                proposed_type="feature",
                proposed_name="결제 기능",
            ),
            extraction_method=ExtractionMethod.LLM,
        )
        claim_id = uow.knowledge_candidates.add_claim_candidate(
            workspace_id=workspace_id,
            run_id=run.id,
            draft=ClaimCandidateDraft(
                local_key="c1",
                subject_local_key="e1",
                predicate="release_month",
                value_type="text",
                value="2026-09",
                statement="9월 예정입니다.",
            ),
            subject_candidate_id=entity_id,
            spec=SPEC,
            extraction_method=ExtractionMethod.LLM,
        )
        uow.commit()

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        candidates = uow.knowledge_candidates.find_claim_candidates(
            workspace_id=workspace_id,
        )

    by_id = {candidate.id: candidate for candidate in candidates}
    return by_id[claim_id].observed_at


def test_observed_at_prefers_occurred_at(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """사건 시각이 있으면 그것이 관찰 시각이 된다."""
    occurred_at = NOW - timedelta(days=10)
    observation = _stored_observation(
        workspace_id,
        session_factory,
        occurred_at=occurred_at,
        source_updated_at=NOW - timedelta(days=5),
        source_observed_at=NOW,
    )

    found = _claim_observed_at(workspace_id, session_factory, observation)

    assert found == occurred_at


def test_observed_at_falls_back_to_source_updated_at(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """사건 시각이 없으면 원문 변경 시각으로 내려간다."""
    source_updated_at = NOW - timedelta(days=5)
    observation = _stored_observation(
        workspace_id,
        session_factory,
        occurred_at=None,
        source_updated_at=source_updated_at,
        source_observed_at=NOW,
    )

    found = _claim_observed_at(workspace_id, session_factory, observation)

    assert found == source_updated_at


def test_observed_at_falls_back_to_collection_time(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """둘 다 없으면 수집 시각이 남는다 — 사슬의 마지막 단계다."""
    collected_at = NOW - timedelta(hours=3)
    observation = _stored_observation(
        workspace_id,
        session_factory,
        occurred_at=None,
        source_updated_at=None,
        source_observed_at=collected_at,
    )

    found = _claim_observed_at(workspace_id, session_factory, observation)

    assert found == collected_at


def test_run_is_recorded_as_succeeded(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """실행 기록이 입력 node를 가리키고 끝맺음까지 남는다."""
    observation = _stored_observation(workspace_id, session_factory)

    result = store_knowledge_candidates(
        observation,
        _batch(),
        spec=SPEC,
        uow=uow_factory(),
    )

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        session = uow.knowledge_candidates._session  # noqa: SLF001
        row = session.get(ExtractionRunRow, result.batch.run_id)
        run = {
            "status": row.status,
            "input_node_id": row.input_node_id,
            "provider": row.provider,
            "completed_at": row.completed_at,
        }
        node_id = uow.knowledge_nodes.get_for_resource(
            workspace_id=workspace_id,
            node_kind=NodeKind.OBSERVATION,
            resource_id=observation.id,
        ).id

    assert run["status"] == "succeeded"
    assert run["input_node_id"] == node_id
    assert run["provider"] == "aws_bedrock"
    assert run["completed_at"] is not None


def test_storing_twice_does_not_stack_candidates(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """후보를 두 벌 쌓으면 resolution이 같은 대상을 여러 번 본다."""
    observation = _stored_observation(workspace_id, session_factory)

    first = store_knowledge_candidates(
        observation, _batch(), spec=SPEC, uow=uow_factory()
    )
    second = store_knowledge_candidates(
        observation, _batch(), spec=SPEC, uow=uow_factory()
    )

    assert not first.reused
    assert second.reused
    assert _count(session_factory, EntityCandidateRow, first.batch.run_id) == 4


def test_storing_needs_the_observation_node(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """graph에 올라오지 않은 Observation은 근거가 될 수 없다."""
    observation = _stored_observation(
        workspace_id,
        session_factory,
        with_node=False,
    )

    with pytest.raises(ObservationNodeMissing):
        store_knowledge_candidates(
            observation, _batch(), spec=SPEC, uow=uow_factory()
        )


def test_unknown_local_key_is_rejected(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """요청에 없던 metadata Entity를 가리키면 저장되지 않는다.

    계약 검증이 batch 안에서만 보므로, 저장 시점이 이것을 막는 마지막 자리다.
    """
    observation = _stored_observation(
        workspace_id,
        session_factory,
        metadata_entities=(),
    )
    batch = KnowledgeCandidateBatch(
        entities=[
            EntityCandidateDraft(
                local_key="e1",
                proposed_type="feature",
                proposed_name="결제 기능",
            )
        ],
        relation_assertions=[
            RelationAssertionCandidateDraft(
                local_key="r1",
                source_local_key="m1",
                target_local_key="e1",
                relation_type="asked_about",
                assertion_text="고객이 물었다.",
            )
        ],
    )

    with pytest.raises(ValueError, match="m1"):
        store_knowledge_candidates(observation, batch, spec=SPEC, uow=uow_factory())


def test_local_key_is_unique_within_a_run(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """같은 run에서 local_key가 겹치면 참조가 어느 쪽인지 알 수 없다."""
    observation = _stored_observation(workspace_id, session_factory)

    with pytest.raises(IntegrityError):
        with uow_factory() as uow:
            node = uow.knowledge_nodes.get_for_resource(
                workspace_id=workspace_id,
                node_kind=NodeKind.OBSERVATION,
                resource_id=observation.id,
            )
            run = uow.knowledge_candidates.start_run(
                workspace_id=workspace_id,
                input_node_id=node.id,
                spec=SPEC,
                started_at=NOW,
            )
            for _ in range(2):
                uow.knowledge_candidates.add_entity_candidate(
                    workspace_id=workspace_id,
                    run_id=run.id,
                    draft=EntityCandidateDraft(
                        local_key="e1",
                        proposed_type="feature",
                        proposed_name="결제 기능",
                    ),
                    extraction_method=ExtractionMethod.LLM,
                )
            uow.commit()


def test_run_records_the_vocabulary_snapshot(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """한 번의 실행은 하나의 어휘로 도므로 실행에 한 번 남긴다.

    predicate와 relation_type이 같은 어휘 스냅샷에서 나오는데 claim에만
    적으면 관계 어휘가 어디서 왔는지 알 수 없다.
    """
    observation = _stored_observation(workspace_id, session_factory)

    result = store_knowledge_candidates(
        observation,
        _batch(),
        spec=SPEC,
        uow=uow_factory(),
    )

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        session = uow.knowledge_candidates._session  # noqa: SLF001
        row = session.get(ExtractionRunRow, result.batch.run_id)
        run = {
            "ontology_id": row.ontology_id,
            "ontology_version": row.ontology_version,
        }
        claim = session.scalar(
            select(ClaimCandidateRow).where(
                ClaimCandidateRow.extraction_run_id == result.batch.run_id
            )
        )
        claim_ontology = (claim.ontology_id, claim.ontology_version)

    assert run["ontology_id"] == SPEC.ontology_id
    assert run["ontology_version"] == SPEC.ontology_version
    # claim의 컬럼은 조인 없이 필터하려고 둔 사본이므로 실행과 어긋나면 안 된다.
    assert claim_ontology == (run["ontology_id"], run["ontology_version"])


def test_the_vocabulary_snapshot_is_stored_with_the_run(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """버전만 남기면 그 어휘가 무엇이었는지 되짚지 못한다."""
    observation = _stored_observation(workspace_id, session_factory)

    store_knowledge_candidates(observation, _batch(), spec=SPEC, uow=uow_factory())

    with KnowledgeMaintenanceUnitOfWork(session_factory) as reader:
        found = reader.ontology.get(
            workspace_id=workspace_id,
            ontology_id=SPEC.ontology_id,
            version=SPEC.ontology_version,
        )

    assert found is not None
    assert found.predicates == ("release_month",)
    assert found.relation_types == ("depends_on", "asked_about")


def test_the_same_snapshot_can_be_written_twice(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """같은 내용이면 두 번 적어도 문제가 없다. 재실행이 안전해야 한다."""
    vocabulary = ExtractionVocabulary(
        snapshot_id="frozen-1",
        predicates=("release_month",),
    )

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        uow.ontology.ensure(
            workspace_id=workspace_id,
            ontology_id="test.ontology",
            vocabulary=vocabulary,
        )
        again = uow.ontology.ensure(
            workspace_id=workspace_id,
            ontology_id="test.ontology",
            vocabulary=vocabulary,
        )
        uow.commit()

    assert again.predicates == ("release_month",)


def test_a_different_vocabulary_under_the_same_version_is_rejected(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """같은 이름에 다른 어휘를 담으면 감사 기록이 거짓이 된다.

    조용히 기존 값을 돌려주면 실행이 가리키는 스냅샷과 실제로 LLM에 넣은
    어휘가 달라진다. 덮어쓰지 않는 것과 충돌을 삼키는 것은 다르다.
    """
    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        uow.ontology.ensure(
            workspace_id=workspace_id,
            ontology_id="test.ontology",
            vocabulary=ExtractionVocabulary(
                snapshot_id="frozen-2",
                predicates=("release_month",),
            ),
        )
        uow.commit()

    with pytest.raises(OntologySnapshotConflict, match="frozen-2"):
        with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
            uow.ontology.ensure(
                workspace_id=workspace_id,
                ontology_id="test.ontology",
                vocabulary=ExtractionVocabulary(
                    snapshot_id="frozen-2",
                    predicates=("launch_month",),
                ),
            )
            uow.commit()


def test_a_run_cannot_point_at_a_missing_snapshot(
    workspace_id: int,
    session_factory: Callable[[], Session],
) -> None:
    """기록되지 않은 어휘를 가리키는 실행은 만들어질 수 없다."""
    observation = _stored_observation(workspace_id, session_factory)

    with pytest.raises(IntegrityError):
        with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
            node = uow.knowledge_nodes.get_for_resource(
                workspace_id=workspace_id,
                node_kind=NodeKind.OBSERVATION,
                resource_id=observation.id,
            )
            uow.knowledge_candidates.start_run(
                workspace_id=workspace_id,
                input_node_id=node.id,
                spec=ExtractionRunSpec(
                    provider="aws_bedrock",
                    extractor_version="x/0",
                    ontology_id="never.recorded",
                    vocabulary=ExtractionVocabulary(snapshot_id="ghost"),
                ),
                started_at=NOW,
            )
            uow.commit()


def _spec(**overrides: object) -> ExtractionRunSpec:
    values: dict[str, object] = {
        "provider": SPEC.provider,
        "extractor_version": SPEC.extractor_version,
        "ontology_id": SPEC.ontology_id,
        "vocabulary": SPEC.vocabulary,
        "model": SPEC.model,
        "prompt_version": SPEC.prompt_version,
    }
    values.update(overrides)
    return ExtractionRunSpec(**values)  # type: ignore[arg-type]


def test_a_new_prompt_version_triggers_re_extraction(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """prompt를 고치면 다시 추출한다.

    입력만 보고 판정하면 프롬프트 버그를 고쳐도 같은 Observation이 영영
    다시 추출되지 않는다. 중복 방지가 아니라 영구 동결이 된다.
    """
    observation = _stored_observation(workspace_id, session_factory)

    first = store_knowledge_candidates(
        observation, _batch(), spec=SPEC, uow=uow_factory()
    )
    second = store_knowledge_candidates(
        observation,
        _batch(),
        spec=_spec(prompt_version="extract_knowledge_candidates/2"),
        uow=uow_factory(),
    )

    assert not first.reused
    assert not second.reused
    assert second.batch.run_id != first.batch.run_id


def test_reextraction_supersedes_stale_pending_candidates(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """재추출은 구 실행이 남긴 pending 후보를 은퇴시킨다.

    은퇴시키지 않으면 resolution이 구 배치와 새 배치를 함께 긁어 같은
    대상을 두 번 처리한다. 사람 결정과 해소 결과는 그대로 둔다.
    """
    observation = _stored_observation(workspace_id, session_factory)

    first = store_knowledge_candidates(
        observation, _batch(), spec=SPEC, uow=uow_factory()
    )
    accepted_candidate_id = first.batch.entity_ids["m1"]

    with uow_factory() as uow:
        node = uow.knowledge_nodes.create_entity_node(
            workspace_id=workspace_id,
            entity_type="channel_talk_user",
            canonical_key=f"{SOURCE_TYPE}:channel_talk_user:{uuid.uuid4().hex}",
            display_name="사용자 008",
        )
        uow.knowledge_candidates.mark_entity_resolved(
            candidate_id=accepted_candidate_id,
            status=EntityResolutionStatus.ACCEPTED,
            resolved_node_id=node.id,
        )
        uow.commit()

    second = store_knowledge_candidates(
        observation,
        _batch(),
        spec=_spec(prompt_version="extract_knowledge_candidates/2"),
        uow=uow_factory(),
    )
    assert second.batch.run_id != first.batch.run_id

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        session = uow.knowledge_candidates._session  # noqa: SLF001
        old_statuses = {
            model.__name__: sorted(
                {
                    status
                    for status in session.scalars(
                        select(model.resolution_status).where(
                            model.extraction_run_id == first.batch.run_id,
                            model.id != accepted_candidate_id,
                        )
                    )
                }
            )
            for model in (EntityCandidateRow, ClaimCandidateRow, RelationRow)
        }
        new_statuses = {
            model.__name__: sorted(
                {
                    status
                    for status in session.scalars(
                        select(model.resolution_status).where(
                            model.extraction_run_id == second.batch.run_id
                        )
                    )
                }
            )
            for model in (EntityCandidateRow, ClaimCandidateRow, RelationRow)
        }
        accepted_status = session.scalar(
            select(EntityCandidateRow.resolution_status).where(
                EntityCandidateRow.id == accepted_candidate_id
            )
        )

    # 구 run의 pending이던 후보는 전부 은퇴한다.
    assert old_statuses == {
        "KnowledgeEntityCandidate": ["superseded"],
        "KnowledgeClaimCandidate": ["superseded"],
        "KnowledgeRelationAssertionCandidate": ["superseded"],
    }
    # 사람 결정·해소 결과는 불변이다.
    assert accepted_status == EntityResolutionStatus.ACCEPTED.value
    # 새 run의 후보는 그대로 pending이다.
    assert new_statuses == {
        "KnowledgeEntityCandidate": ["pending"],
        "KnowledgeClaimCandidate": ["pending"],
        "KnowledgeRelationAssertionCandidate": ["pending"],
    }

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        pending_entity_ids = {
            candidate.id
            for candidate in uow.knowledge_candidates.find_pending_entity_candidates(
                workspace_id=workspace_id,
            )
        }
        claim_ids = {
            candidate.id
            for candidate in uow.knowledge_candidates.find_claim_candidates(
                workspace_id=workspace_id,
            )
        }

    assert not (set(first.batch.entity_ids.values()) & pending_entity_ids)
    assert set(second.batch.entity_ids.values()) <= pending_entity_ids
    assert not (set(first.batch.claim_ids.values()) & claim_ids)
    assert set(second.batch.claim_ids.values()) <= claim_ids


def test_a_new_ontology_version_triggers_re_extraction(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """어휘를 올리면 다시 추출한다."""
    observation = _stored_observation(workspace_id, session_factory)

    store_knowledge_candidates(observation, _batch(), spec=SPEC, uow=uow_factory())
    second = store_knowledge_candidates(
        observation,
        _batch(),
        spec=_spec(
            vocabulary=ExtractionVocabulary(
                snapshot_id="test-round-2",
                predicates=("release_month", "owner_team"),
                relation_types=("depends_on", "asked_about"),
            )
        ),
        uow=uow_factory(),
    )

    assert not second.reused


def test_the_same_contract_still_reuses(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """계약이 같으면 그대로 건너뛴다. 재실행이 안전해야 한다."""
    observation = _stored_observation(workspace_id, session_factory)

    first = store_knowledge_candidates(
        observation, _batch(), spec=SPEC, uow=uow_factory()
    )
    second = store_knowledge_candidates(
        observation, _batch(), spec=SPEC, uow=uow_factory()
    )

    assert second.reused
    # 건너뛰더라도 어느 실행을 재사용했는지 알려준다.
    assert second.batch.run_id == first.batch.run_id


def test_a_failed_extraction_leaves_a_run(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """실패도 기록으로 남는다.

    남기지 않으면 어느 Observation이 왜 실패했는지 DB에 흔적이 없다. 수천
    건에서 몇 %가 조용히 빠져도 아무도 모른다.
    """
    observation = _stored_observation(workspace_id, session_factory)

    run_id = record_failed_extraction(
        observation,
        spec=SPEC,
        error="subject를 찾을 수 없다",
        raw_output={"parsed": None, "note": "스키마에서 어긋남"},
        uow=uow_factory(),
    )

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        session = uow.knowledge_candidates._session  # noqa: SLF001
        row = session.get(ExtractionRunRow, run_id)
        found = {
            "status": row.status,
            "error": row.error,
            "raw_output": row.raw_output,
        }

    assert found["status"] == "failed"
    assert "subject" in found["error"]
    assert found["raw_output"]["note"] == "스키마에서 어긋남"


def test_a_failed_run_does_not_block_a_retry(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """실패 기록이 재시도를 막으면 안 된다.

    재추출 판정이 성공한 실행만 보므로 같은 계약으로 다시 시도할 수 있다.
    """
    observation = _stored_observation(workspace_id, session_factory)

    record_failed_extraction(
        observation,
        spec=SPEC,
        error="일시적 오류",
        uow=uow_factory(),
    )
    retried = store_knowledge_candidates(
        observation, _batch(), spec=SPEC, uow=uow_factory()
    )

    assert not retried.reused
    assert retried.batch.candidate_count == 7


def test_a_successful_run_keeps_the_raw_output(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """성공한 실행도 원본 출력을 남겨 나중에 재현할 수 있다."""
    observation = _stored_observation(workspace_id, session_factory)

    result = store_knowledge_candidates(
        observation,
        _batch(),
        spec=SPEC,
        raw_output={"content": [{"type": "tool_use"}]},
        uow=uow_factory(),
    )

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        session = uow.knowledge_candidates._session  # noqa: SLF001
        raw = session.get(ExtractionRunRow, result.batch.run_id).raw_output

    assert raw["content"][0]["type"] == "tool_use"


def test_a_run_without_raw_output_stores_sql_null(
    workspace_id: int,
    session_factory: Callable[[], Session],
    uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
) -> None:
    """원본 출력이 없으면 SQL NULL이어야 한다.

    JSONB에 Python None을 그대로 넣으면 JSON null로 저장되어
    `raw_output IS NOT NULL`이 참이 된다. "원본 출력이 있다"고 거짓을 말하며,
    나중에 실패 원인을 찾으려 조회하면 전부 걸리는데 열어 보면 비어 있다.
    """
    observation = _stored_observation(workspace_id, session_factory)

    result = store_knowledge_candidates(
        observation, _batch(), spec=SPEC, uow=uow_factory()
    )

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        session = uow.knowledge_candidates._session  # noqa: SLF001
        has_value = session.scalar(
            select(ExtractionRunRow.raw_output.is_not(None)).where(
                ExtractionRunRow.id == result.batch.run_id
            )
        )

    assert has_value is False


# 이 워크스페이스에는 다른 테스트가 남긴 후보가 이미 커밋되어 있으므로, 집계
# 테스트는 자기만 쓰는 이름을 붙여 남의 행과 섞이지 않게 한다.
USAGE_PREFIX = "vocab_convergence_test_"

# 개발 workspace를 공유하므로 발행 계보 테스트는 전용 ontology를 쓴다. 기존
# 커밋된 스냅샷이 `list_versions`에 섞이면 다음 버전 계산이 흔들린다.
CONVERGENCE_ONTOLOGY_ID = "catchup.test-convergence"


def _store_claim_candidates(
    workspace_id: int,
    session_factory: Callable[[], Session],
    *,
    claims: list[ClaimCandidateDraft],
    subject_type: str = "feature",
) -> dict[str, uuid.UUID]:
    """pending claim 후보들을 한 run으로 저장하고 local_key별 id를 돌려준다."""
    observation = _stored_observation(workspace_id, session_factory)

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        node_id = uow.knowledge_nodes.get_for_resource(
            workspace_id=workspace_id,
            node_kind=NodeKind.OBSERVATION,
            resource_id=observation.id,
        ).id
        uow.ontology.ensure(
            workspace_id=workspace_id,
            ontology_id=SPEC.ontology_id,
            vocabulary=SPEC.vocabulary,
        )
        run = uow.knowledge_candidates.start_run(
            workspace_id=workspace_id,
            input_node_id=node_id,
            spec=SPEC,
            started_at=NOW,
        )
        entity_id = uow.knowledge_candidates.add_entity_candidate(
            workspace_id=workspace_id,
            run_id=run.id,
            draft=EntityCandidateDraft(
                local_key="e1",
                proposed_type=subject_type,
                proposed_name="결제 기능",
            ),
            extraction_method=ExtractionMethod.LLM,
        )
        claim_ids = {
            draft.local_key: uow.knowledge_candidates.add_claim_candidate(
                workspace_id=workspace_id,
                run_id=run.id,
                draft=draft,
                subject_candidate_id=entity_id,
                spec=SPEC,
                extraction_method=ExtractionMethod.LLM,
            )
            for draft in claims
        }
        uow.commit()
    return claim_ids


def _store_relation_candidates(
    workspace_id: int,
    session_factory: Callable[[], Session],
    *,
    relations: list[RelationAssertionCandidateDraft],
) -> dict[str, uuid.UUID]:
    """pending 관계 후보들을 한 run으로 저장하고 local_key별 id를 돌려준다."""
    observation = _stored_observation(workspace_id, session_factory)

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        node_id = uow.knowledge_nodes.get_for_resource(
            workspace_id=workspace_id,
            node_kind=NodeKind.OBSERVATION,
            resource_id=observation.id,
        ).id
        uow.ontology.ensure(
            workspace_id=workspace_id,
            ontology_id=SPEC.ontology_id,
            vocabulary=SPEC.vocabulary,
        )
        run = uow.knowledge_candidates.start_run(
            workspace_id=workspace_id,
            input_node_id=node_id,
            spec=SPEC,
            started_at=NOW,
        )
        entity_ids = {
            local_key: uow.knowledge_candidates.add_entity_candidate(
                workspace_id=workspace_id,
                run_id=run.id,
                draft=EntityCandidateDraft(
                    local_key=local_key,
                    proposed_type="feature",
                    proposed_name=local_key,
                ),
                extraction_method=ExtractionMethod.LLM,
            )
            for local_key in ("e1", "e2")
        }
        relation_ids = {
            draft.local_key: uow.knowledge_candidates.add_relation_candidate(
                workspace_id=workspace_id,
                run_id=run.id,
                draft=draft,
                source_candidate_id=entity_ids[draft.source_local_key],
                target_candidate_id=entity_ids[draft.target_local_key],
                extraction_method=ExtractionMethod.LLM,
            )
            for draft in relations
        }
        uow.commit()
    return relation_ids


def _patch_candidate(
    session_factory: Callable[[], Session],
    model,
    candidate_id: uuid.UUID,
    **values: object,
) -> None:
    """후보 행의 컬럼을 직접 고친다.

    superseded 상태와 비어 있는 assertion_text는 저장 경로가 만들지 않으므로
    테스트가 행을 손질한다.
    """
    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        session = uow.knowledge_candidates._session  # noqa: SLF001
        session.execute(
            update(model).where(model.id == candidate_id).values(**values)
        )
        uow.commit()


def _claim_draft(
    local_key: str,
    *,
    predicate: str,
    value: object,
    statement: str,
    value_type: str = "text",
) -> ClaimCandidateDraft:
    return ClaimCandidateDraft(
        local_key=local_key,
        subject_local_key="e1",
        predicate=predicate,
        value_type=value_type,
        value=value,
        statement=statement,
    )


class TestSummarizePredicateUsage:
    """pending claim 후보의 predicate 사용 현황 집계를 고정한다."""

    def test_pending만_집계하고_상태별로_거른다(
        self,
        workspace_id: int,
        session_factory: Callable[[], Session],
    ) -> None:
        predicate = f"{USAGE_PREFIX}deployment_scheduled_on"
        claim_ids = _store_claim_candidates(
            workspace_id,
            session_factory,
            claims=[
                _claim_draft(
                    local_key,
                    predicate=predicate,
                    value="2026-08-12",
                    statement=f"{local_key} 배포 예정입니다.",
                )
                for local_key in ("p1", "p2", "superseded", "rejected")
            ],
        )
        _patch_candidate(
            session_factory,
            ClaimCandidateRow,
            claim_ids["superseded"],
            resolution_status="superseded",
        )
        with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
            uow.knowledge_candidates.reject_claim(
                claim_id=claim_ids["rejected"],
            )
            uow.commit()

        with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
            usage = uow.knowledge_candidates.summarize_predicate_usage(
                workspace_id=workspace_id,
            )

        by_name = {item.name: item for item in usage}
        assert by_name[predicate].usage_count == 2

    def test_값과_예문을_상한까지_중복_없이_담는다(
        self,
        workspace_id: int,
        session_factory: Callable[[], Session],
    ) -> None:
        predicate = f"{USAGE_PREFIX}capped_predicate"
        _store_claim_candidates(
            workspace_id,
            session_factory,
            claims=[
                _claim_draft(
                    "c1",
                    predicate=predicate,
                    value="2026-08-12",
                    statement="8월 12일에 배포합니다.",
                ),
                _claim_draft(
                    "c2",
                    predicate=predicate,
                    value="2026-08-12",
                    statement="배포는 8월 12일입니다.",
                ),
                _claim_draft(
                    "c3",
                    predicate=predicate,
                    value={"day": 3},
                    value_type="json",
                    statement="8월 12일에 배포합니다.",
                ),
            ],
        )

        with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
            usage = uow.knowledge_candidates.summarize_predicate_usage(
                workspace_id=workspace_id,
                value_cap=2,
                example_cap=1,
            )

        item = {entry.name: entry for entry in usage}[predicate]
        assert item.usage_count == 3
        # 문자열 값은 비가공이어야 한다. Task 3의 enum 치역 가드가 사전의
        # enum_values와 이 문자열을 직접 비교한다.
        assert "2026-08-12" in item.observed_values
        assert '{"day": 3}' in item.observed_values
        assert len(item.observed_values) <= 2
        assert len(item.example_statements) == 1
        assert set(item.value_types) == {"text", "json"}

    def test_subject_entity_후보의_종류를_모은다(
        self,
        workspace_id: int,
        session_factory: Callable[[], Session],
    ) -> None:
        predicate = f"{USAGE_PREFIX}owner_of"
        _store_claim_candidates(
            workspace_id,
            session_factory,
            claims=[
                _claim_draft(
                    "c1",
                    predicate=predicate,
                    value="결제팀",
                    statement="결제팀이 담당합니다.",
                )
            ],
            subject_type="service",
        )

        with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
            usage = uow.knowledge_candidates.summarize_predicate_usage(
                workspace_id=workspace_id,
            )

        item = {entry.name: entry for entry in usage}[predicate]
        assert item.subject_types == ("service",)

    def test_사용_횟수_내림차순으로_돌려준다(
        self,
        workspace_id: int,
        session_factory: Callable[[], Session],
    ) -> None:
        rare = f"{USAGE_PREFIX}rare_predicate"
        common = f"{USAGE_PREFIX}common_predicate"
        _store_claim_candidates(
            workspace_id,
            session_factory,
            claims=[
                _claim_draft(
                    "c1",
                    predicate=rare,
                    value="한 번",
                    statement="한 번 쓰였습니다.",
                ),
                *[
                    _claim_draft(
                        f"c{index}",
                        predicate=common,
                        value=f"값 {index}",
                        statement=f"{index}번째로 쓰였습니다.",
                    )
                    for index in range(2, 5)
                ],
            ],
        )

        with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
            usage = uow.knowledge_candidates.summarize_predicate_usage(
                workspace_id=workspace_id,
            )

        names = [
            item.name for item in usage if item.name in {rare, common}
        ]
        assert names == [common, rare]


class TestSummarizeRelationUsage:
    """pending 관계 후보의 relation type 사용 현황 집계를 고정한다."""

    def test_pending_관계의_이름과_예문을_집계한다(
        self,
        workspace_id: int,
        session_factory: Callable[[], Session],
    ) -> None:
        relation_type = f"{USAGE_PREFIX}depends_on"
        relation_ids = _store_relation_candidates(
            workspace_id,
            session_factory,
            relations=[
                RelationAssertionCandidateDraft(
                    local_key=local_key,
                    source_local_key="e1",
                    target_local_key="e2",
                    relation_type=relation_type,
                    assertion_text=f"{local_key} 의존합니다.",
                )
                for local_key in ("r1", "no_text", "superseded")
            ],
        )
        _patch_candidate(
            session_factory,
            RelationRow,
            relation_ids["no_text"],
            assertion_text=None,
        )
        _patch_candidate(
            session_factory,
            RelationRow,
            relation_ids["superseded"],
            resolution_status="superseded",
        )

        with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
            usage = uow.knowledge_candidates.summarize_relation_usage(
                workspace_id=workspace_id,
            )

        item = {entry.name: entry for entry in usage}[relation_type]
        assert item.usage_count == 2
        # 비어 있는 assertion_text는 예문에 넣지 않는다.
        assert len(item.example_assertions) == 1


class TestPublishConvergedVocabulary:
    """수렴 통과분의 발행이 실 DB에서 어떻게 남는지 고정한다."""

    def _guarded(
        self,
        *,
        predicate_entries: tuple[PredicateEntry, ...] = (),
        relation_entries: tuple[RelationTypeEntry, ...] = (),
        absorptions: tuple[SynonymAbsorption, ...] = (),
        rejections: tuple[GuardRejection, ...] = (),
    ) -> ConvergenceGuardResult:
        return ConvergenceGuardResult(
            predicate_entries=predicate_entries,
            relation_entries=relation_entries,
            absorptions=absorptions,
            rejections=rejections,
            covered_names=tuple(
                entry.name
                for entry in (*predicate_entries, *relation_entries)
            ),
        )

    def test_발행은_버전을_단조_증가시키고_기존을_보존한다(
        self,
        workspace_id: int,
        session_factory: Callable[[], Session],
        uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    ) -> None:
        """v1을 그대로 두고 v2에 기존+신규를 함께 담아야 한다."""
        first = ExtractionVocabulary(
            snapshot_id="v1",
            predicates=("release_month",),
            relation_types=("depends_on",),
        )
        with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
            uow.ontology.ensure(
                workspace_id=workspace_id,
                ontology_id=CONVERGENCE_ONTOLOGY_ID,
                vocabulary=first,
            )
            uow.commit()

        guarded = self._guarded(
            predicate_entries=(
                PredicateEntry(
                    name="deployment_scheduled_on",
                    definition="배포 예정 일자를 담는다.",
                    value_type="date",
                ),
            ),
        )

        outcome = publish_converged_vocabulary(
            guarded,
            workspace_id=workspace_id,
            ontology_id=CONVERGENCE_ONTOLOGY_ID,
            current=first,
            uow=uow_factory(),
        )

        assert outcome.version == "v2"
        assert outcome.added_predicates == ("deployment_scheduled_on",)
        assert outcome.added_relations == ()

        with KnowledgeMaintenanceUnitOfWork(session_factory) as reader:
            stored_first = reader.ontology.get(
                workspace_id=workspace_id,
                ontology_id=CONVERGENCE_ONTOLOGY_ID,
                version="v1",
            )
            stored_second = reader.ontology.get(
                workspace_id=workspace_id,
                ontology_id=CONVERGENCE_ONTOLOGY_ID,
                version="v2",
            )

        assert stored_first == first
        assert stored_second is not None
        assert set(stored_second.predicates) >= set(stored_first.predicates)
        assert stored_second.predicates == (
            "release_month",
            "deployment_scheduled_on",
        )
        assert stored_second.relation_types == ("depends_on",)
        assert stored_second.predicate_entries == guarded.predicate_entries

    def test_신규_0이면_발행하지_않는다(
        self,
        workspace_id: int,
        session_factory: Callable[[], Session],
        uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    ) -> None:
        """사전 내용이 안 바뀌는 라운드는 버전을 만들지 않는다."""
        current = ExtractionVocabulary(
            snapshot_id="v1",
            predicates=("release_month",),
        )
        with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
            uow.ontology.ensure(
                workspace_id=workspace_id,
                ontology_id=CONVERGENCE_ONTOLOGY_ID,
                vocabulary=current,
            )
            uow.commit()

        with KnowledgeMaintenanceUnitOfWork(session_factory) as reader:
            before = reader.ontology.list_versions(
                workspace_id=workspace_id,
                ontology_id=CONVERGENCE_ONTOLOGY_ID,
            )

        # absorption만 통과한 라운드다. 정본 사전은 그대로다.
        guarded = self._guarded(
            absorptions=(
                SynonymAbsorption(
                    candidate_name="release_mon",
                    canonical_name="release_month",
                    rationale="같은 뜻의 축약형이다.",
                ),
            ),
            rejections=(GuardRejection(name="bad", reason="관측 증거 없음"),),
        )

        outcome = publish_converged_vocabulary(
            guarded,
            workspace_id=workspace_id,
            ontology_id=CONVERGENCE_ONTOLOGY_ID,
            current=current,
            uow=uow_factory(),
        )

        assert outcome.version is None
        assert outcome.added_predicates == ()
        assert outcome.added_relations == ()

        with KnowledgeMaintenanceUnitOfWork(session_factory) as reader:
            after = reader.ontology.list_versions(
                workspace_id=workspace_id,
                ontology_id=CONVERGENCE_ONTOLOGY_ID,
            )

        assert after == before

    def test_구_버전_문자열은_계보에_끼지_않는다(
        self,
        workspace_id: int,
        session_factory: Callable[[], Session],
        uow_factory: Callable[[], KnowledgeMaintenanceUnitOfWork],
    ) -> None:
        """`vN` 체계 밖의 이름은 발행 계보의 최신으로 보지 않는다."""
        current = ExtractionVocabulary(
            snapshot_id="round-4",
            predicates=("release_month",),
        )
        with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
            uow.ontology.ensure(
                workspace_id=workspace_id,
                ontology_id=CONVERGENCE_ONTOLOGY_ID,
                vocabulary=ExtractionVocabulary(
                    snapshot_id="2",
                    predicates=("release_month",),
                ),
            )
            uow.ontology.ensure(
                workspace_id=workspace_id,
                ontology_id=CONVERGENCE_ONTOLOGY_ID,
                vocabulary=current,
            )
            uow.commit()

        outcome = publish_converged_vocabulary(
            self._guarded(
                relation_entries=(
                    RelationTypeEntry(
                        name="blocked_by",
                        definition="진행을 막는 대상을 가리킨다.",
                    ),
                ),
            ),
            workspace_id=workspace_id,
            ontology_id=CONVERGENCE_ONTOLOGY_ID,
            current=current,
            uow=uow_factory(),
        )

        assert outcome.version == "v1"
        assert outcome.added_relations == ("blocked_by",)

        with KnowledgeMaintenanceUnitOfWork(session_factory) as reader:
            published = reader.ontology.get(
                workspace_id=workspace_id,
                ontology_id=CONVERGENCE_ONTOLOGY_ID,
                version="v1",
            )

        assert published is not None
        assert published.relation_types == ("blocked_by",)
        assert published.predicates == ("release_month",)
