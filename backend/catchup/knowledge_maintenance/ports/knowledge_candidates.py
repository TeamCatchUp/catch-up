from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class AsOfClaim:
    """as-of 조회 결과의 claim 하나를 담는다."""

    claim_id: uuid.UUID
    predicate: str
    value_type: str
    value: object
    statement: str
    valid_from: datetime | None
    valid_to: datetime | None


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

        관찰 시각은 claim 발화 시각이 최우선이다 — 추출이 발화 prefix로
        본 시각과 소비자가 보는 시각이 발화 단위로 일치해야 한다. 발화
        시각이 없으면 문서 사슬로 물러난다.

        rejected와 superseded는 뺀다. 참이었던 적 없는 후보와 재추출이
        대체한 구 배치는 모순 판정의 재료가 아니다.
        """
        ...

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
        OR valid_to > at)`. 그 함수가 유일한 정의처이고 이 SQL은 같은
        규칙을 DB로 옮긴 것이므로, 한쪽만 고치면 안 된다.

        accepted만 싣는다. pending은 아직 지식이 아니고 rejected는
        참이었던 적이 없다. subject는 노드를 직접 가리키는 claim과, 그
        노드로 해소된 entity 후보를 가리키는 claim 둘 다 본다.
        predicate를 주면 그 술어만 거른다.
        """
        ...

    def find_accepted_claims_history(
        self,
        *,
        workspace_id: int,
        subject_node_id: uuid.UUID,
        predicate: str | None = None,
    ) -> tuple[AsOfClaim, ...]:
        """어떤 노드에 대해 accepted였던 claim을 시점 제한 없이 읽는다.

        `find_accepted_claims_as_of`와 유일하게 다른 점은 구간 조건이
        없다는 것이다. 그래서 live accepted와 닫힌 accepted가 함께
        나오고, "언제 바뀌었나"를 valid_from·valid_to로 되짚을 수 있다.

        rejected는 여기서도 뺀다. 닫힌 accepted는 "한때 참이었다"지만
        rejected는 "참이었던 적이 없다"라, 둘을 같이 실으면 역사가
        아니라 소문이 된다.

        정렬은 valid_from 오름차순이되 NULL이 앞이고, 같으면 관측
        시각과 id 순이다. "언제부터인지 모르는 주장"을 시간선의 맨 앞에
        두어야 그 뒤 구간이 이어지는 순서로 읽히기 때문이다.
        """
        ...

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
        사건 claim을 시간선 하나로 모으는 것이 목적이다. 매칭 대상은
        predicate·value·statement이고, 하나라도 키워드를 포함하면
        싣는다.

        `valid_from > at`은 제외한다 — 질문 시점 이후에 발효되는
        지식을 미리 보여주지 않는 기존 차단 규칙과 같다. 닫힌
        accepted(valid_to 있음)는 포함한다 — 한때 참이었던 사건도
        타임라인의 일부다. rejected는 뺀다.

        정렬은 valid_from 오름차순이되 NULL이 뒤다. as-of/history와
        달리 시점 모르는 사건을 뒤로 미는 이유는, 타임라인의 번호가
        날짜 있는 사건의 순서를 나타내야 하기 때문이다.
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

    def get_claim_validity(
        self,
        *,
        claim_id: uuid.UUID,
    ) -> tuple[str, datetime | None, datetime | None] | None:
        """claim 후보의 상태와 유효 구간을 읽는다.

        (resolution_status, valid_from, valid_to)를 돌려준다. 모순
        결정이 구간을 닫을 시각을 정할 때와, 적용기가 이미 닫힌 claim을
        다시 닫지 않기 위해 쓴다. 후보가 없으면 None이다.
        """
        ...

    def close_claim(
        self,
        *,
        claim_id: uuid.UUID,
        valid_to: datetime,
    ) -> None:
        """한때 참이었던 claim의 구간을 닫는다.

        resolution_status는 accepted로 남긴다. 공식 지식이었다는 사실은
        "그 시점에 무엇이 참이었나"의 재료이므로 지우지 않는다.
        """
        ...

    def reject_claim(
        self,
        *,
        claim_id: uuid.UUID,
    ) -> None:
        """지식이 된 적 없는 후보를 탈락시킨다.

        valid_to는 쓰지 않는다. 참이었던 구간이 없으므로 닫을 것도 없다.
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

    def supersede_stale_pending_candidates(
        self,
        *,
        workspace_id: int,
        input_node_id: uuid.UUID,
        current_run_id: uuid.UUID,
    ) -> int:
        """같은 입력의 이전 실행이 남긴 pending 후보를 은퇴시킨다.

        재추출이 만든 새 배치와 구 배치가 resolution에 이중으로 잡히는
        것을 막기 위해서다. pending만 superseded로 전이하며, 사람 결정과
        해소 결과(accepted·merged·duplicate·rejected)는 건드리지 않는다.

        은퇴시킨 행 수를 돌려준다.
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
