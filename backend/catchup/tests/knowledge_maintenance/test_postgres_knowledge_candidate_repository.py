from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Iterator
from datetime import datetime
from datetime import timezone
from decimal import Decimal

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
from catchup.knowledge_maintenance.contracts.extraction import KnowledgeCandidateBatch
from catchup.knowledge_maintenance.contracts.extraction import (
    RelationAssertionCandidateDraft,
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
from catchup.knowledge_maintenance.services.store_knowledge_candidates import (
    ObservationNodeMissing,
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
    ontology_version="unversioned",
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
    **overrides: object,
) -> StoredObservation:
    """Observation과 그 node까지 실제로 저장한다."""
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
        source_updated_at=NOW,
        observed_at=NOW,
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
