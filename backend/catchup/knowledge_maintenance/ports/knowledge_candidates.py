from __future__ import annotations

import uuid
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
from catchup.knowledge_maintenance.domain.evidence import Locator
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionMethod
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionRun
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionRunSpec
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionRunStatus
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
