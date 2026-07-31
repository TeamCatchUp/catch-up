from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ColumnElement
from sqlalchemy import Select
from sqlalchemy import cast
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Session

from catchup.db.models import KnowledgeArtifact as KnowledgeArtifactRow
from catchup.db.models import (
    KnowledgeArtifactChangeProposal as KnowledgeArtifactChangeProposalRow,
)
from catchup.db.models import KnowledgeArtifactRevision as KnowledgeArtifactRevisionRow
from catchup.db.models import (
    KnowledgeCandidateEvidenceLink as KnowledgeCandidateEvidenceLinkRow,
)
from catchup.db.models import KnowledgeClaimCandidate as KnowledgeClaimCandidateRow
from catchup.db.models import KnowledgeEntityCandidate as KnowledgeEntityCandidateRow
from catchup.db.models import KnowledgeExtractionRun as KnowledgeExtractionRunRow
from catchup.db.models import (
    KnowledgeMutationOperation as KnowledgeMutationOperationRow,
)
from catchup.db.models import KnowledgeMutationProposal as KnowledgeMutationProposalRow
from catchup.db.models import KnowledgeNode as KnowledgeNodeRow
from catchup.db.models import KnowledgeNodeAlias as KnowledgeNodeAliasRow
from catchup.db.models import KnowledgeOntologySnapshot as KnowledgeOntologySnapshotRow
from catchup.db.models import KnowledgePipelineOutbox as PipelineOutboxRow
from catchup.db.models import (
    KnowledgeRelationAssertionCandidate as KnowledgeRelationCandidateRow,
)
from catchup.db.models import Observation as ObservationRow
from catchup.db.models import SourceVersion as SourceVersionRow
from catchup.knowledge_maintenance.adapters.postgres.mappers import (
    knowledge_node_to_domain,
)
from catchup.knowledge_maintenance.adapters.postgres.mappers import (
    knowledge_node_to_row,
)
from catchup.knowledge_maintenance.adapters.postgres.mappers import (
    observation_to_domain,
)
from catchup.knowledge_maintenance.adapters.postgres.mappers import observation_to_row
from catchup.knowledge_maintenance.adapters.postgres.mappers import (
    source_version_to_domain,
)
from catchup.knowledge_maintenance.adapters.postgres.mappers import (
    source_version_to_row,
)
from catchup.knowledge_maintenance.contracts.extraction import ClaimCandidateDraft
from catchup.knowledge_maintenance.contracts.extraction import EntityCandidateDraft
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import (
    RelationAssertionCandidateDraft,
)
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import deserialize_blocks
from catchup.knowledge_maintenance.domain.artifact import serialize_blocks
from catchup.knowledge_maintenance.domain.artifact import validate_blocks
from catchup.knowledge_maintenance.domain.claim_conflict import StoredClaimCandidate
from catchup.knowledge_maintenance.domain.entity_resolution import anchor_excerpt
from catchup.knowledge_maintenance.domain.evidence import Locator
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    EntityResolutionStatus,
)
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionMethod
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionRun
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionRunSpec
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionRunStatus
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    StoredEntityCandidate,
)
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    StoredMutationProposal,
)
from catchup.knowledge_maintenance.domain.knowledge_node import KnowledgeNode
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
from catchup.knowledge_maintenance.domain.knowledge_node import resource_ref_for
from catchup.knowledge_maintenance.domain.observation import NormalizedObservation
from catchup.knowledge_maintenance.domain.observation import StoredObservation
from catchup.knowledge_maintenance.domain.pipeline_event import FailureKind
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineAggregateType
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineEvent
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineEventStatus
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineEventType
from catchup.knowledge_maintenance.domain.pipeline_event import next_attempt_at
from catchup.knowledge_maintenance.domain.pipeline_event import resolve_failure
from catchup.knowledge_maintenance.domain.source_version import SourceIdentity
from catchup.knowledge_maintenance.domain.source_version import SourceVersion
from catchup.knowledge_maintenance.ports.artifacts import ArtifactProposalConflict
from catchup.knowledge_maintenance.ports.artifacts import EntityCardSource
from catchup.knowledge_maintenance.ports.artifacts import ProposalAlreadyDecided
from catchup.knowledge_maintenance.ports.artifacts import StoredArtifactProposal
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    MergeProposalAlreadyDecided,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    StoredContradictionProposal,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import (
    StoredContradictionValue,
)
from catchup.knowledge_maintenance.ports.mutation_proposals import StoredMergeCandidate
from catchup.knowledge_maintenance.ports.mutation_proposals import StoredMergeProposal
from catchup.knowledge_maintenance.ports.mutation_proposals import StoredOperation
from catchup.knowledge_maintenance.ports.mutation_proposals import StoredPendingProposal
from catchup.knowledge_maintenance.ports.ontology import OntologySnapshotConflict
from catchup.observability.logging import get_logger

logger = get_logger(__name__)


def _identity_matches(
    source_identity: SourceIdentity,
) -> list[ColumnElement[bool]]:
    """복합 identity를 컬럼 비교 조건으로 편다."""
    return [
        SourceVersionRow.entity_type == source_identity.entity_type,
        SourceVersionRow.scope_id == source_identity.scope_id,
        SourceVersionRow.target_id == source_identity.target_id,
        SourceVersionRow.external_document_id
        == source_identity.external_document_id,
    ]


def _contradiction_values(
    raw: object,
) -> tuple[StoredContradictionValue, ...]:
    """판정 근거의 값 목록을 읽는 형태로 옮긴다.

    낡은 metadata에는 값 목록이 없거나 형태가 다를 수 있다. 읽을 수
    없는 항목은 조용히 버리는 대신 통째로 비워, 호출자가 "고를 것이
    없는 안건"으로 다루게 한다.
    """
    if not isinstance(raw, list):
        return ()
    values: list[StoredContradictionValue] = []
    for item in raw:
        if not isinstance(item, Mapping):
            return ()
        try:
            claim_id = uuid.UUID(str(item["claim_id"]))
        except (KeyError, ValueError, TypeError):
            return ()
        values.append(
            StoredContradictionValue(
                claim_id=claim_id,
                value=item.get("value"),
                normalized=_optional_str(item.get("normalized")),
                statement=_optional_str(item.get("statement")),
                observed_at=_optional_str(item.get("observed_at")),
            )
        )
    return tuple(values)


def _optional_str(value: object) -> str | None:
    """문자열로 읽을 수 있으면 문자열로, 아니면 None으로 준다."""
    if value is None:
        return None
    return str(value)


def _mentions_candidate(
    metadata: Mapping[str, object],
    candidate_ids: set[uuid.UUID],
) -> bool:
    """병합 계획서의 멤버 가운데 주어진 후보가 있는지 본다.

    낡은 metadata가 식별자가 아닌 값을 담고 있으면 그 항목만 버린다.
    """
    member_ids = metadata.get("member_ids")
    if not isinstance(member_ids, list):
        return False
    for member_id in member_ids:
        try:
            parsed = uuid.UUID(str(member_id))
        except ValueError:
            continue
        if parsed in candidate_ids:
            return True
    return False


class SqlAlchemySourceVersionRepository:
    """SourceVersion 영속성을 PostgreSQL로 구현한다."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_idempotency_key(
        self,
        *,
        workspace_id: int,
        idempotency_key: str,
    ) -> SourceVersion | None:
        """같은 전달 키로 이미 저장된 SourceVersion을 찾는다."""
        row = self._session.scalar(
            select(SourceVersionRow).where(
                SourceVersionRow.workspace_id == workspace_id,
                SourceVersionRow.idempotency_key == idempotency_key,
            )
        )
        return source_version_to_domain(row) if row is not None else None

    def get_by_source_version(
        self,
        *,
        workspace_id: int,
        source_type: str,
        source_identity: SourceIdentity,
        source_version_key: str,
    ) -> SourceVersion | None:
        """같은 원문의 같은 버전이 이미 저장됐는지 찾는다."""
        row = self._session.scalar(
            select(SourceVersionRow).where(
                SourceVersionRow.workspace_id == workspace_id,
                SourceVersionRow.source_type == source_type,
                *_identity_matches(source_identity),
                SourceVersionRow.source_version_key == source_version_key,
            )
        )
        return source_version_to_domain(row) if row is not None else None

    def get_latest_for_source(
        self,
        *,
        workspace_id: int,
        source_type: str,
        source_identity: SourceIdentity,
    ) -> SourceVersion | None:
        """같은 원문에서 가장 최근에 갱신된 SourceVersion을 찾는다."""
        row = self._session.scalar(
            select(SourceVersionRow)
            .where(
                SourceVersionRow.workspace_id == workspace_id,
                SourceVersionRow.source_type == source_type,
                *_identity_matches(source_identity),
            )
            .order_by(
                func.coalesce(
                    SourceVersionRow.source_updated_at,
                    SourceVersionRow.observed_at,
                ).desc()
            )
            .limit(1)
        )
        return source_version_to_domain(row) if row is not None else None

    def add(self, source_version: SourceVersion) -> None:
        """SourceVersion을 현재 transaction에 추가한다.

        여기서 flush하지 않는다. 같은 transaction에서 Observation을 이어
        넣어도 SQLAlchemy가 메타데이터의 ForeignKeyConstraint를 읽어 삽입
        순서를 정렬하므로, ORM relationship을 선언하지 않아도 원문이 먼저
        나간다. autoflush가 조회 직전에도 flush한다.
        """
        self._session.add(source_version_to_row(source_version))


class SqlAlchemyObservationRepository:
    """Observation 영속성을 PostgreSQL로 구현한다."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_normalizer(
        self,
        *,
        workspace_id: int,
        source_version_id: uuid.UUID,
        normalizer_id: str,
        normalizer_version: str,
    ) -> StoredObservation | None:
        """같은 원문을 같은 정규화 계약으로 만든 결과를 찾는다."""
        row = self._session.scalar(
            select(ObservationRow).where(
                ObservationRow.workspace_id == workspace_id,
                ObservationRow.source_version_id == source_version_id,
                ObservationRow.normalizer_id == normalizer_id,
                ObservationRow.normalizer_version == normalizer_version,
            )
        )
        return observation_to_domain(row) if row is not None else None

    def list_for_source_version(
        self,
        *,
        workspace_id: int,
        source_version_id: uuid.UUID,
    ) -> tuple[StoredObservation, ...]:
        """한 원문에서 나온 정규화 결과를 모두 찾는다.

        정규화 계약이 바뀌면 같은 원문에 여러 Observation이 쌓인다.

        `created_at`은 transaction 시작 시각이라 한 transaction에서 여러 건을
        남기면 값이 같다. 그때 `id`로 순서를 가르면 uuid4라 실행마다 달라지므로
        계약 이름과 버전을 tie-break로 쓴다.
        """
        rows = self._session.scalars(
            select(ObservationRow)
            .where(
                ObservationRow.workspace_id == workspace_id,
                ObservationRow.source_version_id == source_version_id,
            )
            .order_by(
                ObservationRow.created_at,
                ObservationRow.normalizer_id,
                ObservationRow.normalizer_version,
            )
        )
        return tuple(observation_to_domain(row) for row in rows)

    def add(
        self,
        *,
        workspace_id: int,
        source_version_id: uuid.UUID,
        observation: NormalizedObservation,
    ) -> StoredObservation:
        """정규화 결과를 새 record로 남긴다.

        식별자를 여기서 발급한다. normalizer는 무엇이 어디에 저장되는지
        모르기 때문이다. flush로 `created_at` server default를 받아 온다.
        """
        row = observation_to_row(
            observation_id=uuid.uuid4(),
            workspace_id=workspace_id,
            source_version_id=source_version_id,
            observation=observation,
        )
        self._session.add(row)
        self._session.flush()
        return observation_to_domain(row)


class SqlAlchemyKnowledgeNodeRepository:
    """graph node identity의 영속성을 PostgreSQL로 구현한다."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_for_resource(
        self,
        *,
        workspace_id: int,
        node_kind: NodeKind,
        resource_id: uuid.UUID,
    ) -> KnowledgeNode | None:
        """record 하나에 대응하는 node를 찾는다."""
        row = self._session.scalar(
            select(KnowledgeNodeRow).where(
                KnowledgeNodeRow.workspace_id == workspace_id,
                KnowledgeNodeRow.resource_type == node_kind.value,
                KnowledgeNodeRow.resource_id == str(resource_id),
            )
        )
        return knowledge_node_to_domain(row) if row is not None else None

    def ensure_for_resource(
        self,
        *,
        workspace_id: int,
        node_kind: NodeKind,
        resource_id: uuid.UUID,
        display_name: str | None = None,
    ) -> KnowledgeNode:
        """record 하나에 대응하는 node를 만들거나 이미 있는 것을 돌려준다."""
        found = self.get_for_resource(
            workspace_id=workspace_id,
            node_kind=node_kind,
            resource_id=resource_id,
        )
        if found is not None:
            return found

        row = knowledge_node_to_row(
            KnowledgeNode(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                node_kind=node_kind,
                resource=resource_ref_for(node_kind, resource_id),
                display_name=display_name,
            )
        )
        self._session.add(row)
        self._session.flush()
        return knowledge_node_to_domain(row)

    def get_entity_by_canonical_key(
        self,
        *,
        workspace_id: int,
        canonical_key: str,
    ) -> KnowledgeNode | None:
        """canonical key로 entity 노드를 찾는다."""
        row = self._session.scalar(
            select(KnowledgeNodeRow).where(
                KnowledgeNodeRow.workspace_id == workspace_id,
                KnowledgeNodeRow.node_kind == NodeKind.ENTITY.value,
                KnowledgeNodeRow.canonical_key == canonical_key,
            )
        )
        return knowledge_node_to_domain(row) if row is not None else None

    def create_entity_node(
        self,
        *,
        workspace_id: int,
        entity_type: str,
        canonical_key: str | None,
        display_name: str,
    ) -> KnowledgeNode:
        """canonical entity 노드를 발급한다."""
        row = knowledge_node_to_row(
            KnowledgeNode(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                node_kind=NodeKind.ENTITY,
                entity_type=entity_type,
                canonical_key=canonical_key,
                display_name=display_name,
            )
        )
        self._session.add(row)
        self._session.flush()
        return knowledge_node_to_domain(row)

    def add_alias(
        self,
        *,
        workspace_id: int,
        node_id: uuid.UUID,
        alias: str,
        normalized_alias: str,
        source: str,
    ) -> None:
        """노드에 이름 단서를 남긴다. 같은 정규화 alias면 넘어간다."""
        exists = self._session.scalar(
            select(KnowledgeNodeAliasRow.id).where(
                KnowledgeNodeAliasRow.workspace_id == workspace_id,
                KnowledgeNodeAliasRow.node_id == node_id,
                KnowledgeNodeAliasRow.normalized_alias == normalized_alias,
            )
        )
        if exists is not None:
            return
        self._session.add(
            KnowledgeNodeAliasRow(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                node_id=node_id,
                alias=alias,
                normalized_alias=normalized_alias,
                source=source,
            )
        )
        self._session.flush()


class SqlAlchemyKnowledgeCandidateRepository:
    """추출 결과의 영속성을 PostgreSQL로 구현한다."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def start_run(
        self,
        *,
        workspace_id: int,
        input_node_id: uuid.UUID,
        spec: ExtractionRunSpec,
        started_at: datetime,
    ) -> ExtractionRun:
        """LLM을 부르기 전에 실행 기록을 먼저 확보한다."""
        row = KnowledgeExtractionRunRow(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            input_node_id=input_node_id,
            provider=spec.provider,
            model=spec.model,
            extractor_version=spec.extractor_version,
            prompt_version=spec.prompt_version,
            ontology_id=spec.ontology_id,
            ontology_version=spec.ontology_version,
            status=ExtractionRunStatus.RUNNING.value,
            started_at=started_at,
        )
        self._session.add(row)
        self._session.flush()
        return ExtractionRun(
            id=row.id,
            workspace_id=row.workspace_id,
            input_node_id=row.input_node_id,
            status=ExtractionRunStatus(row.status),
            started_at=row.started_at,
        )

    def complete_run(
        self,
        *,
        run_id: uuid.UUID,
        status: ExtractionRunStatus,
        completed_at: datetime,
        raw_output: dict | None = None,
        error: str | None = None,
    ) -> None:
        """실행을 끝맺는다. 실패한 출력도 남긴다."""
        self._session.execute(
            update(KnowledgeExtractionRunRow)
            .where(KnowledgeExtractionRunRow.id == run_id)
            .values(
                status=status.value,
                completed_at=completed_at,
                raw_output=raw_output,
                error=error,
            )
        )

    def find_succeeded_run(
        self,
        *,
        workspace_id: int,
        input_node_id: uuid.UUID,
        spec: ExtractionRunSpec,
    ) -> ExtractionRun | None:
        """같은 입력을 같은 계약으로 이미 성공시킨 실행을 찾는다.

        계약을 이루는 것은 추출기 버전·프롬프트·모델·어휘 스냅샷이다. 하나라도
        달라지면 다른 결과가 나올 수 있으므로 다시 추출해야 한다.
        """
        row = self._session.scalar(
            select(KnowledgeExtractionRunRow).where(
                KnowledgeExtractionRunRow.workspace_id == workspace_id,
                KnowledgeExtractionRunRow.input_node_id == input_node_id,
                KnowledgeExtractionRunRow.status
                == ExtractionRunStatus.SUCCEEDED.value,
                KnowledgeExtractionRunRow.extractor_version
                == spec.extractor_version,
                KnowledgeExtractionRunRow.prompt_version == spec.prompt_version,
                KnowledgeExtractionRunRow.model == spec.model,
                KnowledgeExtractionRunRow.ontology_id == spec.ontology_id,
                KnowledgeExtractionRunRow.ontology_version
                == spec.ontology_version,
            )
        )
        if row is None:
            return None
        return ExtractionRun(
            id=row.id,
            workspace_id=row.workspace_id,
            input_node_id=row.input_node_id,
            status=ExtractionRunStatus(row.status),
            started_at=row.started_at,
            completed_at=row.completed_at,
        )

    def add_entity_candidate(
        self,
        *,
        workspace_id: int,
        run_id: uuid.UUID,
        draft: EntityCandidateDraft,
        extraction_method: ExtractionMethod,
        confidence: Decimal | None = None,
    ) -> uuid.UUID:
        """Entity 후보를 남기고 발급한 식별자를 돌려준다."""
        row = KnowledgeEntityCandidateRow(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            extraction_run_id=run_id,
            local_key=draft.local_key,
            proposed_type=draft.proposed_type,
            proposed_name=draft.proposed_name,
            extraction_method=extraction_method.value,
            confidence=confidence,
            raw_payload=draft.model_dump(mode="json"),
        )
        self._session.add(row)
        self._session.flush()
        return row.id

    def add_claim_candidate(
        self,
        *,
        workspace_id: int,
        run_id: uuid.UUID,
        draft: ClaimCandidateDraft,
        subject_candidate_id: uuid.UUID,
        spec: ExtractionRunSpec,
        extraction_method: ExtractionMethod,
        confidence: Decimal | None = None,
    ) -> uuid.UUID:
        """Claim 후보를 남긴다. subject는 이미 저장된 Entity 후보를 가리킨다."""
        payload = draft.model_dump(mode="json")
        row = KnowledgeClaimCandidateRow(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            extraction_run_id=run_id,
            local_key=draft.local_key,
            subject_entity_candidate_id=subject_candidate_id,
            subject_node_id=None,
            predicate=draft.predicate,
            value_type=draft.value_type,
            value=payload["value"],
            value_hash=_json_hash(payload["value"]),
            statement=draft.statement,
            valid_from=draft.valid_from,
            valid_to=draft.valid_to,
            ontology_id=spec.ontology_id,
            ontology_version=spec.ontology_version,
            extraction_method=extraction_method.value,
            confidence=confidence,
            raw_payload=payload,
        )
        self._session.add(row)
        self._session.flush()
        return row.id

    def add_relation_candidate(
        self,
        *,
        workspace_id: int,
        run_id: uuid.UUID,
        draft: RelationAssertionCandidateDraft,
        source_candidate_id: uuid.UUID,
        target_candidate_id: uuid.UUID,
        extraction_method: ExtractionMethod,
        confidence: Decimal | None = None,
    ) -> uuid.UUID:
        """관계 후보를 남긴다. 양 끝은 이미 저장된 Entity 후보를 가리킨다."""
        row = KnowledgeRelationCandidateRow(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            extraction_run_id=run_id,
            local_key=draft.local_key,
            source_entity_candidate_id=source_candidate_id,
            source_node_id=None,
            target_entity_candidate_id=target_candidate_id,
            target_node_id=None,
            relation_type=draft.relation_type,
            assertion_text=draft.assertion_text,
            valid_from=draft.valid_from,
            valid_to=draft.valid_to,
            extraction_method=extraction_method.value,
            confidence=confidence,
            raw_payload=draft.model_dump(mode="json"),
        )
        self._session.add(row)
        self._session.flush()
        return row.id

    def add_evidence_link(
        self,
        *,
        workspace_id: int,
        run_id: uuid.UUID,
        evidence_node_id: uuid.UUID,
        entity_candidate_id: uuid.UUID | None = None,
        claim_candidate_id: uuid.UUID | None = None,
        relation_candidate_id: uuid.UUID | None = None,
        excerpt: str | None = None,
        locator: Locator | None = None,
    ) -> uuid.UUID:
        """후보가 어떤 Observation에서 나왔는지 잇는다."""
        row = KnowledgeCandidateEvidenceLinkRow(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            extraction_run_id=run_id,
            entity_candidate_id=entity_candidate_id,
            claim_candidate_id=claim_candidate_id,
            relation_assertion_candidate_id=relation_candidate_id,
            evidence_node_id=evidence_node_id,
            evidence_role="supports",
            excerpt=excerpt,
            locator=asdict(locator) if locator is not None else {},
        )
        self._session.add(row)
        self._session.flush()
        return row.id

    def find_pending_entity_candidates(
        self,
        *,
        workspace_id: int,
    ) -> tuple[StoredEntityCandidate, ...]:
        """아직 해소되지 않은 entity 후보를 source_type과 함께 읽는다.

        source_type은 후보 → 실행 → 입력 Observation 노드 → Observation →
        SourceVersion 경로로 얻는다. 결정론 canonical key가 source를
        접두로 요구하기 때문이다.
        """
        statement = (
            select(
                KnowledgeEntityCandidateRow,
                SourceVersionRow.source_type,
                ObservationRow.normalized_content,
            )
            .join(
                KnowledgeExtractionRunRow,
                KnowledgeEntityCandidateRow.extraction_run_id
                == KnowledgeExtractionRunRow.id,
            )
            .join(
                KnowledgeNodeRow,
                KnowledgeExtractionRunRow.input_node_id == KnowledgeNodeRow.id,
            )
            .join(
                ObservationRow,
                ObservationRow.id
                == cast(KnowledgeNodeRow.resource_id, PgUUID),
            )
            .join(
                SourceVersionRow,
                ObservationRow.source_version_id == SourceVersionRow.id,
            )
            .where(
                KnowledgeEntityCandidateRow.workspace_id == workspace_id,
                KnowledgeEntityCandidateRow.resolution_status
                == EntityResolutionStatus.PENDING.value,
            )
            .order_by(
                KnowledgeEntityCandidateRow.created_at,
                KnowledgeEntityCandidateRow.id,
            )
        )
        return tuple(
            StoredEntityCandidate(
                id=row.id,
                run_id=row.extraction_run_id,
                local_key=row.local_key,
                proposed_type=row.proposed_type,
                proposed_name=row.proposed_name,
                extraction_method=ExtractionMethod(row.extraction_method),
                raw_payload=row.raw_payload,
                source_type=source_type,
                created_at=row.created_at,
                observation_excerpt=(
                    anchor_excerpt(content, row.proposed_name)
                    if content is not None
                    else None
                ),
            )
            for row, source_type, content in (
                self._session.execute(statement).all()
            )
        )

    def find_claim_candidates(
        self,
        *,
        workspace_id: int,
    ) -> tuple[StoredClaimCandidate, ...]:
        """claim 후보를 관찰 시각과 subject 해소 결과와 함께 읽는다.

        관찰 시각은 후보 → 실행 → 입력 Observation 노드 → Observation →
        SourceVersion 경로로 얻는다. 어느 주장이 더 최근인지가 모순
        판정의 입력이기 때문이다. subject가 entity 후보라면 그 후보 행을
        outer join해 해소 결과를 함께 담는다. 아직 해소되지 않은 후보도
        빠지면 안 되므로 outer join이어야 한다.
        """
        statement = (
            select(
                KnowledgeClaimCandidateRow,
                SourceVersionRow.observed_at,
                KnowledgeEntityCandidateRow.resolved_node_id,
            )
            .join(
                KnowledgeExtractionRunRow,
                KnowledgeClaimCandidateRow.extraction_run_id
                == KnowledgeExtractionRunRow.id,
            )
            .join(
                KnowledgeNodeRow,
                KnowledgeExtractionRunRow.input_node_id == KnowledgeNodeRow.id,
            )
            .join(
                ObservationRow,
                ObservationRow.id
                == cast(KnowledgeNodeRow.resource_id, PgUUID),
            )
            .join(
                SourceVersionRow,
                ObservationRow.source_version_id == SourceVersionRow.id,
            )
            .outerjoin(
                KnowledgeEntityCandidateRow,
                KnowledgeClaimCandidateRow.subject_entity_candidate_id
                == KnowledgeEntityCandidateRow.id,
            )
            .where(KnowledgeClaimCandidateRow.workspace_id == workspace_id)
            .order_by(
                KnowledgeClaimCandidateRow.created_at,
                KnowledgeClaimCandidateRow.id,
            )
        )
        return tuple(
            StoredClaimCandidate(
                id=row.id,
                subject_entity_candidate_id=row.subject_entity_candidate_id,
                subject_node_id=row.subject_node_id,
                subject_resolved_node_id=resolved_node_id,
                predicate=row.predicate,
                value_type=row.value_type,
                value=row.value,
                statement=row.statement,
                observed_at=observed_at,
            )
            for row, observed_at, resolved_node_id in (
                self._session.execute(statement).all()
            )
        )

    def mark_entity_resolved(
        self,
        *,
        candidate_id: uuid.UUID,
        status: EntityResolutionStatus,
        resolved_node_id: uuid.UUID,
    ) -> None:
        """후보가 어느 canonical 노드로 해소됐는지 기록한다."""
        self._session.execute(
            update(KnowledgeEntityCandidateRow)
            .where(KnowledgeEntityCandidateRow.id == candidate_id)
            .values(
                resolution_status=status.value,
                resolved_node_id=resolved_node_id,
            )
        )
        self._session.flush()

    def get_entity_resolution(
        self,
        *,
        candidate_id: uuid.UUID,
    ) -> tuple[str, uuid.UUID | None] | None:
        """entity 후보의 현재 해소 상태와 노드를 읽는다."""
        row = self._session.execute(
            select(
                KnowledgeEntityCandidateRow.resolution_status,
                KnowledgeEntityCandidateRow.resolved_node_id,
            ).where(KnowledgeEntityCandidateRow.id == candidate_id)
        ).one_or_none()
        if row is None:
            return None
        return (row[0], row[1])

    def get_claim_validity(
        self,
        *,
        claim_id: uuid.UUID,
    ) -> tuple[str, datetime | None, datetime | None] | None:
        """claim 후보의 상태와 유효 구간을 읽는다."""
        row = self._session.execute(
            select(
                KnowledgeClaimCandidateRow.resolution_status,
                KnowledgeClaimCandidateRow.valid_from,
                KnowledgeClaimCandidateRow.valid_to,
            ).where(KnowledgeClaimCandidateRow.id == claim_id)
        ).one_or_none()
        if row is None:
            return None
        return (row[0], row[1], row[2])

    def close_claim(
        self,
        *,
        claim_id: uuid.UUID,
        valid_to: datetime,
    ) -> None:
        """한때 참이었던 claim의 구간을 닫는다.

        resolution_status는 건드리지 않는다. accepted로 남아야 "그때는
        참이었다"를 질의할 수 있다.
        """
        self._session.execute(
            update(KnowledgeClaimCandidateRow)
            .where(
                KnowledgeClaimCandidateRow.id == claim_id,
                KnowledgeClaimCandidateRow.valid_to.is_(None),
            )
            .values(valid_to=valid_to)
        )
        self._session.flush()

    def reject_claim(
        self,
        *,
        claim_id: uuid.UUID,
    ) -> None:
        """지식이 된 적 없는 후보를 탈락시킨다."""
        self._session.execute(
            update(KnowledgeClaimCandidateRow)
            .where(
                KnowledgeClaimCandidateRow.id == claim_id,
                KnowledgeClaimCandidateRow.resolution_status == "pending",
            )
            .values(resolution_status="rejected")
        )
        self._session.flush()

    def accept_claims(
        self,
        *,
        claim_ids: Sequence[uuid.UUID],
    ) -> int:
        """claim 후보들을 canonical 지식으로 확정한다.

        valid_from의 재료는 근거 관찰의 occurred_at이다. claim →
        extraction run → 입력 observation 노드 → observation 행으로
        거슬러 올라가 읽는다. 없으면 NULL로 둔다 — 시간 정보의 품질이
        확정을 막으면 안 된다.
        """
        unique_ids = list(dict.fromkeys(claim_ids))
        if not unique_ids:
            return 0
        pending_rows = self._session.execute(
            select(
                KnowledgeClaimCandidateRow.id,
                ObservationRow.occurred_at,
            )
            .join(
                KnowledgeExtractionRunRow,
                KnowledgeExtractionRunRow.id
                == KnowledgeClaimCandidateRow.extraction_run_id,
            )
            .join(
                KnowledgeNodeRow,
                KnowledgeNodeRow.id
                == KnowledgeExtractionRunRow.input_node_id,
            )
            .outerjoin(
                ObservationRow,
                ObservationRow.id
                == cast(KnowledgeNodeRow.resource_id, PgUUID),
            )
            .where(
                KnowledgeClaimCandidateRow.id.in_(unique_ids),
                KnowledgeClaimCandidateRow.resolution_status == "pending",
            )
        ).all()

        accepted = 0
        for claim_id, occurred_at in pending_rows:
            result = self._session.execute(
                update(KnowledgeClaimCandidateRow)
                .where(
                    KnowledgeClaimCandidateRow.id == claim_id,
                    KnowledgeClaimCandidateRow.resolution_status
                    == "pending",
                )
                .values(
                    resolution_status="accepted",
                    valid_from=func.coalesce(
                        KnowledgeClaimCandidateRow.valid_from,
                        occurred_at,
                    ),
                )
            )
            accepted += result.rowcount
        self._session.flush()
        return accepted


class SqlAlchemyMutationProposalRepository:
    """mutation proposal의 영속성을 PostgreSQL로 구현한다."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_pending_by_idempotency_key(
        self,
        *,
        workspace_id: int,
        idempotency_key: str,
    ) -> StoredMutationProposal | None:
        """같은 검토 단위로 이미 열려 있는 proposal을 찾는다."""
        row = self._session.scalar(
            select(KnowledgeMutationProposalRow).where(
                KnowledgeMutationProposalRow.workspace_id == workspace_id,
                KnowledgeMutationProposalRow.idempotency_key
                == idempotency_key,
                KnowledgeMutationProposalRow.status == "pending",
            )
        )
        if row is None:
            return None
        return StoredMutationProposal(
            id=row.id,
            idempotency_key=row.idempotency_key,
            status=row.status,
            resolver_metadata=row.resolver_metadata,
        )

    def abandon(self, *, proposal_id: uuid.UUID) -> None:
        """proposal을 접는다."""
        self._session.execute(
            update(KnowledgeMutationProposalRow)
            .where(KnowledgeMutationProposalRow.id == proposal_id)
            .values(status="abandoned")
        )
        self._session.flush()

    def list_pending_duplicates(
        self,
        *,
        workspace_id: int,
    ) -> list[StoredMergeProposal]:
        """검토 대기 중인 병합 안건을 후보 상세와 함께 모은다."""
        proposal_rows = self._session.scalars(
            select(KnowledgeMutationProposalRow)
            .where(
                KnowledgeMutationProposalRow.workspace_id == workspace_id,
                KnowledgeMutationProposalRow.proposal_kind == "duplicate",
                KnowledgeMutationProposalRow.status == "pending",
            )
            .order_by(KnowledgeMutationProposalRow.created_at)
        ).all()
        if not proposal_rows:
            return []

        proposal_ids = [row.id for row in proposal_rows]
        member_rows = self._session.execute(
            select(
                KnowledgeMutationOperationRow.proposal_id,
                KnowledgeEntityCandidateRow,
            )
            .join(
                KnowledgeEntityCandidateRow,
                KnowledgeEntityCandidateRow.id
                == KnowledgeMutationOperationRow.entity_candidate_id,
            )
            .where(
                KnowledgeMutationOperationRow.workspace_id == workspace_id,
                KnowledgeEntityCandidateRow.workspace_id == workspace_id,
                KnowledgeMutationOperationRow.proposal_id.in_(proposal_ids),
            )
            .order_by(
                KnowledgeMutationOperationRow.proposal_id,
                KnowledgeMutationOperationRow.sequence,
            )
        ).all()

        members: dict[uuid.UUID, list[StoredMergeCandidate]] = {}
        for proposal_id, candidate in member_rows:
            members.setdefault(proposal_id, []).append(
                StoredMergeCandidate(
                    id=candidate.id,
                    proposed_name=candidate.proposed_name,
                    proposed_type=candidate.proposed_type,
                    resolution_status=candidate.resolution_status,
                )
            )
        return [
            StoredMergeProposal(
                id=row.id,
                summary=row.summary,
                resolver_metadata=row.resolver_metadata,
                candidates=tuple(members.get(row.id, ())),
            )
            for row in proposal_rows
        ]

    def mark_merge_approved(
        self,
        *,
        workspace_id: int,
        proposal_id: uuid.UUID,
        reviewer: str,
    ) -> None:
        """병합 안건을 승인으로 끝맺는다.

        Raises:
            MergeProposalAlreadyDecided: 계류 중인 병합 안건이 아니다.
        """
        self._decide_merge(
            workspace_id=workspace_id,
            proposal_id=proposal_id,
            status="approved",
            reviewer=reviewer,
        )

    def mark_merge_rejected(
        self,
        *,
        workspace_id: int,
        proposal_id: uuid.UUID,
        reviewer: str,
        reason: str,
    ) -> None:
        """병합 안건을 사유와 함께 반려로 끝맺는다.

        Raises:
            MergeProposalAlreadyDecided: 계류 중인 병합 안건이 아니다.
        """
        self._decide_merge(
            workspace_id=workspace_id,
            proposal_id=proposal_id,
            status="rejected",
            reviewer=reviewer,
            rejection_reason=reason,
        )

    def list_pending_contradictions(
        self,
        *,
        workspace_id: int,
    ) -> list[StoredContradictionProposal]:
        """검토 대기 중인 모순 안건을 값 후보와 함께 모은다."""
        rows = self._session.scalars(
            select(KnowledgeMutationProposalRow)
            .where(
                KnowledgeMutationProposalRow.workspace_id == workspace_id,
                KnowledgeMutationProposalRow.proposal_kind
                == "contradiction",
                KnowledgeMutationProposalRow.status == "pending",
            )
            .order_by(KnowledgeMutationProposalRow.created_at)
        ).all()
        found: list[StoredContradictionProposal] = []
        for row in rows:
            metadata = row.resolver_metadata or {}
            values = _contradiction_values(metadata.get("values"))
            if not values:
                # 값 후보를 읽을 수 없는 안건은 사람이 고를 것이 없다.
                continue
            found.append(
                StoredContradictionProposal(
                    id=row.id,
                    predicate=str(metadata.get("predicate") or ""),
                    subject_key=str(metadata.get("subject_key") or ""),
                    summary=row.summary,
                    values=values,
                )
            )
        return found

    def record_contradiction_decision(
        self,
        *,
        workspace_id: int,
        proposal_id: uuid.UUID,
        decision: Mapping[str, object],
        supersede_targets: Sequence[tuple[uuid.UUID, Mapping[str, object]]],
        reviewer: str,
    ) -> None:
        """모순 결정을 저널에 남기고 적용 명령을 후생성한다.

        Raises:
            MergeProposalAlreadyDecided: 계류 중인 모순 안건이 아니다.
        """
        row = self._session.scalar(
            select(KnowledgeMutationProposalRow).where(
                KnowledgeMutationProposalRow.workspace_id == workspace_id,
                KnowledgeMutationProposalRow.id == proposal_id,
                KnowledgeMutationProposalRow.proposal_kind
                == "contradiction",
                KnowledgeMutationProposalRow.status == "pending",
            )
        )
        if row is None:
            raise MergeProposalAlreadyDecided(str(proposal_id))

        # 판정 근거를 남긴 채 결정만 더한다. 기존 키를 덮으면 무엇을
        # 보고 정했는지가 사라진다.
        metadata = dict(row.resolver_metadata or {})
        metadata["decision"] = dict(decision)
        row.resolver_metadata = metadata
        row.status = "approved"
        row.reviewer = reviewer
        row.reviewed_at = func.now()

        for sequence, (claim_id, data) in enumerate(
            supersede_targets, start=1
        ):
            self._session.add(
                KnowledgeMutationOperationRow(
                    id=uuid.uuid4(),
                    workspace_id=workspace_id,
                    proposal_id=proposal_id,
                    sequence=sequence,
                    operation_type="supersede_claim",
                    claim_candidate_id=claim_id,
                    operation_data=dict(data),
                )
            )
        self._session.flush()

    def find_approved_proposals_with_operations(
        self,
        *,
        workspace_id: int,
    ) -> list[tuple[uuid.UUID, tuple[StoredOperation, ...]]]:
        """승인됐지만 아직 적용되지 않은 안건을 명령과 함께 모은다."""
        proposal_ids = self._session.scalars(
            select(KnowledgeMutationProposalRow.id)
            .where(
                KnowledgeMutationProposalRow.workspace_id == workspace_id,
                KnowledgeMutationProposalRow.status == "approved",
            )
            .order_by(KnowledgeMutationProposalRow.created_at)
        ).all()
        if not proposal_ids:
            return []
        operation_rows = self._session.scalars(
            select(KnowledgeMutationOperationRow)
            .where(
                KnowledgeMutationOperationRow.workspace_id == workspace_id,
                KnowledgeMutationOperationRow.proposal_id.in_(proposal_ids),
            )
            .order_by(
                KnowledgeMutationOperationRow.proposal_id,
                KnowledgeMutationOperationRow.sequence,
            )
        ).all()
        grouped: dict[uuid.UUID, list[StoredOperation]] = {}
        for row in operation_rows:
            grouped.setdefault(row.proposal_id, []).append(
                StoredOperation(
                    sequence=row.sequence,
                    operation_type=row.operation_type,
                    entity_candidate_id=row.entity_candidate_id,
                    operation_data=row.operation_data or {},
                )
            )
        return [
            (proposal_id, tuple(grouped.get(proposal_id, ())))
            for proposal_id in proposal_ids
        ]

    def mark_applied(
        self,
        *,
        workspace_id: int,
        proposal_id: uuid.UUID,
    ) -> None:
        """안건을 적용 완료로 끝맺고 applied_at을 기록한다.

        Raises:
            MergeProposalAlreadyDecided: approved 상태가 아니다.
        """
        result = self._session.execute(
            update(KnowledgeMutationProposalRow)
            .where(
                KnowledgeMutationProposalRow.workspace_id == workspace_id,
                KnowledgeMutationProposalRow.id == proposal_id,
                KnowledgeMutationProposalRow.status == "approved",
            )
            .values(status="applied", applied_at=func.now())
        )
        if result.rowcount != 1:
            raise MergeProposalAlreadyDecided(str(proposal_id))
        self._session.flush()

    def _decide_merge(
        self,
        *,
        workspace_id: int,
        proposal_id: uuid.UUID,
        status: str,
        reviewer: str,
        rejection_reason: str | None = None,
    ) -> None:
        """결정 UPDATE를 계류 행 하나로 한정한다.

        status='pending' 조건과 rowcount 검사가 결정 경합의 방어선이다.
        잠금 없는 사전 확인이 없으므로, 두 결정이 동시에 와도 UPDATE의
        행 재평가에서 한쪽만 1행을 얻는다.
        """
        result = self._session.execute(
            update(KnowledgeMutationProposalRow)
            .where(
                KnowledgeMutationProposalRow.workspace_id == workspace_id,
                KnowledgeMutationProposalRow.id == proposal_id,
                KnowledgeMutationProposalRow.proposal_kind == "duplicate",
                KnowledgeMutationProposalRow.status == "pending",
            )
            .values(
                status=status,
                reviewer=reviewer,
                reviewed_at=func.now(),
                rejection_reason=rejection_reason,
            )
        )
        if result.rowcount != 1:
            raise MergeProposalAlreadyDecided(str(proposal_id))
        self._session.flush()

    def find_pending_duplicate_groups(
        self,
        *,
        workspace_id: int,
    ) -> dict[uuid.UUID, uuid.UUID]:
        """아직 열려 있는 병합 계획서의 멤버를 계획서로 되짚는다.

        member_ids를 SQL에서 펼치지 않고 Python에서 읽는다. 열려 있는
        계획서의 수가 작아 이득이 없고, JSONB 배열을 펼치는 질의는 읽기
        어렵기 때문이다.
        """
        rows = self._session.scalars(
            select(KnowledgeMutationProposalRow).where(
                KnowledgeMutationProposalRow.workspace_id == workspace_id,
                KnowledgeMutationProposalRow.proposal_kind == "duplicate",
                KnowledgeMutationProposalRow.status == "pending",
            )
        ).all()
        groups: dict[uuid.UUID, uuid.UUID] = {}
        for row in rows:
            member_ids = (row.resolver_metadata or {}).get("member_ids")
            if not isinstance(member_ids, list):
                continue
            for member_id in member_ids:
                try:
                    groups[uuid.UUID(str(member_id))] = row.id
                except ValueError:
                    # 낡은 metadata가 식별자가 아닌 값을 담고 있으면 버린다.
                    continue
        return groups

    def find_pending_contradiction_proposals(
        self,
        *,
        workspace_id: int,
    ) -> tuple[tuple[uuid.UUID, str, str | None], ...]:
        """열려 있는 모순 계획서를 식별자·key·predicate로 되짚는다.

        proposal_kind로 거른다. detector로 거르면 판정기 이름이 바뀐 뒤
        옛 이름으로 쓴 계획서가 회수 대상에서 빠져 영원히 남는다.

        predicate는 resolver_metadata에서 읽는다. 값이 문자열이 아니면
        None으로 준다. 호출자가 사전과 견줄 수 없는 값이기 때문이다.
        """
        rows = self._session.scalars(
            select(KnowledgeMutationProposalRow).where(
                KnowledgeMutationProposalRow.workspace_id == workspace_id,
                KnowledgeMutationProposalRow.proposal_kind
                == "contradiction",
                KnowledgeMutationProposalRow.status == "pending",
            )
        ).all()
        found: list[tuple[uuid.UUID, str, str | None]] = []
        for row in rows:
            predicate = (row.resolver_metadata or {}).get("predicate")
            found.append(
                (
                    row.id,
                    row.idempotency_key,
                    predicate if isinstance(predicate, str) else None,
                )
            )
        return tuple(found)

    def find_pending_for_subject_node(
        self,
        *,
        workspace_id: int,
        node_id: uuid.UUID,
    ) -> list[StoredPendingProposal]:
        """어떤 canonical 노드에 걸려 있는 계류 안건을 모은다.

        모순은 판정 근거의 subject_key로, 병합은 멤버 후보의 해소 결과로
        가려낸다. 판정 근거가 JSONB라 걸러내기를 Python에서 한다. 열려
        있는 계획서의 수가 작아 이득이 없고, `find_pending_duplicate_groups`
        도 같은 이유로 그렇게 읽는다.

        workspace로 먼저 좁힌다. 노드 식별자가 UUID라 정확성은 그것만으로도
        지켜지지만, 이 저장소의 다른 질의가 모두 workspace를 경계로 삼고
        검토 큐 인덱스도 workspace_id를 앞세우기 때문이다.

        순서를 식별자로 고정한다. 이 목록이 문서 본문의 순서가 되므로
        실행마다 흔들리면 같은 내용이 다른 지문을 낳는다.
        """
        candidate_ids = set(
            self._session.scalars(
                select(KnowledgeEntityCandidateRow.id).where(
                    KnowledgeEntityCandidateRow.workspace_id == workspace_id,
                    KnowledgeEntityCandidateRow.resolved_node_id == node_id,
                )
            ).all()
        )
        rows = self._session.scalars(
            select(KnowledgeMutationProposalRow)
            .where(
                KnowledgeMutationProposalRow.workspace_id == workspace_id,
                KnowledgeMutationProposalRow.status == "pending",
                KnowledgeMutationProposalRow.proposal_kind.in_(
                    ("contradiction", "duplicate")
                ),
            )
            .order_by(KnowledgeMutationProposalRow.id)
        ).all()

        found: list[StoredPendingProposal] = []
        subject_key = f"node:{node_id}"
        for row in rows:
            metadata = row.resolver_metadata or {}
            if row.proposal_kind == "contradiction":
                if metadata.get("subject_key") != subject_key:
                    continue
            elif not _mentions_candidate(metadata, candidate_ids):
                continue
            found.append(
                StoredPendingProposal(
                    id=row.id,
                    proposal_kind=row.proposal_kind,
                    summary=row.summary,
                    resolver_metadata=metadata,
                )
            )
        return found

    def add_contradiction_proposal(
        self,
        *,
        workspace_id: int,
        idempotency_key: str,
        trigger_claim_candidate_id: uuid.UUID,
        detector: str,
        detector_version: str,
        summary: str,
        resolver_metadata: Mapping[str, JsonValue],
    ) -> uuid.UUID:
        """같은 대상의 주장끼리 값이 어긋난다는 사실을 계획서로 남긴다.

        `add_duplicate_proposal`과 같이 같은 key의 행이 있으면 상태와
        무관하게 되살려 갈아끼운다. `(workspace_id, idempotency_key)`
        UNIQUE가 상태를 구분하지 않기 때문이다.

        trigger는 셋 중 정확히 하나만 채워야 하므로 entity trigger를
        비운다. operation은 만들지 않고, 되살린 행에 남아 있던 것은
        지운다.
        """
        existing = self._session.scalar(
            select(KnowledgeMutationProposalRow).where(
                KnowledgeMutationProposalRow.workspace_id == workspace_id,
                KnowledgeMutationProposalRow.idempotency_key
                == idempotency_key,
            )
        )
        if existing is not None:
            proposal_id = existing.id
            existing.status = "pending"
            existing.proposal_kind = "contradiction"
            existing.trigger_entity_candidate_id = None
            existing.trigger_relation_assertion_candidate_id = None
            existing.trigger_claim_candidate_id = trigger_claim_candidate_id
            existing.detector = detector
            existing.detector_version = detector_version
            existing.summary = summary
            existing.resolver_metadata = dict(resolver_metadata)
            self._session.execute(
                KnowledgeMutationOperationRow.__table__.delete().where(
                    KnowledgeMutationOperationRow.proposal_id == proposal_id
                )
            )
            self._session.flush()
            return proposal_id

        proposal_id = uuid.uuid4()
        self._session.add(
            KnowledgeMutationProposalRow(
                id=proposal_id,
                workspace_id=workspace_id,
                trigger_claim_candidate_id=trigger_claim_candidate_id,
                proposal_kind="contradiction",
                detector=detector,
                detector_version=detector_version,
                summary=summary,
                idempotency_key=idempotency_key,
                resolver_metadata=dict(resolver_metadata),
            )
        )
        self._session.flush()
        return proposal_id

    def add_duplicate_proposal(
        self,
        *,
        workspace_id: int,
        idempotency_key: str,
        trigger_entity_candidate_id: uuid.UUID,
        detector: str,
        detector_version: str,
        summary: str,
        resolver_metadata: Mapping[str, JsonValue],
        representative_candidate_id: uuid.UUID,
        merge_candidate_ids: tuple[uuid.UUID, ...],
        proposed_type: str,
        proposed_name: str,
    ) -> uuid.UUID:
        """같은 대상 후보들을 하나로 합치는 계획서를 쓴다.

        같은 key의 행이 계류·접힘 상태면 그 행을 되살려 내용을
        갈아끼운다. `(workspace_id, idempotency_key)` UNIQUE가 상태를
        구분하지 않아 abandoned 행도 key를 차지하기 때문이다. 반면
        이미 결정된 행(approved·applied·rejected)은 건드리지 않고 그
        id만 돌려준다 — 사람의 결정은 judge 재실행이 덮을 수 없다.
        """
        existing = self._session.scalar(
            select(KnowledgeMutationProposalRow).where(
                KnowledgeMutationProposalRow.workspace_id == workspace_id,
                KnowledgeMutationProposalRow.idempotency_key
                == idempotency_key,
            )
        )
        if existing is not None and existing.status in (
            "approved",
            "applied",
            "rejected",
        ):
            logger.info(
                "merge_proposal_already_decided_skip",
                workspace_id=workspace_id,
                proposal_id=str(existing.id),
                status=existing.status,
            )
            return existing.id
        if existing is not None:
            proposal_id = existing.id
            existing.status = "pending"
            # 되살아난 안건은 새 검토 사건이다. 이전 결정의 흔적이
            # 남으면 감사 기록이 거짓이 된다.
            existing.reviewer = None
            existing.reviewed_at = None
            existing.rejection_reason = None
            existing.applied_at = None
            existing.proposal_kind = "duplicate"
            # trigger는 셋 중 정확히 하나여야 한다. 다른 종류의 계획서가
            # 쓰던 key를 되살리는 경우 나머지를 비워야 한다.
            existing.trigger_claim_candidate_id = None
            existing.trigger_relation_assertion_candidate_id = None
            existing.trigger_entity_candidate_id = trigger_entity_candidate_id
            existing.detector = detector
            existing.detector_version = detector_version
            existing.summary = summary
            existing.resolver_metadata = dict(resolver_metadata)
            self._session.execute(
                KnowledgeMutationOperationRow.__table__.delete().where(
                    KnowledgeMutationOperationRow.proposal_id == proposal_id
                )
            )
            self._session.flush()
        else:
            proposal_id = uuid.uuid4()
            self._session.add(
                KnowledgeMutationProposalRow(
                    id=proposal_id,
                    workspace_id=workspace_id,
                    trigger_entity_candidate_id=trigger_entity_candidate_id,
                    proposal_kind="duplicate",
                    detector=detector,
                    detector_version=detector_version,
                    summary=summary,
                    idempotency_key=idempotency_key,
                    resolver_metadata=dict(resolver_metadata),
                )
            )
            # relationship이 없어 flush 순서가 보장되지 않으므로 proposal을
            # 먼저 확정한다.
            self._session.flush()

        self._session.add(
            KnowledgeMutationOperationRow(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                proposal_id=proposal_id,
                sequence=1,
                operation_type="create_entity",
                entity_candidate_id=representative_candidate_id,
                operation_data={
                    "proposed_type": proposed_type,
                    "proposed_name": proposed_name,
                },
            )
        )
        for offset, candidate_id in enumerate(merge_candidate_ids, start=2):
            self._session.add(
                KnowledgeMutationOperationRow(
                    id=uuid.uuid4(),
                    workspace_id=workspace_id,
                    proposal_id=proposal_id,
                    sequence=offset,
                    operation_type="merge_entity",
                    entity_candidate_id=candidate_id,
                    operation_data={"merge_into_sequence": 1},
                )
            )
        self._session.flush()
        return proposal_id


class SqlAlchemyArtifactRepository:
    """문서·변경안·판의 영속성을 PostgreSQL로 구현한다.

    workspace를 생성 시점에 고정한다. 한 문서를 다루는 호출이 여럿이라
    메서드마다 workspace를 다시 받으면 호출자가 그중 하나를 틀릴 자리가
    생기기 때문이다.
    """

    def __init__(self, session: Session, workspace_id: int | None) -> None:
        self._session = session
        self._scoped_workspace_id = workspace_id

    @property
    def _workspace_id(self) -> int:
        """고정된 workspace를 돌려준다. 없으면 쓰지 못하게 막는다."""
        if self._scoped_workspace_id is None:
            raise RuntimeError(
                "artifact 저장소는 workspace_id를 받은 UnitOfWork에서만"
                " 쓸 수 있다."
            )
        return self._scoped_workspace_id

    def find_top_entity_nodes(self, *, limit: int) -> list[EntityCardSource]:
        """카드를 만들 대상 노드를 claim이 많은 순으로 고른다.

        claim의 subject는 canonical 노드를 직접 가리키거나, 해소를 마친
        entity 후보를 거쳐 가리킨다. 지금 파이프라인은 뒤쪽으로 저장하므로
        두 경로를 coalesce로 합쳐 센다. 한쪽만 보면 대부분의 노드가 0건이
        된다.

        claim과 inner join하므로 claim이 없는 노드는 자연히 빠진다. 순위가
        같을 때는 노드 식별자로 갈라 실행마다 순서가 흔들리지 않게 한다.
        """
        subject_node_id = func.coalesce(
            KnowledgeClaimCandidateRow.subject_node_id,
            KnowledgeEntityCandidateRow.resolved_node_id,
        )
        claim_count = func.count(KnowledgeClaimCandidateRow.id)
        statement = (
            select(
                KnowledgeNodeRow.id,
                KnowledgeNodeRow.display_name,
                KnowledgeNodeRow.canonical_key,
                claim_count,
            )
            .select_from(KnowledgeClaimCandidateRow)
            .outerjoin(
                KnowledgeEntityCandidateRow,
                KnowledgeClaimCandidateRow.subject_entity_candidate_id
                == KnowledgeEntityCandidateRow.id,
            )
            .join(
                KnowledgeNodeRow,
                KnowledgeNodeRow.id == subject_node_id,
            )
            .where(
                KnowledgeClaimCandidateRow.workspace_id == self._workspace_id,
                KnowledgeNodeRow.workspace_id == self._workspace_id,
                KnowledgeNodeRow.node_kind == NodeKind.ENTITY.value,
                KnowledgeNodeRow.lifecycle_state == "active",
            )
            .group_by(
                KnowledgeNodeRow.id,
                KnowledgeNodeRow.display_name,
                KnowledgeNodeRow.canonical_key,
            )
            .order_by(claim_count.desc(), KnowledgeNodeRow.id)
            .limit(limit)
        )
        return [
            EntityCardSource(
                node_id=node_id,
                display_name=display_name or canonical_key or str(node_id),
                claim_count=count,
            )
            for node_id, display_name, canonical_key, count in (
                self._session.execute(statement).all()
            )
        ]

    def get_or_create_artifact(
        self,
        *,
        kind: str,
        subject_node_id: uuid.UUID,
        title: str,
    ) -> uuid.UUID:
        """대상에 붙는 문서를 만들거나 이미 있는 것을 돌려준다.

        이미 있으면 제목을 덮어쓰지 않는다. 제목은 문서의 정체성이라
        컴파일을 다시 돌 때마다 바뀌면 사람이 같은 문서인지 알 수 없다.
        """
        found = self._session.scalar(
            select(KnowledgeArtifactRow.id).where(
                KnowledgeArtifactRow.workspace_id == self._workspace_id,
                KnowledgeArtifactRow.kind == kind,
                KnowledgeArtifactRow.subject_node_id == subject_node_id,
            )
        )
        if found is not None:
            return found

        artifact_id = uuid.uuid4()
        self._session.add(
            KnowledgeArtifactRow(
                id=artifact_id,
                workspace_id=self._workspace_id,
                kind=kind,
                subject_node_id=subject_node_id,
                title=title,
            )
        )
        self._session.flush()
        return artifact_id

    def find_latest_revision_id_and_number(
        self,
        *,
        artifact_id: uuid.UUID,
    ) -> tuple[uuid.UUID, int] | None:
        """문서의 가장 최근 판을 식별자와 번호로 돌려준다."""
        row = self._session.execute(
            select(
                KnowledgeArtifactRevisionRow.id,
                KnowledgeArtifactRevisionRow.revision_number,
            )
            .where(
                KnowledgeArtifactRevisionRow.workspace_id
                == self._workspace_id,
                KnowledgeArtifactRevisionRow.artifact_id == artifact_id,
            )
            .order_by(KnowledgeArtifactRevisionRow.revision_number.desc())
            .limit(1)
        ).first()
        if row is None:
            return None
        return (row[0], row[1])

    def find_latest_content_hashes(
        self,
        *,
        artifact_id: uuid.UUID,
    ) -> set[str]:
        """이미 사람 앞에 놓인 내용의 지문을 모은다.

        판에는 지문 컬럼이 없다. 판은 승인된 변경안을 그대로 얼린 것이므로
        그 변경안의 지문이 곧 판의 지문이다. 승인된 변경안을 따로 훑지
        않는 이유도 같다. 지나간 판의 지문은 넣지 않는다. 옛 내용으로
        되돌리자는 제안은 사람이 다시 볼 값어치가 있기 때문이다.
        """
        hashes: set[str] = set()
        latest_hash = self._session.scalar(
            select(KnowledgeArtifactChangeProposalRow.content_hash)
            .select_from(KnowledgeArtifactRevisionRow)
            .join(
                KnowledgeArtifactChangeProposalRow,
                KnowledgeArtifactRevisionRow.source_proposal_id
                == KnowledgeArtifactChangeProposalRow.id,
            )
            .where(
                KnowledgeArtifactRevisionRow.workspace_id
                == self._workspace_id,
                KnowledgeArtifactRevisionRow.artifact_id == artifact_id,
            )
            .order_by(KnowledgeArtifactRevisionRow.revision_number.desc())
            .limit(1)
        )
        if latest_hash is not None:
            hashes.add(latest_hash)

        hashes.update(
            self._session.scalars(
                select(
                    KnowledgeArtifactChangeProposalRow.content_hash
                ).where(
                    KnowledgeArtifactChangeProposalRow.workspace_id
                    == self._workspace_id,
                    KnowledgeArtifactChangeProposalRow.artifact_id
                    == artifact_id,
                    KnowledgeArtifactChangeProposalRow.status.in_(
                        ("pending", "rejected")
                    ),
                )
            )
        )
        return hashes

    def abandon_pending_proposals(self, *, artifact_id: uuid.UUID) -> int:
        """문서에 계류 중인 변경안을 모두 접고 접은 수를 돌려준다."""
        result = self._session.execute(
            update(KnowledgeArtifactChangeProposalRow)
            .where(
                KnowledgeArtifactChangeProposalRow.workspace_id
                == self._workspace_id,
                KnowledgeArtifactChangeProposalRow.artifact_id == artifact_id,
                KnowledgeArtifactChangeProposalRow.status == "pending",
            )
            .values(status="abandoned")
        )
        self._session.flush()
        return result.rowcount

    def add_or_revive_proposal(
        self,
        *,
        artifact_id: uuid.UUID,
        blocks: Sequence[ArtifactBlock],
        content_hash: str,
        idempotency_key: str,
        base_revision_id: uuid.UUID | None,
    ) -> uuid.UUID:
        """변경안을 올린다. 아직 열려 있거나 접힌 행이면 되살려 갈아끼운다.

        `(workspace_id, idempotency_key)` UNIQUE가 상태를 구분하지 않아
        접힌 행도 key를 계속 차지한다. 새로 INSERT하면 충돌이 나고 같은
        transaction의 다른 작업까지 되돌아가므로 그 행을 되살린다.

        되살리는 것은 pending과 abandoned뿐이다. 사람이 이미 결정을 내린
        approved·rejected 행은 건드리지 않고 예외로 알린다. 멱등 키가
        문서와 내용 지문으로만 만들어져 내용이 A→B→A로 되돌아오면 옛
        결정과 같은 키가 다시 오는데, 그때 되살리면 발행된 판이 가리키는
        승인 행이 pending으로 뒤집히며 검토자와 승인 시각이 지워진다.
        승인 감사 기록을 잃는 것은 조용히 넘길 수 있는 일이 아니다.

        되살릴 때 검토 흔적을 지운다. 반려 사유와 검토자가 남아 있으면
        새 변경안이 이미 반려된 것처럼 보이기 때문이다.

        Raises:
            ArtifactBlockError: 블록이 근거 계약을 어겼을 때 던진다.
            ArtifactProposalConflict: 같은 키를 이미 결정된 변경안이 쓰고
                있을 때 던진다.
        """
        # 근거 없는 문장을 막는 마지막 자리다. 저장 전에 본다.
        validate_blocks(blocks)
        payload = serialize_blocks(blocks)

        existing = self._session.scalar(
            select(KnowledgeArtifactChangeProposalRow).where(
                KnowledgeArtifactChangeProposalRow.workspace_id
                == self._workspace_id,
                KnowledgeArtifactChangeProposalRow.idempotency_key
                == idempotency_key,
            )
        )
        if existing is not None:
            if existing.status not in ("pending", "abandoned"):
                raise ArtifactProposalConflict(
                    f"{existing.status} 상태의 변경안 {existing.id}가 같은"
                    f" 멱등 키를 쓰고 있어 되살릴 수 없다."
                )
            existing.artifact_id = artifact_id
            existing.blocks = payload
            existing.status = "pending"
            existing.content_hash = content_hash
            existing.base_revision_id = base_revision_id
            existing.rejection_reason = None
            existing.reviewer = None
            existing.reviewed_at = None
            self._session.flush()
            return existing.id

        proposal_id = uuid.uuid4()
        self._session.add(
            KnowledgeArtifactChangeProposalRow(
                id=proposal_id,
                workspace_id=self._workspace_id,
                artifact_id=artifact_id,
                blocks=payload,
                status="pending",
                content_hash=content_hash,
                idempotency_key=idempotency_key,
                base_revision_id=base_revision_id,
            )
        )
        self._session.flush()
        return proposal_id

    def get_proposal(
        self,
        *,
        proposal_id: uuid.UUID,
    ) -> StoredArtifactProposal | None:
        """변경안 하나를 문서 제목·대상과 함께 읽는다."""
        row = self._session.execute(
            self._proposal_statement().where(
                KnowledgeArtifactChangeProposalRow.id == proposal_id
            )
        ).first()
        if row is None:
            return None
        return _artifact_proposal_to_domain(row[0], row[1], row[2])

    def list_pending_proposals(self) -> list[StoredArtifactProposal]:
        """검토를 기다리는 변경안을 오래된 순으로 읽는다."""
        statement = (
            self._proposal_statement()
            .where(KnowledgeArtifactChangeProposalRow.status == "pending")
            .order_by(
                KnowledgeArtifactChangeProposalRow.created_at,
                KnowledgeArtifactChangeProposalRow.id,
            )
        )
        return [
            _artifact_proposal_to_domain(proposal, subject_node_id, title)
            for proposal, subject_node_id, title in (
                self._session.execute(statement).all()
            )
        ]

    def _proposal_statement(self) -> Select:
        """변경안을 문서 정보와 함께 읽는 질의의 공통 뼈대를 만든다."""
        return (
            select(
                KnowledgeArtifactChangeProposalRow,
                KnowledgeArtifactRow.subject_node_id,
                KnowledgeArtifactRow.title,
            )
            .join(
                KnowledgeArtifactRow,
                KnowledgeArtifactChangeProposalRow.artifact_id
                == KnowledgeArtifactRow.id,
            )
            .where(
                KnowledgeArtifactChangeProposalRow.workspace_id
                == self._workspace_id,
                KnowledgeArtifactRow.workspace_id == self._workspace_id,
            )
        )

    def mark_approved(self, *, proposal_id: uuid.UUID, reviewer: str) -> None:
        """아직 계류 중인 변경안을 승인으로 끝맺는다.

        Raises:
            ProposalAlreadyDecided: 바꿀 계류 행이 없을 때 던진다.
        """
        self._decide(
            proposal_id=proposal_id,
            values={
                "status": "approved",
                "reviewer": reviewer,
                "reviewed_at": func.now(),
            },
        )

    def mark_rejected(
        self,
        *,
        proposal_id: uuid.UUID,
        reviewer: str,
        reason: str,
    ) -> None:
        """아직 계류 중인 변경안을 사유와 함께 반려로 끝맺는다.

        사유는 DB CHECK가 요구한다. 이유 없는 반려는 다음 사람이 같은
        변경안을 다시 올리게 만들기 때문이다.

        Raises:
            ProposalAlreadyDecided: 바꿀 계류 행이 없을 때 던진다.
        """
        self._decide(
            proposal_id=proposal_id,
            values={
                "status": "rejected",
                "rejection_reason": reason,
                "reviewer": reviewer,
                "reviewed_at": func.now(),
            },
        )

    def _decide(
        self,
        *,
        proposal_id: uuid.UUID,
        values: Mapping[str, object],
    ) -> None:
        """계류 중인 변경안에만 결정을 싣는다.

        `status = 'pending'`을 UPDATE 조건에 둔다. 이것이 낙관적 전이다.
        결정을 쓰는 쪽이 행을 다시 읽으며 조건을 맞춰 보므로, 두 검토가
        같은 계류 행을 읽었더라도 먼저 커밋한 쪽만 조건에 걸린다. 미리
        잠그지 않는 대신 진 쪽이 바꾼 행 수 0으로 자기가 졌음을 안다.

        바꾼 행이 정확히 하나가 아니면 던진다. 0이면 남이 먼저 결정했거나
        없는 변경안이고, 둘 이상은 있을 수 없는 일이라 조용히 넘기면
        결정이 겹쳐 쓰인 채로 커밋된다.

        Raises:
            ProposalAlreadyDecided: 바꾼 계류 행이 하나가 아닐 때 던진다.
        """
        result = self._session.execute(
            update(KnowledgeArtifactChangeProposalRow)
            .where(
                KnowledgeArtifactChangeProposalRow.workspace_id
                == self._workspace_id,
                KnowledgeArtifactChangeProposalRow.id == proposal_id,
                KnowledgeArtifactChangeProposalRow.status == "pending",
            )
            .values(**values)
        )
        if result.rowcount != 1:
            raise ProposalAlreadyDecided(
                f"변경안 {proposal_id}는 계류 중이 아니라 결정을 실을 수"
                f" 없다. 바꾼 행 {result.rowcount}개."
            )
        self._session.flush()

    def add_revision(
        self,
        *,
        artifact_id: uuid.UUID,
        revision_number: int,
        blocks: Sequence[ArtifactBlock],
        source_proposal_id: uuid.UUID,
    ) -> uuid.UUID:
        """승인으로 확정된 판을 새로 쌓는다.

        판 번호가 겹치면 UNIQUE가 막는다. 동시에 두 승인이 같은 번호를
        쓰는 것을 DB가 거절하는 자리이므로 여기서 미리 검사하지 않는다.
        """
        revision_id = uuid.uuid4()
        self._session.add(
            KnowledgeArtifactRevisionRow(
                id=revision_id,
                workspace_id=self._workspace_id,
                artifact_id=artifact_id,
                revision_number=revision_number,
                blocks=serialize_blocks(blocks),
                source_proposal_id=source_proposal_id,
            )
        )
        self._session.flush()
        return revision_id


def _artifact_proposal_to_domain(
    row: KnowledgeArtifactChangeProposalRow,
    subject_node_id: uuid.UUID,
    title: str,
) -> StoredArtifactProposal:
    """저장된 변경안 row를 검토자가 볼 형태로 되돌린다."""
    return StoredArtifactProposal(
        id=row.id,
        artifact_id=row.artifact_id,
        subject_node_id=subject_node_id,
        title=title,
        status=row.status,
        blocks=deserialize_blocks(row.blocks),
        content_hash=row.content_hash,
        base_revision_id=row.base_revision_id,
        rejection_reason=row.rejection_reason,
    )


def _json_hash(value: object) -> str:
    """JSON 표현의 사소한 차이를 무시하고 같은 값인지 비교할 hash를 만든다."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _encode_claim_vocabulary(vocabulary: ExtractionVocabulary) -> object:
    """predicates 컬럼에 담을 값을 만든다.

    사전 항목이 없으면 예전과 같은 이름 목록 그대로 둔다. 항목이 있으면
    이름 목록과 항목을 함께 담은 객체로 감싼다. 전용 컬럼을 새로 만들려면
    migration이 필요하고, JSONB 한 칸이면 스키마 변경 없이 같은 사실을
    보존할 수 있기 때문이다. entity 종류 항목도 claim이 무엇에 대한
    주장인지를 정하는 어휘이므로 여기에 함께 둔다.
    """
    if not vocabulary.predicate_entries and not vocabulary.entity_type_entries:
        return list(vocabulary.predicates)
    return {
        "names": list(vocabulary.predicates),
        "predicate_entries": [
            entry.model_dump(mode="json")
            for entry in vocabulary.predicate_entries
        ],
        "entity_type_entries": [
            entry.model_dump(mode="json")
            for entry in vocabulary.entity_type_entries
        ],
    }


def _encode_relation_vocabulary(vocabulary: ExtractionVocabulary) -> object:
    """relation_types 컬럼에 담을 값을 만든다."""
    if not vocabulary.relation_type_entries:
        return list(vocabulary.relation_types)
    return {
        "names": list(vocabulary.relation_types),
        "relation_type_entries": [
            entry.model_dump(mode="json")
            for entry in vocabulary.relation_type_entries
        ],
    }


def _decode_names(column_value: object) -> tuple[str, ...]:
    """컬럼 값에서 이름 목록을 읽는다."""
    if isinstance(column_value, dict):
        return tuple(column_value.get("names", ()))
    return tuple(column_value or ())


def _decode_entries(column_value: object, key: str) -> tuple[dict, ...]:
    """컬럼 값에서 사전 항목 원본을 읽는다."""
    if isinstance(column_value, dict):
        return tuple(column_value.get(key, ()))
    return ()


class SqlAlchemyOntologyRepository:
    """어휘 스냅샷의 영속성을 PostgreSQL로 구현한다."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(
        self,
        *,
        workspace_id: int,
        ontology_id: str,
        version: str,
    ) -> ExtractionVocabulary | None:
        """어느 버전이 어떤 어휘였는지 찾는다."""
        row = self._session.scalar(
            select(KnowledgeOntologySnapshotRow).where(
                KnowledgeOntologySnapshotRow.workspace_id == workspace_id,
                KnowledgeOntologySnapshotRow.ontology_id == ontology_id,
                KnowledgeOntologySnapshotRow.version == version,
            )
        )
        if row is None:
            return None
        return ExtractionVocabulary(
            snapshot_id=row.version,
            predicates=_decode_names(row.predicates),
            relation_types=_decode_names(row.relation_types),
            entity_type_entries=_decode_entries(
                row.predicates, "entity_type_entries"
            ),
            predicate_entries=_decode_entries(
                row.predicates, "predicate_entries"
            ),
            relation_type_entries=_decode_entries(
                row.relation_types, "relation_type_entries"
            ),
        )

    def ensure(
        self,
        *,
        workspace_id: int,
        ontology_id: str,
        vocabulary: ExtractionVocabulary,
    ) -> ExtractionVocabulary:
        """스냅샷을 남기거나 이미 있는 것을 돌려준다.

        어휘는 그 버전에서 확정된 값이므로 덮어쓰지 않는다.
        """
        found = self.get(
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            version=vocabulary.snapshot_id,
        )
        if found is not None:
            # 이름뿐 아니라 정의까지 비교한다. 같은 이름에 다른 뜻을 담으면
            # 그 버전으로 추출한 후보가 어떤 규칙을 따랐는지 기록이 어긋난다.
            if (
                found.predicates != vocabulary.predicates
                or found.relation_types != vocabulary.relation_types
                or found.entity_type_entries != vocabulary.entity_type_entries
                or found.predicate_entries != vocabulary.predicate_entries
                or found.relation_type_entries
                != vocabulary.relation_type_entries
            ):
                raise OntologySnapshotConflict(
                    f"{ontology_id} {vocabulary.snapshot_id}에 다른 어휘를 "
                    f"담으려 했다. 저장된 predicate {len(found.predicates)}종, "
                    f"넣으려는 것 {len(vocabulary.predicates)}종"
                )
            return found

        row = KnowledgeOntologySnapshotRow(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            version=vocabulary.snapshot_id,
            predicates=_encode_claim_vocabulary(vocabulary),
            relation_types=_encode_relation_vocabulary(vocabulary),
        )
        self._session.add(row)
        self._session.flush()
        return vocabulary

    def list_versions(
        self,
        *,
        workspace_id: int,
        ontology_id: str,
    ) -> tuple[str, ...]:
        """저장된 어휘 버전을 만든 순서대로 돌려준다."""
        rows = self._session.scalars(
            select(KnowledgeOntologySnapshotRow.version)
            .where(
                KnowledgeOntologySnapshotRow.workspace_id == workspace_id,
                KnowledgeOntologySnapshotRow.ontology_id == ontology_id,
            )
            .order_by(
                KnowledgeOntologySnapshotRow.created_at,
                KnowledgeOntologySnapshotRow.version,
            )
        )
        return tuple(rows)


class SqlAlchemyPipelineEventRepository:
    """파이프라인 큐의 영속성을 PostgreSQL로 구현한다."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(
        self,
        *,
        workspace_id: int,
        event_type: PipelineEventType,
        aggregate_type: PipelineAggregateType,
        aggregate_id: uuid.UUID,
        payload: dict | None = None,
    ) -> PipelineEvent | None:
        """할 일을 큐에 적는다. 이미 있으면 새로 적지 않는다."""
        existing = self._session.scalar(
            select(PipelineOutboxRow).where(
                PipelineOutboxRow.event_type == event_type.value,
                PipelineOutboxRow.aggregate_type == aggregate_type.value,
                PipelineOutboxRow.aggregate_id == aggregate_id,
            )
        )
        if existing is not None:
            return None

        row = PipelineOutboxRow(
            workspace_id=workspace_id,
            event_type=event_type.value,
            aggregate_type=aggregate_type.value,
            aggregate_id=aggregate_id,
            payload=payload or {},
            status=PipelineEventStatus.PENDING.value,
        )
        self._session.add(row)
        self._session.flush()
        return _pipeline_event_to_domain(row)

    def claim_pending(
        self,
        *,
        workspace_id: int,
        event_type: PipelineEventType,
        now: datetime,
        limit: int | None = None,
    ) -> tuple[PipelineEvent, ...]:
        """지금 처리할 수 있는 일을 집는다."""
        statement = (
            select(PipelineOutboxRow)
            .where(
                PipelineOutboxRow.workspace_id == workspace_id,
                PipelineOutboxRow.event_type == event_type.value,
                PipelineOutboxRow.status == PipelineEventStatus.PENDING.value,
                PipelineOutboxRow.available_at <= now,
            )
            .order_by(PipelineOutboxRow.available_at, PipelineOutboxRow.id)
        )
        if limit is not None:
            statement = statement.limit(limit)

        return tuple(
            _pipeline_event_to_domain(row)
            for row in self._session.scalars(statement)
        )

    def mark_processed(self, *, event_id: int, now: datetime) -> None:
        """처리를 마쳤음을 남긴다."""
        self._session.execute(
            update(PipelineOutboxRow)
            .where(PipelineOutboxRow.id == event_id)
            .values(
                status=PipelineEventStatus.PROCESSED.value,
                processed_at=now,
                last_error=None,
            )
        )

    def mark_failed(
        self,
        *,
        event_id: int,
        kind: FailureKind,
        error: str,
        now: datetime,
    ) -> PipelineEvent:
        """실패를 기록하고 다시 시도할지 정한다."""
        row = self._session.get(PipelineOutboxRow, event_id)
        if row is None:
            raise ValueError(f"pipeline event를 찾을 수 없다: {event_id}")

        attempts = row.attempts + 1
        status = resolve_failure(kind, attempts)
        row.attempts = attempts
        row.status = status.value
        row.last_error = error
        if status is PipelineEventStatus.PENDING:
            row.available_at = next_attempt_at(attempts, now=now)
        else:
            row.processed_at = now
        self._session.flush()
        return _pipeline_event_to_domain(row)


def _pipeline_event_to_domain(row: PipelineOutboxRow) -> PipelineEvent:
    """저장된 row를 도메인 타입으로 되돌린다."""
    return PipelineEvent(
        id=row.id,
        workspace_id=row.workspace_id,
        event_type=PipelineEventType(row.event_type),
        aggregate_type=PipelineAggregateType(row.aggregate_type),
        aggregate_id=row.aggregate_id,
        status=PipelineEventStatus(row.status),
        attempts=row.attempts,
        available_at=row.available_at,
        payload=row.payload,
        last_error=row.last_error,
    )
