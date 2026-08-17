"""저장 단계의 행위자 규칙을 fake 포트로 검증한다.

세 규칙 모두 "그 observation의 외부 행위자 metadata가 정확히 하나일 때만"
발동한다. 둘 이상이면 어느 사람을 가리키는지 원문 밖에서 정할 근거가 없다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from types import TracebackType

import pytest

from catchup.knowledge_maintenance.contracts.extraction import EntityCandidateDraft
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import KnowledgeCandidateBatch
from catchup.knowledge_maintenance.contracts.extraction import (
    RelationAssertionCandidateDraft,
)
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionMethod
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionRun
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionRunSpec
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionRunStatus
from catchup.knowledge_maintenance.domain.knowledge_node import KnowledgeNode
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
from catchup.knowledge_maintenance.domain.observation import MetadataEntity
from catchup.knowledge_maintenance.domain.observation import NormalizedObservation
from catchup.knowledge_maintenance.domain.observation import ObservationKind
from catchup.knowledge_maintenance.domain.observation import StoredObservation
from catchup.knowledge_maintenance.domain.observation import content_hash
from catchup.knowledge_maintenance.services.store_knowledge_candidates import (
    store_knowledge_candidates,
)

NOW = datetime(2026, 8, 17, 9, 0, tzinfo=timezone.utc)
WORKSPACE = 1
CONTENT = "문의 본문"
SPEC = ExtractionRunSpec(
    provider="test",
    extractor_version="1",
    ontology_id="test-ontology",
    vocabulary=ExtractionVocabulary(snapshot_id="v1"),
)


@dataclass(frozen=True, slots=True)
class _StoredEntity:
    id: uuid.UUID
    draft: EntityCandidateDraft
    extraction_method: ExtractionMethod


@dataclass(frozen=True, slots=True)
class _StoredClaim:
    id: uuid.UUID
    draft: object
    subject_candidate_id: uuid.UUID
    extraction_method: ExtractionMethod


@dataclass(frozen=True, slots=True)
class _StoredRelation:
    id: uuid.UUID
    draft: RelationAssertionCandidateDraft
    source_candidate_id: uuid.UUID
    target_candidate_id: uuid.UUID
    extraction_method: ExtractionMethod


@dataclass(frozen=True, slots=True)
class _StoredEvidence:
    entity_candidate_id: uuid.UUID | None
    claim_candidate_id: uuid.UUID | None
    relation_candidate_id: uuid.UUID | None


class _FakeCandidateRepository:
    """저장된 후보를 순서대로 모아 두는 최소 저장소다."""

    def __init__(self) -> None:
        self.entities: list[_StoredEntity] = []
        self.claims: list[_StoredClaim] = []
        self.relations: list[_StoredRelation] = []
        self.evidence: list[_StoredEvidence] = []

    def find_succeeded_run(self, **kwargs) -> None:
        del kwargs
        return None

    def start_run(self, *, workspace_id, input_node_id, spec, started_at):
        del spec
        return ExtractionRun(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            input_node_id=input_node_id,
            status=ExtractionRunStatus.RUNNING,
            started_at=started_at,
        )

    def supersede_stale_pending_candidates(self, **kwargs) -> int:
        del kwargs
        return 0

    def add_entity_candidate(
        self, *, workspace_id, run_id, draft, extraction_method, confidence=None
    ) -> uuid.UUID:
        del workspace_id, run_id, confidence
        stored = _StoredEntity(
            id=uuid.uuid4(), draft=draft, extraction_method=extraction_method
        )
        self.entities.append(stored)
        return stored.id

    def add_claim_candidate(
        self,
        *,
        workspace_id,
        run_id,
        draft,
        subject_candidate_id,
        spec,
        extraction_method,
        confidence=None,
    ) -> uuid.UUID:
        del workspace_id, run_id, spec, confidence
        stored = _StoredClaim(
            id=uuid.uuid4(),
            draft=draft,
            subject_candidate_id=subject_candidate_id,
            extraction_method=extraction_method,
        )
        self.claims.append(stored)
        return stored.id

    def add_relation_candidate(
        self,
        *,
        workspace_id,
        run_id,
        draft,
        source_candidate_id,
        target_candidate_id,
        extraction_method,
        confidence=None,
    ) -> uuid.UUID:
        del workspace_id, run_id, confidence
        stored = _StoredRelation(
            id=uuid.uuid4(),
            draft=draft,
            source_candidate_id=source_candidate_id,
            target_candidate_id=target_candidate_id,
            extraction_method=extraction_method,
        )
        self.relations.append(stored)
        return stored.id

    def add_evidence_link(
        self,
        *,
        workspace_id,
        run_id,
        evidence_node_id,
        entity_candidate_id=None,
        claim_candidate_id=None,
        relation_candidate_id=None,
        excerpt=None,
        locator=None,
    ) -> uuid.UUID:
        del workspace_id, run_id, evidence_node_id, excerpt, locator
        self.evidence.append(
            _StoredEvidence(
                entity_candidate_id=entity_candidate_id,
                claim_candidate_id=claim_candidate_id,
                relation_candidate_id=relation_candidate_id,
            )
        )
        return uuid.uuid4()

    def complete_run(self, **kwargs) -> None:
        del kwargs


class _FakeNodeRepository:
    def __init__(self, node: KnowledgeNode) -> None:
        self.node = node

    def get_for_resource(self, *, workspace_id, node_kind, resource_id):
        del workspace_id, node_kind, resource_id
        return self.node


class _FakeOntologyRepository:
    def ensure(self, **kwargs) -> None:
        del kwargs


class _FakeUnitOfWork:
    def __init__(self, node: KnowledgeNode) -> None:
        self.knowledge_candidates = _FakeCandidateRepository()
        self.knowledge_nodes = _FakeNodeRepository(node)
        self.ontology = _FakeOntologyRepository()
        self.committed = False

    def __enter__(self) -> _FakeUnitOfWork:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def commit(self) -> None:
        self.committed = True


@pytest.fixture
def uow() -> _FakeUnitOfWork:
    node = KnowledgeNode(
        id=uuid.uuid4(),
        workspace_id=WORKSPACE,
        node_kind=NodeKind.OBSERVATION,
    )
    return _FakeUnitOfWork(node)


def _observation(*metadata: MetadataEntity) -> StoredObservation:
    return StoredObservation(
        id=uuid.uuid4(),
        workspace_id=WORKSPACE,
        source_version_id=uuid.uuid4(),
        observation=NormalizedObservation(
            normalizer_id="test.normalizer",
            normalizer_version="1",
            observation_kind=ObservationKind.DOCUMENT,
            content=CONTENT,
            content_hash=content_hash(CONTENT),
            metadata_entities=metadata,
            occurred_at=NOW,
        ),
        created_at=NOW,
    )


def _customer_meta(
    external_key: str = "ext-1",
    email: str = "neo@example.com",
    name: str = "팀원A",
) -> MetadataEntity:
    return MetadataEntity(
        entity_type="channel_talk_user",
        external_key=external_key,
        display_name=name,
        attributes={"email": email, "user_type": "member"},
    )


def test_actor_metadata_is_stored_as_customer_candidate(uow) -> None:
    store_knowledge_candidates(
        _observation(_customer_meta()),
        KnowledgeCandidateBatch(),
        spec=SPEC,
        uow=uow,
    )

    (entity,) = uow.knowledge_candidates.entities
    assert entity.draft.proposed_type == "customer"
    assert entity.extraction_method is ExtractionMethod.DETERMINISTIC
    assert entity.draft.attributes["email"] == "neo@example.com"
    assert entity.draft.attributes["actor"]["source_entity_type"] == "channel_talk_user"


def test_manager_metadata_keeps_its_own_type(uow) -> None:
    manager = MetadataEntity(
        entity_type="channel_talk_manager",
        external_key="m-1",
        display_name="상담원",
        attributes={},
    )

    store_knowledge_candidates(
        _observation(manager),
        KnowledgeCandidateBatch(),
        spec=SPEC,
        uow=uow,
    )

    (entity,) = uow.knowledge_candidates.entities
    assert entity.draft.proposed_type == "channel_talk_manager"


def _aliased_batch() -> KnowledgeCandidateBatch:
    return KnowledgeCandidateBatch(
        entities=(
            EntityCandidateDraft(
                local_key="e1",
                proposed_type="feature_request",
                proposed_name="커넥터 요청",
            ),
            EntityCandidateDraft(
                local_key="e2",
                proposed_type="customer",
                proposed_name="고객",
            ),
        ),
        relation_assertions=(
            RelationAssertionCandidateDraft(
                local_key="r1",
                source_local_key="e1",
                target_local_key="e2",
                relation_type="requested_by",
                assertion_text="고객이 요청했다",
            ),
        ),
    )


def test_role_label_customer_is_aliased_to_actor(uow) -> None:
    store_knowledge_candidates(
        _observation(_customer_meta()),
        _aliased_batch(),
        spec=SPEC,
        uow=uow,
    )

    names = [entity.draft.proposed_name for entity in uow.knowledge_candidates.entities]
    assert names == ["팀원A", "커넥터 요청"]

    (relation,) = uow.knowledge_candidates.relations
    actor_id = uow.knowledge_candidates.entities[0].id
    assert relation.target_candidate_id == actor_id
    assert relation.extraction_method is ExtractionMethod.LLM
    # 근거 링크는 저장된 후보 수만큼만 (별칭에 중복 없음): entity 2 + relation 1
    assert len(uow.knowledge_candidates.evidence) == 3


def test_feature_request_without_requested_by_gets_derived_relation(uow) -> None:
    batch = KnowledgeCandidateBatch(
        entities=(
            EntityCandidateDraft(
                local_key="e1",
                proposed_type="feature_request",
                proposed_name="커넥터 요청",
            ),
        ),
    )

    store_knowledge_candidates(
        _observation(_customer_meta()),
        batch,
        spec=SPEC,
        uow=uow,
    )

    (relation,) = uow.knowledge_candidates.relations
    assert relation.draft.local_key == "actor:requested_by:e1"
    assert relation.draft.relation_type == "requested_by"
    assert relation.draft.assertion_text == "팀원A이(가) 이 문의를 남겼다"
    assert relation.extraction_method is ExtractionMethod.DETERMINISTIC
    assert relation.source_candidate_id == uow.knowledge_candidates.entities[1].id
    assert relation.target_candidate_id == uow.knowledge_candidates.entities[0].id
    assert any(
        link.relation_candidate_id == relation.id
        for link in uow.knowledge_candidates.evidence
    )


def test_no_derivation_when_requested_by_already_present(uow) -> None:
    store_knowledge_candidates(
        _observation(_customer_meta()),
        _aliased_batch(),
        spec=SPEC,
        uow=uow,
    )

    assert len(uow.knowledge_candidates.relations) == 1


def test_rules_are_off_when_two_actors_share_the_observation(uow) -> None:
    batch = KnowledgeCandidateBatch(
        entities=(
            EntityCandidateDraft(
                local_key="e1",
                proposed_type="feature_request",
                proposed_name="커넥터 요청",
            ),
            EntityCandidateDraft(
                local_key="e2",
                proposed_type="customer",
                proposed_name="고객",
            ),
        ),
    )

    store_knowledge_candidates(
        _observation(
            _customer_meta("ext-1"),
            _customer_meta("ext-2", "b@x.com", "B"),
        ),
        batch,
        spec=SPEC,
        uow=uow,
    )

    names = [entity.draft.proposed_name for entity in uow.knowledge_candidates.entities]
    assert names == ["팀원A", "B", "커넥터 요청", "고객"]
    assert uow.knowledge_candidates.relations == []


def test_no_actor_means_no_rules(uow) -> None:
    batch = KnowledgeCandidateBatch(
        entities=(
            EntityCandidateDraft(
                local_key="e1",
                proposed_type="feature_request",
                proposed_name="커넥터 요청",
            ),
            EntityCandidateDraft(
                local_key="e2",
                proposed_type="customer",
                proposed_name="고객",
            ),
        ),
    )

    store_knowledge_candidates(_observation(), batch, spec=SPEC, uow=uow)

    assert len(uow.knowledge_candidates.entities) == 2
    assert uow.knowledge_candidates.relations == []
