from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ColumnElement
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.orm import Session

from catchup.db.models import (
    KnowledgeCandidateEvidenceLink as KnowledgeCandidateEvidenceLinkRow,
)
from catchup.db.models import KnowledgeClaimCandidate as KnowledgeClaimCandidateRow
from catchup.db.models import KnowledgeEntityCandidate as KnowledgeEntityCandidateRow
from catchup.db.models import KnowledgeExtractionRun as KnowledgeExtractionRunRow
from catchup.db.models import KnowledgeNode as KnowledgeNodeRow
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
from catchup.knowledge_maintenance.domain.evidence import Locator
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionMethod
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionRun
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionRunSpec
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionRunStatus
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
from catchup.knowledge_maintenance.ports.ontology import OntologySnapshotConflict


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


def _json_hash(value: object) -> str:
    """JSON 표현의 사소한 차이를 무시하고 같은 값인지 비교할 hash를 만든다."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
            predicates=tuple(row.predicates),
            relation_types=tuple(row.relation_types),
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
            if (
                found.predicates != vocabulary.predicates
                or found.relation_types != vocabulary.relation_types
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
            predicates=list(vocabulary.predicates),
            relation_types=list(vocabulary.relation_types),
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
