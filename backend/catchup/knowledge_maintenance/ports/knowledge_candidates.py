from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from types import TracebackType
from typing import Protocol
from typing import Self

from catchup.knowledge_maintenance.contracts.extraction import ClaimCandidateDraft
from catchup.knowledge_maintenance.contracts.extraction import EntityCandidateDraft
from catchup.knowledge_maintenance.contracts.extraction import (
    RelationAssertionCandidateDraft,
)
from catchup.knowledge_maintenance.domain.claim_conflict import StoredClaimCandidate
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
from catchup.knowledge_maintenance.ports.knowledge_nodes import KnowledgeNodeRepository
from catchup.knowledge_maintenance.ports.ontology import OntologyRepository


class KnowledgeCandidateRepository(Protocol):
    """추출 결과의 영속성 기능을 정의한다.

    후보끼리의 참조는 `local_key`가 아니라 발급된 식별자로 저장한다. 호출자가
    entity를 먼저 넣어 식별자를 받은 뒤 그것으로 claim과 relation을 넣는다.
    """

    def start_run(
        self,
        *,
        workspace_id: int,
        input_node_id: uuid.UUID,
        spec: ExtractionRunSpec,
        started_at: datetime,
    ) -> ExtractionRun:
        """LLM을 부르기 전에 실행 기록을 먼저 확보한다.

        중복 실행을 막고 재시도의 기준점이 되기 때문이다.
        """
        ...

    def complete_run(
        self,
        *,
        run_id: uuid.UUID,
        status: ExtractionRunStatus,
        completed_at: datetime,
        raw_output: dict | None = None,
        error: str | None = None,
    ) -> None: ...

    def add_entity_candidate(
        self,
        *,
        workspace_id: int,
        run_id: uuid.UUID,
        draft: EntityCandidateDraft,
        extraction_method: ExtractionMethod,
        confidence: Decimal | None = None,
    ) -> uuid.UUID: ...

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
    ) -> uuid.UUID: ...

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
    ) -> uuid.UUID: ...

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
    ) -> uuid.UUID: ...

    def find_pending_entity_candidates(
        self,
        *,
        workspace_id: int,
    ) -> tuple[StoredEntityCandidate, ...]:
        """아직 해소되지 않은 entity 후보를 source_type과 함께 읽는다."""
        ...

    def find_claim_candidates(
        self,
        *,
        workspace_id: int,
    ) -> tuple[StoredClaimCandidate, ...]:
        """claim 후보를 관찰 시각과 subject 해소 결과와 함께 읽는다.

        모순 판정은 같은 대상에 대한 주장끼리 비교하는 일이고, 어느 쪽이
        더 최근인지도 알아야 한다. 후보 행만으로는 둘 다 알 수 없다.
        """
        ...

    def mark_entity_resolved(
        self,
        *,
        candidate_id: uuid.UUID,
        status: EntityResolutionStatus,
        resolved_node_id: uuid.UUID,
    ) -> None:
        """후보가 어느 canonical 노드로 해소됐는지 기록한다."""
        ...

    def get_entity_resolution(
        self,
        *,
        candidate_id: uuid.UUID,
    ) -> tuple[str, uuid.UUID | None] | None:
        """entity 후보의 현재 해소 상태와 노드를 읽는다.

        Applier가 이미 해소된 후보를 다시 해소하지 않기 위해 쓴다.
        후보가 없으면 None이다.
        """
        ...

    def accept_claims(
        self,
        *,
        claim_ids: Sequence[uuid.UUID],
    ) -> int:
        """claim 후보들을 canonical 지식으로 확정한다.

        pending인 행만 accepted로 전이한다 — 이미 확정된 claim은
        건드리지 않는다(같은 사실은 한 번만 확정된다). valid_from은
        근거 관찰의 사실 시각이 있으면 채우고 없으면 NULL로 둔다.
        시간 정보의 품질이 확정을 막으면 안 되기 때문이다. valid_to는
        여기서 절대 쓰지 않는다 — 구간을 닫는 것은 별도의 결정이다.

        이번에 새로 확정된 수를 돌려준다.
        """
        ...

    def find_succeeded_run(
        self,
        *,
        workspace_id: int,
        input_node_id: uuid.UUID,
        spec: ExtractionRunSpec,
    ) -> ExtractionRun | None:
        """같은 입력을 같은 계약으로 이미 성공시킨 실행을 찾는다.

        입력만 보고 판정하면 prompt를 고치거나 어휘를 올려도 다시 추출되지
        않는다. 그것은 중복 방지가 아니라 Observation을 영구히 얼리는 일이다.

        실패한 실행은 세지 않는다. 재시도를 막으면 안 되기 때문이다.
        """
        ...


class KnowledgeCandidateUnitOfWork(Protocol):
    """추출 결과 저장에 필요한 transaction 경계를 정의한다.

    node repository를 함께 요구한다. 후보의 근거 링크가 Observation node를
    가리키므로, 저장 전에 그 node를 찾아야 하기 때문이다.
    """

    knowledge_candidates: KnowledgeCandidateRepository
    knowledge_nodes: KnowledgeNodeRepository
    ontology: OntologyRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...
