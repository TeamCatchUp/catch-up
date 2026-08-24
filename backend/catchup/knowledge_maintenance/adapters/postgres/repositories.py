from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement
from sqlalchemy import DateTime
from sqlalchemy import Select
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import cast
from sqlalchemy import collate
from sqlalchemy import func
from sqlalchemy import literal
from sqlalchemy import nullsfirst
from sqlalchemy import nullslast
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from sqlalchemy.orm import aliased

from catchup.db.models import ArtifactDefinition as ArtifactDefinitionRow
from catchup.db.models import ArtifactOwner as ArtifactOwnerRow
from catchup.db.models import Channel as ChannelRow
from catchup.db.models import ChannelPurpose as ChannelPurposeRow
from catchup.db.models import KnowledgeArtifact as KnowledgeArtifactRow
from catchup.db.models import (
    KnowledgeArtifactChangeProposal as KnowledgeArtifactChangeProposalRow,
)
from catchup.db.models import KnowledgeArtifactRevision as KnowledgeArtifactRevisionRow
from catchup.db.models import KnowledgeBlockVerdict as KnowledgeBlockVerdictRow
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
from catchup.knowledge_maintenance.contracts.vocabulary_convergence import (
    PredicateUsage,
)
from catchup.knowledge_maintenance.contracts.vocabulary_convergence import RelationUsage
from catchup.knowledge_maintenance.domain.actor_identity import ACTOR_ATTRIBUTE
from catchup.knowledge_maintenance.domain.artifact import ArtifactBlock
from catchup.knowledge_maintenance.domain.artifact import block_content_hash
from catchup.knowledge_maintenance.domain.artifact import deserialize_blocks
from catchup.knowledge_maintenance.domain.artifact import serialize_blocks
from catchup.knowledge_maintenance.domain.artifact import validate_blocks
from catchup.knowledge_maintenance.domain.artifact_definition import DIRECTION_ANY
from catchup.knowledge_maintenance.domain.artifact_definition import DIRECTION_IN
from catchup.knowledge_maintenance.domain.artifact_definition import DIRECTION_OUT
from catchup.knowledge_maintenance.domain.artifact_definition import (
    deserialize_selection_spec,
)
from catchup.knowledge_maintenance.domain.claim_conflict import StoredClaimCandidate
from catchup.knowledge_maintenance.domain.entity_resolution import anchor_excerpt
from catchup.knowledge_maintenance.domain.evidence import Locator
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    AssertionResolutionStatus,
)
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
from catchup.knowledge_maintenance.domain.knowledge_node import NodeLifecycleState
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
from catchup.knowledge_maintenance.domain.source_version import JsonValue
from catchup.knowledge_maintenance.domain.source_version import SourceIdentity
from catchup.knowledge_maintenance.domain.source_version import SourceVersion
from catchup.knowledge_maintenance.ports.artifact_definitions import (
    StoredArtifactDefinition,
)
from catchup.knowledge_maintenance.ports.artifacts import ArtifactProposalConflict
from catchup.knowledge_maintenance.ports.artifacts import CurrentRevisionForProjection
from catchup.knowledge_maintenance.ports.artifacts import EntityCardSource
from catchup.knowledge_maintenance.ports.artifacts import ProposalAlreadyDecided
from catchup.knowledge_maintenance.ports.artifacts import StoredArtifactProposal
from catchup.knowledge_maintenance.ports.block_verdicts import StoredBlockVerdict
from catchup.knowledge_maintenance.ports.knowledge_candidates import AsOfClaim
from catchup.knowledge_maintenance.ports.knowledge_nodes import ActiveEntityAlias
from catchup.knowledge_maintenance.ports.mutation_proposals import ApprovedProposal
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
from catchup.knowledge_maintenance.ports.relations import StoredRelationEdge
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
                citation_verified=_optional_bool(
                    item.get("citation_verified")
                ),
            )
        )
    return tuple(values)


def _optional_str(value: object) -> str | None:
    """문자열로 읽을 수 있으면 문자열로, 아니면 None으로 준다."""
    if value is None:
        return None
    return str(value)


def _optional_bool(value: object) -> bool | None:
    """불리언이면 그대로, 아니면 None으로 준다."""
    return value if isinstance(value, bool) else None


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

    def get_by_id(
        self,
        *,
        workspace_id: int,
        source_version_id: uuid.UUID,
    ) -> SourceVersion | None:
        """workspace 안에서 SourceVersion 식별자로 찾는다."""
        row = self._session.scalar(
            select(SourceVersionRow).where(
                SourceVersionRow.workspace_id == workspace_id,
                SourceVersionRow.id == source_version_id,
            )
        )
        return source_version_to_domain(row) if row is not None else None

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

    def get_by_id(
        self,
        *,
        workspace_id: int,
        observation_id: uuid.UUID,
    ) -> StoredObservation | None:
        """workspace 안에서 Observation 식별자로 찾는다."""
        row = self._session.scalar(
            select(ObservationRow).where(
                ObservationRow.workspace_id == workspace_id,
                ObservationRow.id == observation_id,
            )
        )
        return observation_to_domain(row) if row is not None else None

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

    def find_entity_by_normalized_alias(
        self,
        *,
        workspace_id: int,
        normalized_alias: str,
        entity_type: str | None = None,
    ) -> KnowledgeNode | None:
        """정규화된 alias 정확 일치로 entity 노드를 찾는다.

        alias는 identity가 아니라 단서이므로 같은 alias가 여러 노드에
        걸릴 수 있다. 그때는 node id 순 첫 번째만 돌려준다 — 같은
        질의가 같은 답을 주어야 하기 때문이다.

        entity_type을 주면 그 type의 노드만 후보로 좁힌다. 1건만 돌려주는
        조회라 type을 뒤에서 보면 다른 type 노드가 id 순으로 앞설 때 맞는
        노드가 가려지므로, 거르기를 SQL 안에서 한다.
        """
        statement = (
            select(KnowledgeNodeRow)
            .join(
                KnowledgeNodeAliasRow,
                KnowledgeNodeAliasRow.node_id == KnowledgeNodeRow.id,
            )
            .where(
                KnowledgeNodeAliasRow.workspace_id == workspace_id,
                KnowledgeNodeAliasRow.normalized_alias == normalized_alias,
                KnowledgeNodeRow.workspace_id == workspace_id,
                KnowledgeNodeRow.node_kind == NodeKind.ENTITY.value,
            )
        )
        if entity_type is not None:
            statement = statement.where(
                KnowledgeNodeRow.entity_type == entity_type
            )
        row = self._session.scalar(
            statement.order_by(KnowledgeNodeRow.id).limit(1)
        )
        return knowledge_node_to_domain(row) if row is not None else None

    def list_active_entity_aliases(
        self,
        *,
        workspace_id: int,
    ) -> list[ActiveEntityAlias]:
        """살아 있는 entity 노드의 이름을 모두 모은다.

        노드 하나에 이름이 여럿이면 그 수만큼 행이 나온다. 어느 표기가
        후보와 닮았는지는 부르는 쪽이 견줘야 알 수 있어 저장소가 미리
        하나로 줄이지 않는다. 정렬을 node id·정규화 이름으로 고정해 같은
        질의가 같은 순서를 주게 한다.
        """
        rows = self._session.execute(
            select(
                KnowledgeNodeAliasRow.node_id,
                KnowledgeNodeRow.entity_type,
                KnowledgeNodeAliasRow.alias,
                KnowledgeNodeAliasRow.normalized_alias,
            )
            .join(
                KnowledgeNodeRow,
                KnowledgeNodeRow.id == KnowledgeNodeAliasRow.node_id,
            )
            .where(
                KnowledgeNodeAliasRow.workspace_id == workspace_id,
                KnowledgeNodeRow.workspace_id == workspace_id,
                KnowledgeNodeRow.node_kind == NodeKind.ENTITY.value,
                KnowledgeNodeRow.lifecycle_state
                == NodeLifecycleState.ACTIVE.value,
                KnowledgeNodeRow.entity_type.is_not(None),
            )
            .order_by(
                KnowledgeNodeAliasRow.node_id,
                KnowledgeNodeAliasRow.normalized_alias,
            )
        ).all()
        return [
            ActiveEntityAlias(
                node_id=row.node_id,
                entity_type=row.entity_type,
                alias=row.alias,
                normalized_alias=row.normalized_alias,
            )
            for row in rows
        ]

    def get_entity_by_id(
        self,
        *,
        workspace_id: int,
        node_id: uuid.UUID,
    ) -> KnowledgeNode | None:
        """node id로 entity 노드를 그대로 찾는다.

        이름 해소가 없는 조회다. lifecycle은 거르지 않는다 — 살아 있는
        노드만 쓸지는 읽기 경로가 정한다.
        """
        row = self._session.scalar(
            select(KnowledgeNodeRow).where(
                KnowledgeNodeRow.workspace_id == workspace_id,
                KnowledgeNodeRow.node_kind == NodeKind.ENTITY.value,
                KnowledgeNodeRow.id == node_id,
            )
        )
        return knowledge_node_to_domain(row) if row is not None else None

    def find_entity_candidates_by_similarity(
        self,
        *,
        workspace_id: int,
        normalized_query: str,
        threshold: float,
        limit: int,
    ) -> list[tuple[KnowledgeNode, float]]:
        """이름이 비슷한 active entity 노드를 점수와 함께 찾는다.

        두 단으로 나눠 읽는다. 먼저 `=%`로 alias 행을 줄이고, 남은
        행에만 bigm_similarity를 매겨 노드 단위 MAX로 접는다. 노드
        단위로 접는 이유는 alias가 많은 노드가 같은 후보를 여러 줄
        차지하면 상위 N이 노드 하나로 차 버리기 때문이다.

        `=%`를 쓰는 이유는 그 형태만 `idx_knowledge_node_aliases_bigm`
        (GIN, gin_bigm_ops)을 타기 때문이다. 함수 호출을 모든 행에
        계산한 뒤 HAVING으로 거르는 형태는 index condition이 되지
        못해, miss 한 번마다 workspace의 alias 전부에 유사도 함수가
        돈다.

        `=%`의 판정 기준은 GUC `pg_bigm.similarity_limit`이라 예전에는
        세션 설정에 답이 끌려다닐 위험 때문에 쓰지 않았다. 그 위험은
        `set_config(..., is_local => true)`, 즉 SET LOCAL로 없앤다.
        조회 직전 호출자가 넘긴 threshold를 현재 transaction에만 걸고,
        transaction이 끝나면 원래 값으로 돌아가므로 session에 설정이
        남지 않는다. `KnowledgeMaintenanceUnitOfWork`는 빠져나올 때
        rollback·close를 하므로 그 경계가 곧 설정의 수명이다.

        두 단의 문턱값이 같으므로 결과는 한 단짜리와 같다. `=%`는
        유사도가 문턱값 이상인 행만 통과시키고, MAX는 통과한 행들
        중에서 고른다 — 걸러진 행은 어차피 HAVING을 넘지 못한다.
        """
        # SET LOCAL을 문자열로 조립하지 않는다. SET은 bind 파라미터를
        # 받지 못하지만 set_config는 받으므로, threshold가 값으로만
        # 들어간다.
        self._session.execute(
            select(
                func.set_config(
                    "pg_bigm.similarity_limit",
                    str(threshold),
                    True,
                )
            )
        )
        narrowed = (
            select(
                KnowledgeNodeAliasRow.node_id.label("node_id"),
                KnowledgeNodeAliasRow.normalized_alias.label(
                    "normalized_alias"
                ),
            )
            .where(
                KnowledgeNodeAliasRow.workspace_id == workspace_id,
                KnowledgeNodeAliasRow.normalized_alias.op("=%")(
                    normalized_query
                ),
            )
            .subquery()
        )
        narrowed_score = func.max(
            func.bigm_similarity(
                narrowed.c.normalized_alias,
                normalized_query,
            )
        ).label("score")
        rows = self._session.execute(
            select(KnowledgeNodeRow, narrowed_score)
            .join(
                narrowed,
                narrowed.c.node_id == KnowledgeNodeRow.id,
            )
            .where(
                KnowledgeNodeRow.workspace_id == workspace_id,
                KnowledgeNodeRow.node_kind == NodeKind.ENTITY.value,
                KnowledgeNodeRow.lifecycle_state
                == NodeLifecycleState.ACTIVE.value,
            )
            .group_by(KnowledgeNodeRow.id)
            .having(narrowed_score >= threshold)
            .order_by(narrowed_score.desc(), KnowledgeNodeRow.id.asc())
            .limit(limit)
        ).all()
        return [
            (knowledge_node_to_domain(row), float(value)) for row, value in rows
        ]

    def create_entity_node(
        self,
        *,
        workspace_id: int,
        entity_type: str,
        canonical_key: str | None,
        display_name: str,
        attributes: Mapping[str, JsonValue] | None = None,
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
                attributes=dict(attributes or {}),
            )
        )
        self._session.add(row)
        self._session.flush()
        return knowledge_node_to_domain(row)

    def find_entity_by_actor_key(
        self,
        *,
        workspace_id: int,
        entity_type: str,
        key_kind: str,
        value: str,
    ) -> KnowledgeNode | None:
        """행위자 키로 active entity 노드를 찾는다.

        한 사람이 소스 세션마다 다른 external_key를 받으므로 canonical_key
        하나로는 동일성을 못 잡는다. 노드가 지금까지 본 키를
        attributes[ACTOR_ATTRIBUTE][key_kind] 목록에 쌓아 두고, 여기서는
        그 목록에 값이 들어 있는지를 JSONB 포함(@>)으로 본다. 포함 연산을
        쓰는 이유는 그 형태만 jsonb GIN index를 탈 수 있기 때문이다.

        둘 이상이 걸리면 created_at·id 순 첫 번째만 준다.
        """
        containment = cast(
            {ACTOR_ATTRIBUTE: {key_kind: [value]}},
            JSONB,
        )
        row = self._session.scalar(
            select(KnowledgeNodeRow)
            .where(
                KnowledgeNodeRow.workspace_id == workspace_id,
                KnowledgeNodeRow.node_kind == NodeKind.ENTITY.value,
                KnowledgeNodeRow.entity_type == entity_type,
                KnowledgeNodeRow.lifecycle_state
                == NodeLifecycleState.ACTIVE.value,
                KnowledgeNodeRow.attributes.op("@>")(containment),
            )
            .order_by(KnowledgeNodeRow.created_at, KnowledgeNodeRow.id)
            .limit(1)
        )
        return knowledge_node_to_domain(row) if row is not None else None

    def set_entity_attributes(
        self,
        *,
        workspace_id: int,
        node_id: uuid.UUID,
        attributes: Mapping[str, JsonValue],
    ) -> KnowledgeNode:
        """노드의 attributes를 통째로 바꾼다.

        키 단위로 합치지 않는다. 무엇을 남기고 무엇을 덮을지는 도메인
        규칙이라 호출자가 합친 결과를 그대로 적는다.
        """
        row = self._session.scalar(
            select(KnowledgeNodeRow).where(
                KnowledgeNodeRow.workspace_id == workspace_id,
                KnowledgeNodeRow.id == node_id,
            )
        )
        if row is None:
            raise ValueError(f"unknown knowledge node: {node_id}")
        row.attributes = dict(attributes)
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
    ) -> bool:
        """노드에 이름 단서를 남긴다. 같은 정규화 alias면 넘어간다.

        Returns:
            이번 호출이 행을 새로 넣었으면 참, 이미 있어 넘어갔으면 거짓을
            준다.
        """
        exists = self._session.scalar(
            select(KnowledgeNodeAliasRow.id).where(
                KnowledgeNodeAliasRow.workspace_id == workspace_id,
                KnowledgeNodeAliasRow.node_id == node_id,
                KnowledgeNodeAliasRow.normalized_alias == normalized_alias,
            )
        )
        if exists is not None:
            return False
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
        return True

    def remove_alias(
        self,
        *,
        workspace_id: int,
        node_id: uuid.UUID,
        normalized_alias: str,
    ) -> None:
        """확정이 남긴 이름 단서 하나를 노드에서 거둔다.

        source가 "system"인 행만 지운다. 같은 표기를 다른 관찰이 따로
        붙여 두었을 수 있어, 정규화 이름만 보고 지우면 되돌림과 무관한
        단서까지 사라진다.
        """
        row = self._session.scalar(
            select(KnowledgeNodeAliasRow).where(
                KnowledgeNodeAliasRow.workspace_id == workspace_id,
                KnowledgeNodeAliasRow.node_id == node_id,
                KnowledgeNodeAliasRow.normalized_alias == normalized_alias,
                KnowledgeNodeAliasRow.source == "system",
            )
        )
        if row is None:
            return
        self._session.delete(row)
        self._session.flush()

    def retire_entity_node(
        self,
        *,
        workspace_id: int,
        node_id: uuid.UUID,
    ) -> None:
        """entity 노드를 퇴역 상태로 물린다.

        행을 지우지 않는다. 저널과 지난 기록이 이 노드를 계속 가리키므로
        노드는 남되 살아 있는 노드를 보는 경로에서만 빠져야 한다.

        Raises:
            ValueError: 노드가 없을 때 던진다.
        """
        row = self._session.scalar(
            select(KnowledgeNodeRow).where(
                KnowledgeNodeRow.workspace_id == workspace_id,
                KnowledgeNodeRow.id == node_id,
            )
        )
        if row is None:
            raise ValueError(f"unknown knowledge node: {node_id}")
        row.lifecycle_state = NodeLifecycleState.RETIRED.value
        # merged_into_node_id는 비운다. lifecycle이 merged가 아닌 행에
        # 흡수처가 남아 있으면 DB CHECK가 막는다.
        row.merged_into_node_id = None
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

    def supersede_stale_pending_candidates(
        self,
        *,
        workspace_id: int,
        input_node_id: uuid.UUID,
        current_run_id: uuid.UUID,
    ) -> int:
        """같은 입력의 이전 실행이 남긴 pending 후보를 은퇴시킨다.

        재추출이 만든 새 배치와 구 배치가 resolution에 이중으로 잡히는
        것을 막기 위해서다. pending만 superseded로 전이한다 — 사람 결정과
        해소 결과(accepted·merged·duplicate·rejected)는 되돌릴 수 없는
        기록이라 건드리지 않는다.
        """
        stale_run_ids = (
            select(KnowledgeExtractionRunRow.id)
            .where(
                KnowledgeExtractionRunRow.workspace_id == workspace_id,
                KnowledgeExtractionRunRow.input_node_id == input_node_id,
                KnowledgeExtractionRunRow.id != current_run_id,
            )
            .scalar_subquery()
        )
        total = 0
        for row_type, pending, superseded in (
            (
                KnowledgeEntityCandidateRow,
                EntityResolutionStatus.PENDING.value,
                EntityResolutionStatus.SUPERSEDED.value,
            ),
            (
                KnowledgeClaimCandidateRow,
                AssertionResolutionStatus.PENDING.value,
                AssertionResolutionStatus.SUPERSEDED.value,
            ),
            (
                KnowledgeRelationCandidateRow,
                AssertionResolutionStatus.PENDING.value,
                AssertionResolutionStatus.SUPERSEDED.value,
            ),
        ):
            result = self._session.execute(
                update(row_type)
                .where(
                    row_type.workspace_id == workspace_id,
                    row_type.extraction_run_id.in_(stale_run_ids),
                    row_type.resolution_status == pending,
                )
                .values(resolution_status=superseded)
            )
            total += result.rowcount or 0
        return total

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
        """후보가 어떤 Observation에서 나왔는지 잇는다.

        locator의 빈 항목은 저장하지 않는다. `locator != '{}'`가 인용 검증
        통과 여부를 읽는 신호이므로, 값이 없는 키까지 적으면 그 판정과
        무관한 잡음이 JSONB에 남는다.
        """
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
            locator=(
                {
                    key: value
                    for key, value in asdict(locator).items()
                    if value is not None
                }
                if locator is not None
                else {}
            ),
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
        판정의 입력이기 때문이다. 그 시각은 claim 발화 시각을 맨 앞에 둔
        사슬(evidence locator의 event_at → occurred_at →
        source_updated_at → observed_at)로 공급한다.

        claim 발화 시각이 최우선이다 — 추출이 발화 prefix로 본 시각과
        소비자가 보는 시각이 발화 단위로 일치한다. 문서 시각만 쓰면 8/1에
        열린 상담의 8/10 발화가 8/5에 열린 상담보다 오래된 것으로 정렬되어
        모순 판정의 승자가 뒤집힌다. 발화 시각이 없는 claim은 뒤의 문서
        사슬로 물러나며, 그 사슬은
        domain.temporal.resolve_reference_time과 같다.
        subject가 entity 후보라면 그 후보 행을
        outer join해 해소 결과를 함께 담는다. 아직 해소되지 않은 후보도
        빠지면 안 되므로 outer join이어야 한다.

        rejected는 참이었던 적 없는 후보라 이 reader의 기본 경로에서
        제외한다. 감사는 행 보존과 결정 저널이 담당하므로 조회에서 빼도
        기록은 남는다. 반대로 닫힌 accepted는 "한때 참이었다"를 묻는
        temporal 자료라 계속 싣고, 거르는 일은 각 소비자가 valid_to로
        한다.

        superseded도 뺀다. 재추출이 대체한 구 배치라 새 배치와 함께
        실리면 같은 주장이 두 번 판정된다.
        """
        citation_verified = (
            select(
                func.bool_or(
                    KnowledgeCandidateEvidenceLinkRow.locator
                    != cast({}, JSONB)
                )
            )
            .where(
                KnowledgeCandidateEvidenceLinkRow.claim_candidate_id
                == KnowledgeClaimCandidateRow.id
            )
            .scalar_subquery()
        )
        # 근거 링크는 claim 하나에 여러 개일 수 있다. 그중 가장 이른 발화
        # 시각을 쓴다 — 주장이 처음 말해진 때가 그 주장의 시간이다.
        claim_event_at = (
            select(
                func.min(
                    cast(
                        KnowledgeCandidateEvidenceLinkRow.locator["event_at"].astext,
                        DateTime(timezone=True),
                    )
                )
            )
            .where(
                KnowledgeCandidateEvidenceLinkRow.claim_candidate_id
                == KnowledgeClaimCandidateRow.id
            )
            .scalar_subquery()
        )
        statement = (
            select(
                KnowledgeClaimCandidateRow,
                func.coalesce(
                    claim_event_at,
                    ObservationRow.occurred_at,
                    SourceVersionRow.source_updated_at,
                    SourceVersionRow.observed_at,
                ).label("observed_at"),
                KnowledgeEntityCandidateRow.resolved_node_id,
                citation_verified,
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
            .where(
                KnowledgeClaimCandidateRow.workspace_id == workspace_id,
                KnowledgeClaimCandidateRow.resolution_status.notin_(
                    (
                        AssertionResolutionStatus.REJECTED.value,
                        AssertionResolutionStatus.SUPERSEDED.value,
                    )
                ),
            )
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
                valid_from=row.valid_from,
                valid_to=row.valid_to,
                citation_verified=verified,
            )
            for row, observed_at, resolved_node_id, verified in (
                self._session.execute(statement).all()
            )
        )

    def summarize_predicate_usage(
        self,
        *,
        workspace_id: int,
        value_cap: int = 20,
        example_cap: int = 5,
    ) -> tuple[PredicateUsage, ...]:
        """pending claim 후보의 predicate 사용 현황을 집계한다.

        사전 등재 여부로 거르지 않는다 — OOV 판정은 소비자의 몫이다.
        집계는 Python에서 한다. 평가 러너 규모라 caps를 SQL로 옮길 이유가
        없고, 값 직렬화 규칙을 한 곳에 두는 편이 낫다.
        """
        rows = self._session.execute(
            select(
                KnowledgeClaimCandidateRow.predicate,
                KnowledgeClaimCandidateRow.value_type,
                KnowledgeClaimCandidateRow.value,
                KnowledgeClaimCandidateRow.statement,
                KnowledgeEntityCandidateRow.proposed_type,
            )
            .join(
                KnowledgeEntityCandidateRow,
                (
                    KnowledgeEntityCandidateRow.workspace_id
                    == KnowledgeClaimCandidateRow.workspace_id
                )
                & (
                    KnowledgeEntityCandidateRow.id
                    == KnowledgeClaimCandidateRow.subject_entity_candidate_id
                ),
                isouter=True,
            )
            .where(
                KnowledgeClaimCandidateRow.workspace_id == workspace_id,
                KnowledgeClaimCandidateRow.resolution_status == "pending",
            )
        ).all()

        grouped: dict[str, dict[str, Any]] = {}
        for predicate, value_type, value, statement, subject_type in rows:
            bucket = grouped.setdefault(
                predicate,
                {
                    "count": 0,
                    "value_types": set(),
                    "values": [],
                    "statements": [],
                    "subject_types": set(),
                },
            )
            bucket["count"] += 1
            bucket["value_types"].add(value_type)
            # 문자열 값은 비가공으로 둔다. 소비자의 enum 치역 가드가 사전의
            # enum_values와 이 문자열을 직접 비교한다.
            serialized = (
                value
                if isinstance(value, str)
                else json.dumps(value, ensure_ascii=False, sort_keys=True)
            )
            if serialized not in bucket["values"]:
                bucket["values"].append(serialized)
            if statement not in bucket["statements"]:
                bucket["statements"].append(statement)
            if subject_type is not None:
                bucket["subject_types"].add(subject_type)

        usage = [
            PredicateUsage(
                name=name,
                usage_count=bucket["count"],
                value_types=tuple(sorted(bucket["value_types"])),
                observed_values=tuple(sorted(bucket["values"])[:value_cap]),
                example_statements=tuple(bucket["statements"][:example_cap]),
                subject_types=tuple(sorted(bucket["subject_types"])),
            )
            for name, bucket in grouped.items()
        ]
        usage.sort(key=lambda item: (-item.usage_count, item.name))
        return tuple(usage)

    def summarize_relation_usage(
        self,
        *,
        workspace_id: int,
        example_cap: int = 5,
    ) -> tuple[RelationUsage, ...]:
        """pending 관계 후보의 relation type 사용 현황을 집계한다.

        사전 등재 여부로 거르지 않는다 — OOV 판정은 소비자의 몫이다.
        """
        rows = self._session.execute(
            select(
                KnowledgeRelationCandidateRow.relation_type,
                KnowledgeRelationCandidateRow.assertion_text,
            ).where(
                KnowledgeRelationCandidateRow.workspace_id == workspace_id,
                KnowledgeRelationCandidateRow.resolution_status == "pending",
            )
        ).all()

        grouped: dict[str, dict[str, Any]] = {}
        for relation_type, assertion_text in rows:
            bucket = grouped.setdefault(
                relation_type,
                {"count": 0, "assertions": []},
            )
            bucket["count"] += 1
            if assertion_text is None:
                continue
            if assertion_text not in bucket["assertions"]:
                bucket["assertions"].append(assertion_text)

        usage = [
            RelationUsage(
                name=name,
                usage_count=bucket["count"],
                example_assertions=tuple(bucket["assertions"][:example_cap]),
            )
            for name, bucket in grouped.items()
        ]
        usage.sort(key=lambda item: (-item.usage_count, item.name))
        return tuple(usage)

    def find_accepted_claims_as_of(
        self,
        *,
        workspace_id: int,
        subject_node_id: uuid.UUID,
        at: datetime,
        predicate: str | None = None,
    ) -> tuple[AsOfClaim, ...]:
        """어떤 노드에 대해 at 시점에 참이었던 claim을 읽는다.

        구간 조건은 `domain.temporal.claim_valid_at`과 정의가 같다 —
        `(valid_from IS NULL OR valid_from <= at) AND (valid_to IS NULL
        OR valid_to > at)`. 그 함수가 유일한 정의처이고 여기 SQL은 같은
        규칙을 DB로 옮긴 것이라, 한쪽만 고치면 두 경로의 답이 갈린다.

        subject 해소는 `find_claim_candidates`와 같은 방식이다. 노드를
        직접 가리키는 claim과, 그 노드로 해소된 entity 후보를 가리키는
        claim 둘 다 같은 대상에 대한 주장이기 때문이다. 상태는
        accepted만 본다 — pending은 아직 지식이 아니고 rejected는
        참이었던 적이 없다.
        """
        statement = (
            self._accepted_claims_of_subject(
                workspace_id=workspace_id,
                subject_node_id=subject_node_id,
                predicate=predicate,
            )
            .where(
                or_(
                    KnowledgeClaimCandidateRow.valid_from.is_(None),
                    KnowledgeClaimCandidateRow.valid_from <= at,
                ),
                or_(
                    KnowledgeClaimCandidateRow.valid_to.is_(None),
                    KnowledgeClaimCandidateRow.valid_to > at,
                ),
            )
            .order_by(
                KnowledgeClaimCandidateRow.predicate,
                KnowledgeClaimCandidateRow.created_at,
                KnowledgeClaimCandidateRow.id,
            )
        )
        return self._as_of_claims(statement)

    def find_accepted_claims_history(
        self,
        *,
        workspace_id: int,
        subject_node_id: uuid.UUID,
        predicate: str | None = None,
    ) -> tuple[AsOfClaim, ...]:
        """어떤 노드에 대해 accepted였던 claim을 시점 제한 없이 읽는다.

        `find_accepted_claims_as_of`와 술어가 하나 다르다 — 구간 조건이
        없다. 그래서 live accepted와 닫힌 accepted가 함께 나오고,
        "언제 바뀌었나"를 valid_from·valid_to로 되짚을 수 있다.

        rejected는 여기서도 뺀다. 닫힌 accepted는 "한때 참이었다"지만
        rejected는 "참이었던 적이 없다"라, 둘을 같이 실으면 역사가
        아니라 소문이 된다.

        정렬은 valid_from 오름차순에 NULL이 먼저다. "언제부터인지
        모르는 주장"을 시간선 맨 앞에 둬야 그 뒤 구간이 이어지는 순서로
        읽힌다. 같은 valid_from끼리는 관측 순서를 대신하는
        `created_at`과 id로 묶어 매번 같은 순서를 준다 — 근거 링크의
        event_at은 inner join이 필요해, 관측이 없는 claim을 조용히
        떨어뜨린다.
        """
        statement = self._accepted_claims_of_subject(
            workspace_id=workspace_id,
            subject_node_id=subject_node_id,
            predicate=predicate,
        ).order_by(
            nullsfirst(KnowledgeClaimCandidateRow.valid_from.asc()),
            KnowledgeClaimCandidateRow.created_at,
            KnowledgeClaimCandidateRow.id,
        )
        return self._as_of_claims(statement)

    def find_accepted_claims_by_text(
        self,
        *,
        workspace_id: int,
        query_texts: Sequence[str],
        at: datetime,
        limit: int,
    ) -> tuple[AsOfClaim, ...]:
        """키워드와 겹치는 accepted claim을 workspace 횡단으로 모은다.

        subject 노드를 거치지 않는다 — 여러 세션·여러 entity에 흩어진
        사건 claim을 시간선 하나로 모으는 것이 목적이다.

        ILIKE 부분 일치를 쓴다. `%`·`_`는 escape해 키워드가
        와일드카드로 새지 않게 한다. value는 JSONB라 문자열로 cast해
        비교한다 — 문자열 값은 JSON 따옴표가 붙지만 부분 일치라
        영향이 없다.

        정렬은 valid_from 오름차순이되 NULL이 뒤다. 날짜를 모르는
        사건이 앞에 서면 타임라인의 번호가 사건의 순서를 뜻하지 않게
        된다.
        """
        cleaned = [text.strip() for text in query_texts if text.strip()]
        if not cleaned:
            return ()
        columns = (
            KnowledgeClaimCandidateRow.predicate,
            KnowledgeClaimCandidateRow.value.cast(String),
            KnowledgeClaimCandidateRow.statement,
        )
        matchers: list[ColumnElement[bool]] = []
        for keyword in cleaned:
            escaped = (
                keyword.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            pattern = f"%{escaped}%"
            for column in columns:
                matchers.append(column.ilike(pattern, escape="\\"))
        statement = (
            select(KnowledgeClaimCandidateRow)
            .where(
                KnowledgeClaimCandidateRow.workspace_id == workspace_id,
                KnowledgeClaimCandidateRow.resolution_status
                == AssertionResolutionStatus.ACCEPTED.value,
                or_(
                    KnowledgeClaimCandidateRow.valid_from.is_(None),
                    KnowledgeClaimCandidateRow.valid_from <= at,
                ),
                or_(*matchers),
            )
            .order_by(
                nullslast(KnowledgeClaimCandidateRow.valid_from.asc()),
                KnowledgeClaimCandidateRow.created_at,
                KnowledgeClaimCandidateRow.id,
            )
            .limit(limit)
        )
        return self._as_of_claims(statement)

    def _accepted_claims_of_subject(
        self,
        *,
        workspace_id: int,
        subject_node_id: uuid.UUID,
        predicate: str | None,
    ) -> Select[tuple[KnowledgeClaimCandidateRow]]:
        """어떤 노드에 대한 accepted claim을 고르는 술어를 만든다.

        as-of와 history가 대상 선정에서 갈리면 "닫혔다"의 뜻이 두 갈래가
        된다. 구간과 정렬만 각자 얹도록 공통부를 한 곳에 둔다.

        subject 해소는 `find_claim_candidates`와 같은 방식이다. 노드를
        직접 가리키는 claim과, 그 노드로 해소된 entity 후보를 가리키는
        claim 둘 다 같은 대상에 대한 주장이기 때문이다.
        """
        statement = (
            select(KnowledgeClaimCandidateRow)
            .outerjoin(
                KnowledgeEntityCandidateRow,
                KnowledgeClaimCandidateRow.subject_entity_candidate_id
                == KnowledgeEntityCandidateRow.id,
            )
            .where(
                KnowledgeClaimCandidateRow.workspace_id == workspace_id,
                or_(
                    KnowledgeClaimCandidateRow.subject_node_id
                    == subject_node_id,
                    KnowledgeEntityCandidateRow.resolved_node_id
                    == subject_node_id,
                ),
                KnowledgeClaimCandidateRow.resolution_status
                == AssertionResolutionStatus.ACCEPTED.value,
            )
        )
        if predicate is not None:
            statement = statement.where(
                KnowledgeClaimCandidateRow.predicate == predicate
            )
        return statement

    def _as_of_claims(
        self,
        statement: Select[tuple[KnowledgeClaimCandidateRow]],
    ) -> tuple[AsOfClaim, ...]:
        """claim 행을 읽기 경로가 쓰는 모양으로 옮긴다."""
        return tuple(
            AsOfClaim(
                claim_id=row.id,
                predicate=row.predicate,
                value_type=row.value_type,
                value=row.value,
                statement=row.statement,
                valid_from=row.valid_from,
                valid_to=row.valid_to,
            )
            for row in self._session.scalars(statement).all()
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

    def find_decided_by_idempotency_key(
        self,
        *,
        workspace_id: int,
        idempotency_key: str,
    ) -> StoredMutationProposal | None:
        """같은 검토 단위에 이미 내려진 결정을 찾는다.

        결정된 행이 있으면 판정기가 그 구성(member_hash)과 지금의 모순을
        견줘, 같은 사실이면 다시 묻지 않고 구성이 달라졌으면 새 검토
        사건을 연다.
        """
        row = self._session.scalar(
            select(KnowledgeMutationProposalRow).where(
                KnowledgeMutationProposalRow.workspace_id == workspace_id,
                KnowledgeMutationProposalRow.idempotency_key
                == idempotency_key,
                KnowledgeMutationProposalRow.status.in_(
                    ("approved", "applied", "rejected")
                ),
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

    def get_contradiction_status(
        self,
        *,
        workspace_id: int,
        proposal_id: uuid.UUID,
    ) -> str | None:
        """모순 안건 하나의 현재 상태를 읽는다. 없으면 None이다."""
        return self._session.scalar(
            select(KnowledgeMutationProposalRow.status).where(
                KnowledgeMutationProposalRow.workspace_id == workspace_id,
                KnowledgeMutationProposalRow.id == proposal_id,
                KnowledgeMutationProposalRow.proposal_kind
                == "contradiction",
            )
        )

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
            ValueError: reviewer가 비어 있다. 결정 저널은 누가 정했는지를
                저장소 수준에서 요구한다.
        """
        if not reviewer.strip():
            raise ValueError("reviewer가 비어 있어 결정을 기록할 수 없다.")
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
    ) -> list[ApprovedProposal]:
        """승인됐지만 아직 적용되지 않은 안건을 명령과 함께 모은다."""
        proposal_rows = self._session.scalars(
            select(KnowledgeMutationProposalRow)
            .where(
                KnowledgeMutationProposalRow.workspace_id == workspace_id,
                KnowledgeMutationProposalRow.status == "approved",
            )
            .order_by(KnowledgeMutationProposalRow.created_at)
        ).all()
        if not proposal_rows:
            return []
        proposal_ids = [row.id for row in proposal_rows]
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
                    claim_candidate_id=row.claim_candidate_id,
                    operation_data=row.operation_data or {},
                )
            )
        return [
            ApprovedProposal(
                proposal_id=row.id,
                proposal_kind=row.proposal_kind,
                # 승인 행에는 reviewer가 반드시 있지만 컬럼은 pending 행을
                # 위해 nullable이라 빈 문자열로 받아 둔다.
                reviewer=row.reviewer or "",
                detector=row.detector,
                detector_version=row.detector_version,
                resolver_metadata=dict(row.resolver_metadata or {}),
                operations=tuple(grouped.get(row.id, ())),
            )
            for row in proposal_rows
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

        Raises:
            ValueError: reviewer가 비어 있다. 결정 저널은 누가 정했는지를
                저장소 수준에서 요구한다.
        """
        if not reviewer.strip():
            raise ValueError("reviewer가 비어 있어 결정을 기록할 수 없다.")
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

        `add_duplicate_proposal`과 같이 계류·접힘 상태의 같은 key 행은
        되살려 갈아끼운다. `(workspace_id, idempotency_key)` UNIQUE가
        상태를 구분하지 않기 때문이다. 반면 이미 결정된 행(approved·
        applied·rejected)은 행과 operation을 그대로 보존하고 id만
        돌려준다 — 사람의 결정은 판정 재실행이 덮을 수 없다.

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
        if existing is not None and existing.status in (
            "approved",
            "applied",
            "rejected",
        ):
            logger.info(
                "contradiction_proposal_already_decided_skip",
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
        merge_into_node_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """같은 대상 후보들을 하나로 합치는 계획서를 쓴다.

        `merge_into_node_id`를 주면 1번 명령이 노드를 새로 만들지 않고 그
        노드로 붙는다는 표시를 명령 재료에 함께 적는다.

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

        operation_data: dict[str, JsonValue] = {
            "proposed_type": proposed_type,
            "proposed_name": proposed_name,
        }
        if merge_into_node_id is not None:
            operation_data["merge_into_node_id"] = str(merge_into_node_id)
        self._session.add(
            KnowledgeMutationOperationRow(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                proposal_id=proposal_id,
                sequence=1,
                operation_type="create_entity",
                entity_candidate_id=representative_candidate_id,
                operation_data=operation_data,
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

    def find_entity_nodes_by_types(
        self,
        *,
        entity_types: Sequence[str],
    ) -> list[EntityCardSource]:
        """고른 종류의 살아 있는 entity 노드를 모두 돌려준다.

        claim과 join하지 않는다. claim이 아직 없는 노드도 정의가 고른
        종류면 대상이기 때문이다.

        정렬을 DB에 맡긴다. 이름은 비어 있을 수 있어 표시에 쓰는 값과
        같은 식으로 메워 그 값으로 줄을 세우고, 이름이 같으면 식별자를
        문자열로 캐 갈라 실행마다 같은 차례가 나오게 한다.

        줄 세우기에 C 대조 규칙을 못 박는다. DB 기본 대조 규칙은 로케일
        설정에 따라 한글의 앞뒤가 달라져, 같은 코드가 서버마다 다른
        차례를 내고 파이썬 쪽 문자열 비교와도 어긋나기 때문이다.
        """
        display_name = func.coalesce(
            KnowledgeNodeRow.display_name,
            KnowledgeNodeRow.canonical_key,
            cast(KnowledgeNodeRow.id, Text),
        )
        statement = (
            select(KnowledgeNodeRow.id, display_name)
            .where(
                KnowledgeNodeRow.workspace_id == self._workspace_id,
                KnowledgeNodeRow.entity_type.in_(list(entity_types)),
                KnowledgeNodeRow.lifecycle_state == "active",
            )
            .order_by(
                collate(display_name, "C"),
                collate(cast(KnowledgeNodeRow.id, Text), "C"),
            )
        )
        return [
            EntityCardSource(node_id=node_id, display_name=name)
            for node_id, name in self._session.execute(statement).all()
        ]

    def get_or_create_definition_artifact(
        self,
        *,
        definition_id: uuid.UUID,
        channel_id: uuid.UUID,
        kind: str,
        subject_node_id: uuid.UUID,
        title: str,
        folder_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """정의가 대상에 만드는 문서를 찾거나 새로 만든다.

        (정의, 대상)으로만 찾는다. 그 짝의 UNIQUE가 이 문서의 유일성을
        말하는 제약이므로, 조건을 넓히면 정의가 kind나 채널을 바꾼 뒤
        같은 짝에 문서가 둘 생기려다 제약에 막힌다.

        이미 있으면 제목도 채널도 덮어쓰지 않는다. 제목은 문서의 정체성
        이고, 채널을 옮기는 일은 컴파일이 아니라 사람의 결정이다.

        폴더도 새 행에만 적는다. 이미 있는 문서의 폴더는 덮어쓰지 않는다.
        폴더 이동은 사람의 결정이다.
        """
        found = self._session.scalar(
            select(KnowledgeArtifactRow.id).where(
                KnowledgeArtifactRow.workspace_id == self._workspace_id,
                KnowledgeArtifactRow.definition_id == definition_id,
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
                definition_id=definition_id,
                channel_id=channel_id,
                kind=kind,
                subject_node_id=subject_node_id,
                title=title,
                folder_id=folder_id,
            )
        )
        self._session.flush()
        return artifact_id

    def find_definition_artifact(
        self,
        *,
        definition_id: uuid.UUID,
        subject_node_id: uuid.UUID,
    ) -> uuid.UUID | None:
        """정의가 대상에 만든 문서를 찾기만 한다. 없으면 None이다.

        찾는 기준은 `get_or_create_definition_artifact`와 같은 (정의,
        대상)이고, 없을 때 행을 만들지 않는 것만 다르다.
        """
        return self._session.scalar(
            select(KnowledgeArtifactRow.id).where(
                KnowledgeArtifactRow.workspace_id == self._workspace_id,
                KnowledgeArtifactRow.definition_id == definition_id,
                KnowledgeArtifactRow.subject_node_id == subject_node_id,
            )
        )

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

    def find_current_revisions(
        self, *, workspace_id: int
    ) -> tuple[CurrentRevisionForProjection, ...]:
        """workspace의 모든 문서에서 current revision을 한 번에 읽는다.

        current revision은 컬럼이 아니라 문서별 판 번호의 최대값이다.
        `find_latest_revision_id_and_number`가 문서 하나에 하는 일을
        문서별 최대 판 번호 서브쿼리로 넓혀, 한 질의로 문서당 한 행만
        고른다. 판이 없는 문서는 판 쪽에서 시작해 조인하므로 자연히
        빠진다.

        Raises:
            ValueError: 저장소가 고정한 workspace와 다를 때 던진다.
        """
        if workspace_id != self._workspace_id:
            raise ValueError(
                f"저장소가 고정한 workspace {self._workspace_id}와 요청한"
                f" workspace {workspace_id}가 다르다."
            )

        latest = (
            select(
                KnowledgeArtifactRevisionRow.artifact_id.label("artifact_id"),
                func.max(KnowledgeArtifactRevisionRow.revision_number).label(
                    "revision_number"
                ),
            )
            .where(
                KnowledgeArtifactRevisionRow.workspace_id == workspace_id,
            )
            .group_by(KnowledgeArtifactRevisionRow.artifact_id)
            .subquery()
        )
        statement = (
            select(
                KnowledgeArtifactRevisionRow.artifact_id,
                KnowledgeArtifactRow.title,
                KnowledgeArtifactRevisionRow.id,
                KnowledgeArtifactRevisionRow.revision_number,
                KnowledgeArtifactRevisionRow.blocks,
                KnowledgeArtifactRevisionRow.created_at,
            )
            .select_from(KnowledgeArtifactRevisionRow)
            .join(
                latest,
                (
                    KnowledgeArtifactRevisionRow.artifact_id
                    == latest.c.artifact_id
                )
                & (
                    KnowledgeArtifactRevisionRow.revision_number
                    == latest.c.revision_number
                ),
            )
            .join(
                KnowledgeArtifactRow,
                KnowledgeArtifactRow.id
                == KnowledgeArtifactRevisionRow.artifact_id,
            )
            .where(
                KnowledgeArtifactRevisionRow.workspace_id == workspace_id,
                KnowledgeArtifactRow.workspace_id == workspace_id,
            )
            .order_by(KnowledgeArtifactRevisionRow.artifact_id)
        )
        return tuple(
            CurrentRevisionForProjection(
                artifact_id=artifact_id,
                title=title,
                revision_id=revision_id,
                revision_number=revision_number,
                blocks=deserialize_blocks(blocks),
                created_at=created_at,
            )
            for (
                artifact_id,
                title,
                revision_id,
                revision_number,
                blocks,
                created_at,
            ) in self._session.execute(statement).all()
        )

    def find_latest_revision_blocks(
        self,
        *,
        artifact_id: uuid.UUID,
    ) -> tuple[ArtifactBlock, ...] | None:
        """최신 발행 판의 블록을 돌려준다. 발행 판이 없으면 None이다.

        최신 판을 고르는 기준은 `find_latest_revision_id_and_number`와 같은
        판 번호 최대값이다. 기준이 갈리면 같은 문서를 두 코드가 다르게
        가리킨다.
        """
        raw = self._session.scalar(
            select(KnowledgeArtifactRevisionRow.blocks)
            .where(
                KnowledgeArtifactRevisionRow.workspace_id
                == self._workspace_id,
                KnowledgeArtifactRevisionRow.artifact_id == artifact_id,
            )
            .order_by(KnowledgeArtifactRevisionRow.revision_number.desc())
            .limit(1)
        )
        if raw is None:
            return None
        return deserialize_blocks(raw)

    def list_reusable_change_reasons(
        self,
        *,
        artifact_id: uuid.UUID,
        base_revision_id: uuid.UUID,
    ) -> dict[str, str]:
        """같은 기준 판 위에 선 계류 변경안에서 수정 이유를 모아 온다.

        재료는 계류 변경안뿐이다. 발행 판의 블록에 붙은 이유는 그 판을
        만들 때 비교한 더 앞의 판을 두고 쓴 문장이라, 지금 기준 판과
        짝짓는 이유로 다시 쓸 수 없다.
        """
        found: dict[str, str] = {}
        for raw in self._session.scalars(
            select(KnowledgeArtifactChangeProposalRow.blocks).where(
                KnowledgeArtifactChangeProposalRow.workspace_id
                == self._workspace_id,
                KnowledgeArtifactChangeProposalRow.artifact_id
                == artifact_id,
                KnowledgeArtifactChangeProposalRow.status == "pending",
                KnowledgeArtifactChangeProposalRow.base_revision_id
                == base_revision_id,
            )
        ):
            for block in deserialize_blocks(raw):
                if block.change_reason is not None:
                    found[block_content_hash(block)] = block.change_reason
        return found

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

    def list_reusable_narratives(
        self,
        *,
        artifact_id: uuid.UUID,
    ) -> dict[str, str]:
        """다시 쓸 수 있는 산문을 블록 지문으로 찾아 모은다.

        최신 판을 고르는 기준은 `find_latest_revision_id_and_number`와
        같은 판 번호 최대값이다. 기준이 갈리면 같은 문서를 두 코드가
        다르게 가리킨다.

        계류 변경안을 뒤에 얹는다. 같은 지문이 양쪽에 있으면 사람 앞에
        더 가까이 놓인 쪽을 쓴다는 뜻이며, 순서를 못박아야 실행마다
        결과가 흔들리지 않는다.
        """
        found: dict[str, str] = {}
        latest_blocks = self._session.scalar(
            select(KnowledgeArtifactRevisionRow.blocks)
            .where(
                KnowledgeArtifactRevisionRow.workspace_id
                == self._workspace_id,
                KnowledgeArtifactRevisionRow.artifact_id == artifact_id,
            )
            .order_by(KnowledgeArtifactRevisionRow.revision_number.desc())
            .limit(1)
        )
        if latest_blocks:
            self._collect_narratives(found, latest_blocks)

        for raw in self._session.scalars(
            select(KnowledgeArtifactChangeProposalRow.blocks).where(
                KnowledgeArtifactChangeProposalRow.workspace_id
                == self._workspace_id,
                KnowledgeArtifactChangeProposalRow.artifact_id
                == artifact_id,
                KnowledgeArtifactChangeProposalRow.status == "pending",
            )
        ):
            self._collect_narratives(found, raw)
        return found

    @staticmethod
    def _collect_narratives(
        found: dict[str, str], raw: Sequence[Mapping[str, Any]]
    ) -> None:
        """저장된 블록에서 산문을 지문에 걸어 모은다."""
        for block in deserialize_blocks(raw):
            if block.narrative is not None:
                found[block_content_hash(block)] = block.narrative

    def _lock_artifact(self, artifact_id: uuid.UUID) -> None:
        """문서 행을 transaction이 끝날 때까지 잠근다.

        컴파일이 변경안을 저장하는 자리와 검토가 새 판을 쌓는 자리가 이
        행 하나를 두고 줄을 선다. 그래야 기준 판을 읽은 뒤 쓰기까지의
        사이에 다른 쪽이 새 판을 커밋하지 못한다. 잠그지 않으면 컴파일이
        낡은 기준 판을 적은 계류를 남기고, 그 계류는 발행이 받아 주지
        않는데 다음 컴파일은 내용 지문이 같아 건너뛰므로 스스로 풀리지
        않는다.

        문서 행은 이 저장소에서 가장 바깥 잠금이다. 문서 행과 변경안 행을
        함께 잡는 경로는 모두 문서 행을 먼저 잡는다. 컴파일은 계류를 접기
        전에, 발행과 단건 판정은 변경안 행을 FOR UPDATE로 읽기 전에 이
        잠금을 잡는다. 잡는 차례가 한 방향뿐이라 서로 기다리는 짝이
        생기지 않는다. 변경안 행만 잡고 문서 행은 잡지 않는 경로가 있어도
        그 경로는 문서 행을 기다리지 않으므로 짝이 되지 못한다.

        같은 transaction에서 두 번 잡아도 된다. 이미 쥔 행을 다시 잡는
        것은 아무 일도 하지 않으므로, 잠금이 필요한 함수마다 스스로
        잡아도 서로 방해하지 않는다.

        문서 행이 없으면 아무것도 잠그지 않고 지나간다. 없는 문서에 다는
        변경안은 어차피 FK가 막는다.
        """
        self._session.execute(
            select(KnowledgeArtifactRow.id)
            .where(
                KnowledgeArtifactRow.workspace_id == self._workspace_id,
                KnowledgeArtifactRow.id == artifact_id,
            )
            .with_for_update()
        )

    def abandon_pending_proposals(
        self,
        *,
        artifact_id: uuid.UUID,
        except_content_hash: str | None = None,
    ) -> int:
        """문서의 계류안을 접되 지정한 현재 내용은 남긴다.

        접기 전에 문서 행을 잠근다. 이 함수를 부르는 컴파일은 이어서
        변경안을 저장하며 문서 행을 잡으므로, 여기서 미리 잡아 두어야
        문서 행을 먼저 잡는 차례가 지켜진다.
        """
        self._lock_artifact(artifact_id)
        statement = update(KnowledgeArtifactChangeProposalRow).where(
                KnowledgeArtifactChangeProposalRow.workspace_id
                == self._workspace_id,
                KnowledgeArtifactChangeProposalRow.artifact_id == artifact_id,
                KnowledgeArtifactChangeProposalRow.status == "pending",
            )
        if except_content_hash is not None:
            statement = statement.where(
                KnowledgeArtifactChangeProposalRow.content_hash
                != except_content_hash
            )
        result = self._session.execute(statement.values(status="abandoned"))
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

        문서 행을 잠근 뒤 최신 판을 읽어 `base_revision_id`와 같은지 본다.
        호출자가 기준 판을 읽은 시점과 여기 도착한 시점 사이에 다른
        검토가 새 판을 냈으면 낡은 기준의 계류가 되기 때문이다. 다르면
        `ArtifactProposalConflict`를 던진다. 새 예외를 두지 않는 것은
        호출자가 이미 이 예외를 그 문서 하나만 접고 나머지는 그대로 두는
        신호로 다루고 있어서다.

        Raises:
            ArtifactBlockError: 블록이 근거 계약을 어겼을 때 던진다.
            ArtifactProposalConflict: 같은 키를 이미 결정된 변경안이 쓰고
                있거나, 기준 판이 최신이 아닐 때 던진다.
        """
        # 근거 없는 문장을 막는 마지막 자리다. 저장 전에 본다.
        validate_blocks(blocks)
        payload = serialize_blocks(blocks)

        self._lock_artifact(artifact_id)
        latest = self.find_latest_revision_id_and_number(
            artifact_id=artifact_id,
        )
        latest_revision_id = None if latest is None else latest[0]

        existing = self._session.scalar(
            select(KnowledgeArtifactChangeProposalRow).where(
                KnowledgeArtifactChangeProposalRow.workspace_id
                == self._workspace_id,
                KnowledgeArtifactChangeProposalRow.idempotency_key
                == idempotency_key,
            )
        )
        if existing is not None and existing.status not in (
            "pending",
            "abandoned",
        ):
            raise ArtifactProposalConflict(
                f"{existing.status} 상태의 변경안 {existing.id}가 같은"
                f" 멱등 키를 쓰고 있어 되살릴 수 없다."
            )
        if latest_revision_id != base_revision_id:
            raise ArtifactProposalConflict(
                f"문서 {artifact_id}의 최신 판이 {latest_revision_id}로"
                f" 옮겨가 기준 판 {base_revision_id} 위의 변경안을 저장할"
                f" 수 없다."
            )

        if existing is not None:
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
        for_update: bool = False,
    ) -> StoredArtifactProposal | None:
        """변경안 하나를 문서 제목·대상과 함께 읽는다.

        for_update가 참이면 그 변경안이 달린 문서 행을 먼저 잠그고, 이어
        변경안 행에 FOR UPDATE를 건다. 문서 행까지 잠그면 그 문서를
        건드리는 다른 일도 줄을 서지만, 판을 쌓는 쪽과 변경안을 저장하는
        쪽이 같은 문서를 두고 순서 없이 겹치면 낡은 기준 판의 계류가
        남는다. 문서 행을 먼저 잡는 차례는 `_lock_artifact`가 설명한다.
        잠금은 transaction이 끝날 때 풀린다.
        """
        statement = self._proposal_statement().where(
            KnowledgeArtifactChangeProposalRow.id == proposal_id
        )
        if for_update:
            artifact_id = self._session.scalar(
                select(KnowledgeArtifactChangeProposalRow.artifact_id).where(
                    KnowledgeArtifactChangeProposalRow.workspace_id
                    == self._workspace_id,
                    KnowledgeArtifactChangeProposalRow.id == proposal_id,
                )
            )
            if artifact_id is not None:
                self._lock_artifact(artifact_id)
            statement = statement.with_for_update(
                of=KnowledgeArtifactChangeProposalRow
            )
        row = self._session.execute(statement).first()
        if row is None:
            return None
        return _artifact_proposal_to_domain(row[0], row[1], row[2])

    def list_pending_proposals(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[StoredArtifactProposal]:
        """검토를 기다리는 변경안을 오래된 순으로 읽는다.

        정렬을 `(created_at, id)`로 고정한다. 시각이 같은 행이 있으면
        페이지마다 순서가 흔들려 같은 행이 두 쪽에 나오거나 아예 빠질 수
        있기 때문이다. limit/offset은 그 순서 위에서 자른다.
        """
        statement = (
            self._proposal_statement()
            .where(KnowledgeArtifactChangeProposalRow.status == "pending")
            .order_by(
                KnowledgeArtifactChangeProposalRow.created_at,
                KnowledgeArtifactChangeProposalRow.id,
            )
        )
        if offset:
            statement = statement.offset(offset)
        if limit is not None:
            statement = statement.limit(limit)
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

    def lock_owner_user_ids(
        self, *, artifact_id: uuid.UUID
    ) -> frozenset[int]:
        """문서 행을 잠그고 그 문서의 담당자 사용자 id를 읽는다.

        담당자를 지정·해제하는 경로도 같은 문서 행을 잠근다. 그래서 명단을
        바꾸는 일과 결정을 확정하는 일이 이 행 하나를 두고 줄을 선다.
        잠금은 transaction이 끝날 때 풀린다.

        명단을 workspace로 좁히지 않는다. 문서 행 잠금이 이미 이 저장소의
        workspace를 통과한 문서만 잡으므로, 담당자 행은 그 문서에 달린
        것으로 충분하다.
        """
        self._lock_artifact(artifact_id)
        return frozenset(
            self._session.scalars(
                select(ArtifactOwnerRow.user_id).where(
                    ArtifactOwnerRow.artifact_id == artifact_id
                )
            ).all()
        )

    def add_owner_if_absent(
        self, *, artifact_id: uuid.UUID, user_id: int, granted_by: int
    ) -> bool:
        """담당자 행을 넣되 이미 있으면 그대로 둔다. 넣었으면 참이다.

        ON CONFLICT DO NOTHING을 (문서, 사용자) 키에 한정해 건다. 예외를
        잡아 거르면 어떤 제약이 막았는지 문자열로 가려내야 하고, 외래 키가
        막은 잘못된 부여까지 함께 삼킬 수 있다.
        """
        result = self._session.execute(
            pg_insert(ArtifactOwnerRow)
            .values(
                artifact_id=artifact_id,
                user_id=user_id,
                granted_by=granted_by,
            )
            .on_conflict_do_nothing(index_elements=["artifact_id", "user_id"])
        )
        self._session.flush()
        return result.rowcount > 0

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

        쌓기 전에 문서 행을 잠근다. 변경안을 저장하는 쪽도 같은 행을
        잠그므로, 그쪽이 기준 판을 확인하고 쓰는 동안 이쪽이 새 판을
        커밋하지 못한다.
        """
        self._lock_artifact(artifact_id)
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


class SqlAlchemyArtifactDefinitionRepository:
    """정의 행 읽기를 PostgreSQL로 구현한다.

    artifact 저장소와 같이 workspace를 생성 시점에 고정한다.
    """

    def __init__(self, session: Session, workspace_id: int | None) -> None:
        self._session = session
        self._scoped_workspace_id = workspace_id

    @property
    def _workspace_id(self) -> int:
        """고정된 workspace를 돌려준다. 없으면 쓰지 못하게 막는다."""
        if self._scoped_workspace_id is None:
            raise RuntimeError(
                "artifact 정의 저장소는 workspace_id를 받은 UnitOfWork에서만"
                " 쓸 수 있다."
            )
        return self._scoped_workspace_id

    def find_channel_style(self, *, channel_id: uuid.UUID) -> str | None:
        """채널에 걸린 문체 preset id를 읽는다. 없으면 None이다.

        workspace를 조건에 함께 건다. 채널 식별자만으로 찾으면 남의
        workspace 채널의 문체가 이 workspace 문서에 실린다.
        """
        return self._session.scalar(
            select(ChannelRow.style_preset).where(
                ChannelRow.id == channel_id,
                ChannelRow.workspace_id == self._workspace_id,
            )
        )

    def find_channel_purposes(self, *, channel_id: uuid.UUID) -> tuple[str, ...]:
        """채널이 고른 목적 preset id를 고른 순서대로 읽는다. 없으면 빈 튜플이다.

        목적은 채널 칸이 아니라 channel_purposes 행으로 산다. 채널 하나가
        목적을 여러 개 고를 수 있어서다. position이 사람이 고른 차례라
        그 순서로 줄을 세운다.

        workspace를 조건에 함께 건다. 채널 식별자만으로 찾으면 남의
        workspace 채널의 목적이 이 workspace 문서에 실린다.
        """
        return tuple(
            self._session.scalars(
                select(ChannelPurposeRow.purpose_preset)
                .join(ChannelRow, ChannelRow.id == ChannelPurposeRow.channel_id)
                .where(
                    ChannelPurposeRow.channel_id == channel_id,
                    ChannelRow.workspace_id == self._workspace_id,
                )
                .order_by(ChannelPurposeRow.position)
            ).all()
        )

    def list_definitions(self) -> tuple[StoredArtifactDefinition, ...]:
        """workspace의 정의를 식별자 사전순으로 모두 읽는다.

        정렬을 DB에 맡긴다. 식별자를 문자열로 캐 C 대조 규칙으로 줄을
        세우므로, 서버 로케일이 달라도 실행마다 같은 차례가 나온다.

        선택 규칙 역직렬화가 던지면 그대로 올려 보낸다. 깨진 행 하나를
        건너뛰면 그 정의의 문서만 조용히 비기 때문이다.

        title_prefix는 kind와 같은 값으로 채운다. 아직 제목 앞자리를
        따로 저장하는 칸이 없다.

        folder_id는 저장된 값을 그대로 싣는다. 컴파일이 만드는 문서가
        어느 폴더에 설지는 정의에 적혀 있다.

        Raises:
            SelectionSpecError: 저장된 선택 규칙을 읽을 수 없을 때 던진다.
        """
        statement = (
            select(
                ArtifactDefinitionRow.id,
                ArtifactDefinitionRow.channel_id,
                ArtifactDefinitionRow.kind,
                ArtifactDefinitionRow.selection_spec,
                ArtifactDefinitionRow.folder_id,
            )
            .where(ArtifactDefinitionRow.workspace_id == self._workspace_id)
            .order_by(collate(cast(ArtifactDefinitionRow.id, Text), "C"))
        )
        return tuple(
            StoredArtifactDefinition(
                id=definition_id,
                channel_id=channel_id,
                kind=kind,
                selection_spec=deserialize_selection_spec(selection_spec),
                title_prefix=kind,
                folder_id=folder_id,
            )
            for (
                definition_id,
                channel_id,
                kind,
                selection_spec,
                folder_id,
            ) in self._session.execute(statement).all()
        )


class SqlAlchemyRelationRepository:
    """관계 한 걸음 읽기를 PostgreSQL로 구현한다.

    artifact 저장소와 같이 workspace를 생성 시점에 고정한다.
    """

    def __init__(self, session: Session, workspace_id: int | None) -> None:
        self._session = session
        self._scoped_workspace_id = workspace_id

    @property
    def _workspace_id(self) -> int:
        """고정된 workspace를 돌려준다. 없으면 쓰지 못하게 막는다."""
        if self._scoped_workspace_id is None:
            raise RuntimeError(
                "관계 저장소는 workspace_id를 받은 UnitOfWork에서만 쓸 수"
                " 있다."
            )
        return self._scoped_workspace_id

    def find_edges(
        self,
        *,
        node_ids: Sequence[uuid.UUID],
        relation_type: str,
        direction: str,
        now: datetime,
    ) -> list[StoredRelationEdge]:
        """주어진 노드에 걸린 살아 있는 관계 간선을 읽는다.

        끝점 해소는 `find_claim_candidates`의 subject 해소와 같은
        방식이다. 노드를 직접 가리키는 끝점과, 그 노드로 해소된 entity
        후보를 가리키는 끝점은 같은 대상을 가리키기 때문이다. 두 칸을
        coalesce로 한 값으로 합쳐, 걸러 내기와 돌려주기 양쪽이 같은
        표현을 본다 — 주어진 노드를 원본 칸으로만 맞추면 후보를 거쳐
        들어온 간선이 통째로 빠져 경로가 한 걸음 앞에서 끊긴다.

        해소되지 않은 끝점이 있으면 그 행은 빠진다. 어느 노드를
        가리키는지 정해지지 않은 끝점은 순회의 다음 출발점이 될 수 없다.

        생사 판정은 domain.temporal.claim_not_closed_at과 같은 술어를
        SQL로 옮긴 것이다. valid_from은 보지 않고 닫힌 관계만 뺀다.

        상태로 거르는 것은 `find_claim_candidates`와 같다 — rejected는
        참이었던 적이 없고, superseded는 재추출이 대체한 구 배치라
        새 배치와 함께 실리면 같은 관계가 두 번 들어간다.

        정렬을 DB에 맡긴다. 식별자를 문자열로 캐 C 대조 규칙으로 줄을
        세우므로, 서버 로케일이 달라도 같은 차례가 나온다.

        해소된 끝점 노드를 한 번 더 이어 표시 이름과 attributes를 함께
        캔다. 순회가 이웃을 이름 차례로 세우고, 노출 수준을 적용하는
        쪽이 행위자 키·이메일을 보므로, 이것을 걸음마다 따로 물으면
        왕복이 곱절이 된다.
        """
        source_candidate = aliased(KnowledgeEntityCandidateRow)
        target_candidate = aliased(KnowledgeEntityCandidateRow)
        source_node = aliased(KnowledgeNodeRow)
        target_node = aliased(KnowledgeNodeRow)
        source_endpoint = func.coalesce(
            KnowledgeRelationCandidateRow.source_node_id,
            source_candidate.resolved_node_id,
        )
        target_endpoint = func.coalesce(
            KnowledgeRelationCandidateRow.target_node_id,
            target_candidate.resolved_node_id,
        )
        wanted = list(node_ids)
        if direction == DIRECTION_OUT:
            reachable = source_endpoint.in_(wanted)
        elif direction == DIRECTION_IN:
            reachable = target_endpoint.in_(wanted)
        elif direction == DIRECTION_ANY:
            reachable = or_(
                source_endpoint.in_(wanted), target_endpoint.in_(wanted)
            )
        else:
            raise ValueError(f"알 수 없는 관계 방향이다: {direction}")

        statement = (
            select(
                KnowledgeRelationCandidateRow.id,
                source_endpoint,
                target_endpoint,
                KnowledgeRelationCandidateRow.assertion_text,
                source_node.display_name,
                target_node.display_name,
                source_node.attributes,
                target_node.attributes,
            )
            .outerjoin(
                source_candidate,
                KnowledgeRelationCandidateRow.source_entity_candidate_id
                == source_candidate.id,
            )
            .outerjoin(
                target_candidate,
                KnowledgeRelationCandidateRow.target_entity_candidate_id
                == target_candidate.id,
            )
            .outerjoin(source_node, source_node.id == source_endpoint)
            .outerjoin(target_node, target_node.id == target_endpoint)
            .where(
                KnowledgeRelationCandidateRow.workspace_id
                == self._workspace_id,
                KnowledgeRelationCandidateRow.relation_type == relation_type,
                KnowledgeRelationCandidateRow.resolution_status.notin_(
                    (
                        AssertionResolutionStatus.REJECTED.value,
                        AssertionResolutionStatus.SUPERSEDED.value,
                    )
                ),
                or_(
                    KnowledgeRelationCandidateRow.valid_to.is_(None),
                    KnowledgeRelationCandidateRow.valid_to > now,
                ),
                source_endpoint.is_not(None),
                target_endpoint.is_not(None),
                reachable,
            )
            .order_by(
                collate(cast(KnowledgeRelationCandidateRow.id, Text), "C")
            )
        )
        return [
            StoredRelationEdge(
                id=relation_id,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                assertion_text=assertion_text,
                source_display_name=source_display_name,
                target_display_name=target_display_name,
                source_attributes=dict(source_attributes or {}),
                target_attributes=dict(target_attributes or {}),
            )
            for (
                relation_id,
                source_node_id,
                target_node_id,
                assertion_text,
                source_display_name,
                target_display_name,
                source_attributes,
                target_attributes,
            ) in self._session.execute(statement).all()
        ]


class SqlAlchemyBlockVerdictRepository:
    """블록 결정 저널의 영속성을 PostgreSQL로 구현한다.

    artifact 저장소와 같이 workspace를 생성 시점에 고정한다. 결정 행이
    가리키는 변경안 FK는 workspace를 함께 보지 않으므로, 남의 workspace
    변경안에 결정을 다는 일을 DB가 막지 못한다. 그 자리를 이 저장소가
    읽기와 쓰기 양쪽에서 대신 막는다.
    """

    def __init__(self, session: Session, workspace_id: int | None) -> None:
        self._session = session
        self._scoped_workspace_id = workspace_id

    @property
    def _workspace_id(self) -> int:
        """고정된 workspace를 돌려준다. 없으면 쓰지 못하게 막는다."""
        if self._scoped_workspace_id is None:
            raise RuntimeError(
                "블록 결정 저장소는 workspace_id를 받은 UnitOfWork에서만"
                " 쓸 수 있다."
            )
        return self._scoped_workspace_id

    def upsert_verdict(
        self,
        *,
        proposal_id: uuid.UUID,
        block_index: int,
        block_content_hash: str,
        verdict: str,
        rejection_reason: str | None,
        chosen_winner_claim_id: uuid.UUID | None,
        reviewer: str,
        reviewed_at: datetime,
    ) -> None:
        """블록 하나의 결정을 저널에 남긴다.

        `updated_at`을 set_에 직접 넣는다. `on_conflict_do_update`는 ORM의
        onupdate를 태우지 않아, 넣지 않으면 재판정한 행의 갱신 시각이 첫
        저장 때 값에 머문다.

        Raises:
            ValueError: 변경안이 고정된 workspace에 없을 때 던진다.
        """
        self._assert_proposal_in_workspace(proposal_id)
        statement = pg_insert(KnowledgeBlockVerdictRow).values(
            id=uuid.uuid4(),
            workspace_id=self._workspace_id,
            proposal_id=proposal_id,
            block_index=block_index,
            block_content_hash=block_content_hash,
            verdict=verdict,
            rejection_reason=rejection_reason,
            chosen_winner_claim_id=chosen_winner_claim_id,
            reviewer=reviewer,
            reviewed_at=reviewed_at,
        )
        statement = statement.on_conflict_do_update(
            constraint="uq_block_verdict_proposal_block",
            set_={
                "block_content_hash": statement.excluded.block_content_hash,
                "verdict": statement.excluded.verdict,
                "rejection_reason": statement.excluded.rejection_reason,
                "chosen_winner_claim_id": (
                    statement.excluded.chosen_winner_claim_id
                ),
                "reviewer": statement.excluded.reviewer,
                "reviewed_at": statement.excluded.reviewed_at,
                "updated_at": func.now(),
            },
        )
        self._session.execute(statement)
        self._session.flush()

    def insert_verdict_if_absent(
        self,
        *,
        proposal_id: uuid.UUID,
        block_index: int,
        block_content_hash: str,
        verdict: str,
        rejection_reason: str | None,
        chosen_winner_claim_id: uuid.UUID | None,
        reviewer: str,
        reviewed_at: datetime,
    ) -> bool:
        """결정이 없는 블록에만 결정을 쓴다.

        `ON CONFLICT DO NOTHING`이라 이미 결정이 있으면 한 컬럼도 바뀌지
        않는다. 넣었으면 True, 이미 있어서 건너뛰었으면 False다. 판단과
        쓰기가 한 문장 안에서 끝나므로, 미결정을 고른 뒤 사람이 단건
        결정을 저장해도 그 결정을 덮어쓰지 않는다.

        넣었는지는 RETURNING이 돌려준 행으로 본다. 이 조합에서 rowcount는
        -1로 나와 쓸 수 없고, 충돌해서 건너뛴 INSERT는 RETURNING 행이
        아예 없다.

        Raises:
            ValueError: 변경안이 고정된 workspace에 없을 때 던진다.
        """
        self._assert_proposal_in_workspace(proposal_id)
        statement = pg_insert(KnowledgeBlockVerdictRow).values(
            id=uuid.uuid4(),
            workspace_id=self._workspace_id,
            proposal_id=proposal_id,
            block_index=block_index,
            block_content_hash=block_content_hash,
            verdict=verdict,
            rejection_reason=rejection_reason,
            chosen_winner_claim_id=chosen_winner_claim_id,
            reviewer=reviewer,
            reviewed_at=reviewed_at,
        )
        statement = statement.on_conflict_do_nothing(
            constraint="uq_block_verdict_proposal_block",
        ).returning(KnowledgeBlockVerdictRow.id)
        inserted = self._session.execute(statement).first()
        self._session.flush()
        return inserted is not None

    def list_for_proposal(
        self, *, proposal_id: uuid.UUID
    ) -> tuple[StoredBlockVerdict, ...]:
        """변경안에 달린 결정을 block_index 순으로 읽는다."""
        rows = self._session.scalars(
            select(KnowledgeBlockVerdictRow)
            .where(
                KnowledgeBlockVerdictRow.workspace_id == self._workspace_id,
                KnowledgeBlockVerdictRow.proposal_id == proposal_id,
            )
            .order_by(KnowledgeBlockVerdictRow.block_index)
        ).all()
        return tuple(_block_verdict_to_domain(row) for row in rows)

    def find_rejected_hashes(
        self, *, artifact_id: uuid.UUID
    ) -> dict[str, str]:
        """artifact의 과거 반려 블록을 hash에서 사유로 모은다.

        결정 행은 변경안에 매달려 있으므로 변경안을 거쳐 문서로 올라간다.
        같은 지문에 반려가 여럿이면 나중 결정이 이긴다. 그래서 결정 시각
        오름차순으로 읽어 마지막 사유가 dict에 남게 한다.
        """
        rows = self._session.execute(
            select(
                KnowledgeBlockVerdictRow.block_content_hash,
                KnowledgeBlockVerdictRow.rejection_reason,
            )
            .join(
                KnowledgeArtifactChangeProposalRow,
                KnowledgeBlockVerdictRow.proposal_id
                == KnowledgeArtifactChangeProposalRow.id,
            )
            .where(
                KnowledgeBlockVerdictRow.workspace_id == self._workspace_id,
                KnowledgeArtifactChangeProposalRow.workspace_id
                == self._workspace_id,
                KnowledgeArtifactChangeProposalRow.artifact_id == artifact_id,
                KnowledgeBlockVerdictRow.verdict == "rejected",
            )
            .order_by(
                KnowledgeBlockVerdictRow.reviewed_at,
                KnowledgeBlockVerdictRow.block_index,
            )
        ).all()
        return {
            content_hash: reason or "" for content_hash, reason in rows
        }

    def _assert_proposal_in_workspace(self, proposal_id: uuid.UUID) -> None:
        """결정을 달 변경안이 고정된 workspace 것인지 확인한다.

        Raises:
            ValueError: 그 workspace에 그런 변경안이 없을 때 던진다.
        """
        found = self._session.scalar(
            select(KnowledgeArtifactChangeProposalRow.id).where(
                KnowledgeArtifactChangeProposalRow.id == proposal_id,
                KnowledgeArtifactChangeProposalRow.workspace_id
                == self._workspace_id,
            )
        )
        if found is None:
            raise ValueError(
                f"변경안 {proposal_id}는 workspace {self._workspace_id}에"
                " 없어 블록 결정을 달 수 없다."
            )


def _block_verdict_to_domain(
    row: KnowledgeBlockVerdictRow,
) -> StoredBlockVerdict:
    """저장된 블록 결정 row를 읽는 쪽이 쓸 형태로 되돌린다."""
    return StoredBlockVerdict(
        proposal_id=row.proposal_id,
        block_index=row.block_index,
        block_content_hash=row.block_content_hash,
        verdict=row.verdict,
        rejection_reason=row.rejection_reason,
        chosen_winner_claim_id=row.chosen_winner_claim_id,
        reviewer=row.reviewer,
        reviewed_at=row.reviewed_at,
    )


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
        origin=row.origin,
        created_at=row.created_at,
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

    def lock_lineage(
        self,
        *,
        workspace_id: int,
        ontology_id: str,
    ) -> None:
        """한 계보의 발행을 현재 트랜잭션이 끝날 때까지 직렬화한다.

        버전 이름은 기존 목록을 읽어 다음 번호를 세어 정한다. 두
        트랜잭션이 동시에 읽으면 같은 번호를 세고 뒤에 커밋하는 쪽이
        버전 UNIQUE 제약에 걸린다. 잠금을 먼저 잡으면 뒤에 온 쪽은
        앞의 커밋을 기다렸다가 최신 버전을 보고 번호를 센다.

        잠금 키는 고정 문구와 `workspace_id:ontology_id`를 각각
        `hashtext`로 접은 두 정수다. 같은 계보면 항상 같은 키가 나오고,
        고정 문구가 다른 용도의 advisory lock과 키 공간을 갈라 준다.
        트랜잭션 범위 잠금이라 커밋·롤백에서 저절로 풀린다.
        """
        self._session.execute(
            select(
                func.pg_advisory_xact_lock(
                    func.hashtext(literal("knowledge_ontology_publish")),
                    func.hashtext(literal(f"{workspace_id}:{ontology_id}")),
                )
            )
        )

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

    def list_pending(
        self,
        *,
        workspace_id: int,
        event_type: PipelineEventType,
        now: datetime,
        limit: int | None = None,
    ) -> tuple[PipelineEvent, ...]:
        """지금 처리할 수 있는 일을 상태 변경 없이 조회한다."""
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
