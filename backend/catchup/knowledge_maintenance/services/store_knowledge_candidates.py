"""추출 결과를 candidate로 저장한다.

여기서 두 가지가 일어난다.

**`local_key`가 실제 식별자가 된다.** Extractor는 `e1`, `c1`처럼 그 실행
안에서만 유효한 이름으로 서로를 가리킨다. 저장 시점에 entity를 먼저 넣어
식별자를 받고, 그것으로 claim과 relation의 참조를 FK로 바꾼다.

**레이어 1이 뽑은 Entity가 행이 된다.** 프롬프트가 고객과 상담원을 `m1`,
`m2`로 보여주고 Extractor가 그것을 관계의 끝점으로 쓰므로, 그 Entity가
`deterministic` candidate로 먼저 저장되어야 관계의 FK가 걸린다. 이것이
설계 문서 §7이 말한 "레이어 1 산출물의 통로"다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from decimal import Decimal

from catchup.knowledge_maintenance.contracts.extraction import EntityCandidateDraft
from catchup.knowledge_maintenance.contracts.extraction import KnowledgeCandidateBatch
from catchup.knowledge_maintenance.contracts.extraction import is_metadata_local_key
from catchup.knowledge_maintenance.contracts.extraction import metadata_local_key
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionMethod
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionRunSpec
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionRunStatus
from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    StoredCandidateBatch,
)
from catchup.knowledge_maintenance.domain.knowledge_node import NodeKind
from catchup.knowledge_maintenance.domain.observation import MetadataEntity
from catchup.knowledge_maintenance.domain.observation import StoredObservation
from catchup.knowledge_maintenance.ports.knowledge_candidates import (
    KnowledgeCandidateUnitOfWork,
)

# 결정론적 레이어의 산출물은 추론이 아니라 원문 구조에 적혀 있던 사실이다.
DETERMINISTIC_CONFIDENCE = Decimal("1.0")


class ObservationNodeMissing(RuntimeError):
    """Observation이 graph에 올라와 있지 않음을 알린다."""


@dataclass(frozen=True, slots=True)
class CandidateStorageResult:
    """저장 결과를 표현한다.

    Attributes:
        batch: 저장된 후보와 local_key 지도를 담는다.
        reused: 이미 저장된 실행이 있어 새로 넣지 않았는지 나타낸다.
    """

    batch: StoredCandidateBatch
    reused: bool = False


def store_knowledge_candidates(
    observation: StoredObservation,
    batch: KnowledgeCandidateBatch,
    *,
    spec: ExtractionRunSpec,
    uow: KnowledgeCandidateUnitOfWork,
    clock: Callable[[], datetime] | None = None,
) -> CandidateStorageResult:
    """추출 결과 한 벌을 후보로 저장한다.

    같은 Observation에 이미 실행 기록이 있으면 다시 저장하지 않는다. 후보를
    두 벌 쌓으면 resolution이 같은 대상을 여러 번 보게 된다.
    """
    clock = clock or _utcnow
    now = clock()

    with uow:
        node = uow.knowledge_nodes.get_for_resource(
            workspace_id=observation.workspace_id,
            node_kind=NodeKind.OBSERVATION,
            resource_id=observation.id,
        )
        if node is None:
            raise ObservationNodeMissing(
                f"observation {observation.id} has no graph node"
            )

        existing = uow.knowledge_candidates.count_runs_for_input(
            workspace_id=observation.workspace_id,
            input_node_id=node.id,
        )
        if existing:
            return CandidateStorageResult(
                batch=StoredCandidateBatch(run_id=uuid.UUID(int=0)),
                reused=True,
            )

        run = uow.knowledge_candidates.start_run(
            workspace_id=observation.workspace_id,
            input_node_id=node.id,
            spec=spec,
            started_at=now,
        )

        entity_ids = _store_entities(
            observation,
            batch,
            run_id=run.id,
            uow=uow,
        )
        claim_ids = _store_claims(
            observation,
            batch,
            run_id=run.id,
            entity_ids=entity_ids,
            spec=spec,
            uow=uow,
        )
        relation_ids = _store_relations(
            observation,
            batch,
            run_id=run.id,
            entity_ids=entity_ids,
            uow=uow,
        )
        evidence_count = _store_evidence(
            observation,
            batch,
            run_id=run.id,
            evidence_node_id=node.id,
            entity_ids=entity_ids,
            claim_ids=claim_ids,
            relation_ids=relation_ids,
            uow=uow,
        )

        uow.knowledge_candidates.complete_run(
            run_id=run.id,
            status=ExtractionRunStatus.SUCCEEDED,
            completed_at=clock(),
        )
        uow.commit()

        return CandidateStorageResult(
            batch=StoredCandidateBatch(
                run_id=run.id,
                entity_ids=entity_ids,
                claim_ids=claim_ids,
                relation_ids=relation_ids,
                evidence_link_count=evidence_count,
            )
        )


def _store_entities(
    observation: StoredObservation,
    batch: KnowledgeCandidateBatch,
    *,
    run_id: uuid.UUID,
    uow: KnowledgeCandidateUnitOfWork,
) -> dict[str, uuid.UUID]:
    """metadata Entity를 먼저, 그 다음 Extractor가 만든 Entity를 저장한다.

    순서가 중요하다. relation의 끝점이 `m1`을 가리킬 수 있으므로 그 행이 먼저
    있어야 한다.
    """
    entity_ids: dict[str, uuid.UUID] = {}

    for index, entity in enumerate(observation.observation.metadata_entities, start=1):
        local_key = metadata_local_key(index)
        entity_ids[local_key] = uow.knowledge_candidates.add_entity_candidate(
            workspace_id=observation.workspace_id,
            run_id=run_id,
            draft=_metadata_entity_draft(local_key, entity),
            extraction_method=ExtractionMethod.DETERMINISTIC,
            confidence=DETERMINISTIC_CONFIDENCE,
        )

    for draft in batch.entities:
        entity_ids[draft.local_key] = uow.knowledge_candidates.add_entity_candidate(
            workspace_id=observation.workspace_id,
            run_id=run_id,
            draft=draft,
            extraction_method=ExtractionMethod.LLM,
        )

    return entity_ids


def _metadata_entity_draft(
    local_key: str,
    entity: MetadataEntity,
) -> EntityCandidateDraft:
    """레이어 1 Entity를 Extractor 출력과 같은 형태로 맞춘다.

    저장 경로를 하나로 두려는 것이다. resolution이 나중에 한 곳만 보면 되고
    provenance도 한 형태로 유지된다. 출처는 `extraction_method`가 밝힌다.
    """
    return EntityCandidateDraft(
        local_key=local_key,
        proposed_type=entity.entity_type,
        proposed_name=entity.display_name,
        attributes={
            "external_key": entity.external_key,
            **dict(entity.attributes),
        },
    )


def _store_claims(
    observation: StoredObservation,
    batch: KnowledgeCandidateBatch,
    *,
    run_id: uuid.UUID,
    entity_ids: dict[str, uuid.UUID],
    spec: ExtractionRunSpec,
    uow: KnowledgeCandidateUnitOfWork,
) -> dict[str, uuid.UUID]:
    claim_ids: dict[str, uuid.UUID] = {}
    for draft in batch.claims:
        subject_id = _resolve(draft.subject_local_key, entity_ids, draft.local_key)
        claim_ids[draft.local_key] = uow.knowledge_candidates.add_claim_candidate(
            workspace_id=observation.workspace_id,
            run_id=run_id,
            draft=draft,
            subject_candidate_id=subject_id,
            spec=spec,
            extraction_method=_method_for(draft.subject_local_key),
        )
    return claim_ids


def _store_relations(
    observation: StoredObservation,
    batch: KnowledgeCandidateBatch,
    *,
    run_id: uuid.UUID,
    entity_ids: dict[str, uuid.UUID],
    uow: KnowledgeCandidateUnitOfWork,
) -> dict[str, uuid.UUID]:
    relation_ids: dict[str, uuid.UUID] = {}
    for draft in batch.relation_assertions:
        source_id = _resolve(draft.source_local_key, entity_ids, draft.local_key)
        target_id = _resolve(draft.target_local_key, entity_ids, draft.local_key)
        relation_ids[draft.local_key] = (
            uow.knowledge_candidates.add_relation_candidate(
                workspace_id=observation.workspace_id,
                run_id=run_id,
                draft=draft,
                source_candidate_id=source_id,
                target_candidate_id=target_id,
                extraction_method=ExtractionMethod.LLM,
            )
        )
    return relation_ids


def _method_for(subject_local_key: str) -> ExtractionMethod:
    """주장이 확정된 Entity에 대한 것인지 보고 출처를 정한다.

    Extractor가 metadata Entity를 주어로 삼아도 그 주장 자체는 LLM이 원문에서
    읽은 것이므로 `llm`이다. 여기서 `deterministic`이 되는 것은 레이어 1이
    직접 만든 Entity뿐이다.
    """
    del subject_local_key
    return ExtractionMethod.LLM


def _resolve(
    local_key: str,
    entity_ids: dict[str, uuid.UUID],
    referrer: str,
) -> uuid.UUID:
    """`local_key` 참조를 저장된 식별자로 바꾼다."""
    found = entity_ids.get(local_key)
    if found is None:
        kind = "metadata" if is_metadata_local_key(local_key) else "entity"
        raise ValueError(
            f"{referrer}가 가리킨 {kind} local_key를 찾을 수 없다: {local_key}"
        )
    return found


def _store_evidence(
    observation: StoredObservation,
    batch: KnowledgeCandidateBatch,
    *,
    run_id: uuid.UUID,
    evidence_node_id: uuid.UUID,
    entity_ids: dict[str, uuid.UUID],
    claim_ids: dict[str, uuid.UUID],
    relation_ids: dict[str, uuid.UUID],
    uow: KnowledgeCandidateUnitOfWork,
) -> int:
    """모든 후보를 그것이 나온 Observation에 잇는다.

    Claim은 근거 문구를 함께 남긴다. Extractor가 원문에서 그대로 인용하도록
    계약이 요구하므로, 나중에 서버가 본문에서 위치를 다시 찾을 수 있다.
    """
    count = 0
    for local_key, candidate_id in entity_ids.items():
        del local_key
        uow.knowledge_candidates.add_evidence_link(
            workspace_id=observation.workspace_id,
            run_id=run_id,
            evidence_node_id=evidence_node_id,
            entity_candidate_id=candidate_id,
        )
        count += 1

    statements = {draft.local_key: draft.statement for draft in batch.claims}
    for local_key, candidate_id in claim_ids.items():
        uow.knowledge_candidates.add_evidence_link(
            workspace_id=observation.workspace_id,
            run_id=run_id,
            evidence_node_id=evidence_node_id,
            claim_candidate_id=candidate_id,
            excerpt=statements.get(local_key),
        )
        count += 1

    for local_key, candidate_id in relation_ids.items():
        del local_key
        uow.knowledge_candidates.add_evidence_link(
            workspace_id=observation.workspace_id,
            run_id=run_id,
            evidence_node_id=evidence_node_id,
            relation_candidate_id=candidate_id,
        )
        count += 1

    return count


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
