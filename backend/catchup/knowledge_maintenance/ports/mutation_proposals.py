from __future__ import annotations

import uuid
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from catchup.knowledge_maintenance.domain.knowledge_candidate import (
    StoredMutationProposal,
)
from catchup.knowledge_maintenance.domain.source_version import JsonValue


class MergeProposalAlreadyDecided(Exception):
    """이미 결정된 병합 안건을 다시 결정하려 할 때 던진다.

    결정은 감사 기록이다. 나중 결정이 먼저 확정된 결정을 조용히 덮으면
    "누가 언제 정했나"가 사라지므로, 덮어쓰기 대신 명시적으로 거부한다.
    """


@dataclass(frozen=True, slots=True)
class StoredMergeCandidate:
    """병합 안건에 묶인 entity 후보 하나를 읽는 형태로 담는다.

    Attributes:
        id: 후보 행을 식별한다.
        proposed_name: 추출기가 제안한 이름이다. 사람이 안건을 도메인
            언어("A와 B가 같은가?")로 읽는 재료다.
        proposed_type: 추출기가 제안한 entity 종류다.
        resolution_status: 후보의 현재 해소 상태다. 이미 해소된 후보가
            섞여 있으면 검토자가 알아야 한다.
    """

    id: uuid.UUID
    proposed_name: str
    proposed_type: str
    resolution_status: str


@dataclass(frozen=True, slots=True)
class StoredMergeProposal:
    """검토 대기 중인 병합 안건 하나를 읽는 형태로 담는다.

    Attributes:
        id: proposal 행을 식별한다.
        summary: 판정기가 남긴 요약이다.
        resolver_metadata: judge의 판정 근거를 보존한다.
        candidates: 묶인 후보들이다. operations의 sequence 순서를
            따르므로 첫 후보가 대표다.
    """

    id: uuid.UUID
    summary: str
    resolver_metadata: Mapping[str, object]
    candidates: tuple[StoredMergeCandidate, ...]


@dataclass(frozen=True, slots=True)
class StoredContradictionValue:
    """모순 안건에 실린 값 후보 하나를 읽는 형태로 담는다.

    Attributes:
        claim_id: 이 값을 주장한 claim 후보를 가리킨다. 사람이 고르는
            승자가 이 id다.
        value: 주장된 원본 값을 보존한다.
        normalized: 비교에 쓴 정규화 값을 보존한다.
        statement: 주장을 사람이 읽는 문장으로 보존한다.
        observed_at: 주장이 놓인 시각이다. 사건 시각을 먼저 쓰고 없으면
            원문 변경 시각, 그것도 없으면 수집 시각으로 내려가는
            domain.temporal.resolve_reference_time과 같은 사슬이다.
        citation_verified: 근거 인용의 원문 대조 결과다. 낡은 안건에는
            없어 None일 수 있다.
    """

    claim_id: uuid.UUID
    value: object
    normalized: str | None
    statement: str | None
    observed_at: str | None
    citation_verified: bool | None = None


@dataclass(frozen=True, slots=True)
class StoredContradictionProposal:
    """검토 대기 중인 모순 안건 하나를 읽는 형태로 담는다.

    Attributes:
        id: proposal 행을 식별한다.
        predicate: 어떤 속성에서 값이 갈렸는지 나타낸다.
        subject_key: 어느 대상에 대한 모순인지 나타낸다.
        summary: 판정기가 남긴 요약을 보존한다.
        values: 갈린 값 후보들이다. 사람은 이 중 하나를 승자로 고른다.
    """

    id: uuid.UUID
    predicate: str
    subject_key: str
    summary: str
    values: tuple[StoredContradictionValue, ...]


@dataclass(frozen=True, slots=True)
class StoredOperation:
    """proposal에 딸린 적용 명령 하나를 읽는 형태로 담는다.

    Attributes:
        sequence: 실행 순서를 나타낸다.
        operation_type: 어떤 종류의 변경인지 나타낸다.
        entity_candidate_id: 명령이 다루는 entity 후보를 가리킨다.
        claim_candidate_id: 명령이 다루는 claim 후보를 가리킨다.
            supersede_claim이 닫을 패자가 여기 있다.
        operation_data: 명령의 재료를 담는다. create_entity는
            proposed_type·proposed_name을, merge_entity는
            merge_into_sequence를, supersede_claim은 winner_claim_id와
            valid_to를 여기서 읽는다.
    """

    sequence: int
    operation_type: str
    entity_candidate_id: uuid.UUID | None
    claim_candidate_id: uuid.UUID | None
    operation_data: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class StoredPendingProposal:
    """어떤 대상에 걸려 있는 계류 안건 하나를 읽는 형태로 담는다.

    문서가 이 안건을 열린 질문으로 옮겨 적을 때 쓴다. 요약과 판정 근거를
    그대로 실어야 하므로 둘 다 담는다.

    Attributes:
        id: proposal 행을 식별한다.
        proposal_kind: 어떤 종류의 안건인지 나타낸다.
        summary: 판정기가 남긴 요약을 보존한다.
        resolver_metadata: 판정 근거를 보존한다.
    """

    id: uuid.UUID
    proposal_kind: str
    summary: str
    resolver_metadata: Mapping[str, object]


class MutationProposalRepository(Protocol):
    """mutation proposal의 영속성 기능을 정의한다."""

    def find_pending_by_idempotency_key(
        self,
        *,
        workspace_id: int,
        idempotency_key: str,
    ) -> StoredMutationProposal | None:
        """같은 검토 단위로 이미 열려 있는 proposal을 찾는다."""
        ...

    def find_decided_by_idempotency_key(
        self,
        *,
        workspace_id: int,
        idempotency_key: str,
    ) -> StoredMutationProposal | None:
        """같은 검토 단위에 이미 내려진 결정을 찾는다.

        approved·applied·rejected 행이 대상이다. 판정기가 이 결정의
        구성(member_hash)과 지금의 모순을 견줘 같은 사실을 다시 묻지
        않게 한다.
        """
        ...

    def abandon(self, *, proposal_id: uuid.UUID) -> None:
        """proposal을 접는다. 멤버가 달라져 낡은 계획서가 됐을 때 쓴다."""
        ...

    def find_pending_duplicate_groups(
        self,
        *,
        workspace_id: int,
    ) -> dict[uuid.UUID, uuid.UUID]:
        """아직 열려 있는 병합 계획서의 멤버를 계획서로 되짚는다.

        entity 후보 하나가 어느 병합 묶음에 속하는지 알아야 아직 노드로
        해소되지 않은 후보들도 같은 대상으로 묶어 주장을 비교할 수 있다.
        """
        ...

    def find_pending_contradiction_proposals(
        self,
        *,
        workspace_id: int,
    ) -> tuple[tuple[uuid.UUID, str, str | None], ...]:
        """열려 있는 모순 계획서를 식별자·key·predicate로 되짚는다.

        모순은 사라질 수 있다. 값이 한 종으로 수렴하거나 근거 claim이
        없어지거나 subject가 다른 키로 이주하면 옛 계획서는 더 이상
        사실이 아니다. 이번 실행이 확인한 key와 견주어 회수하려면 열려
        있는 목록을 통째로 읽어야 한다.

        predicate를 함께 준다. key만으로는 "모순이 사라졌다"와 "사전이
        더 이상 그 속성을 비교하지 않는다"를 구분할 수 없는데, 뒤쪽까지
        회수하면 어휘를 되돌리는 순간 검토 큐가 통째로 비기 때문이다.
        낡은 metadata에 predicate가 없으면 None이다.
        """
        ...

    def find_pending_for_subject_node(
        self,
        *,
        workspace_id: int,
        node_id: uuid.UUID,
    ) -> list[StoredPendingProposal]:
        """어떤 canonical 노드에 걸려 있는 계류 안건을 모은다.

        모순 안건은 판정 근거의 subject_key가 그 노드를 가리키는 것이고,
        병합 안건은 멤버 후보 가운데 그 노드로 해소된 것이 있는 것이다.
        둘 다 봐야 하는 이유는 카드가 "이 대상에 대해 아직 답이 나오지
        않은 질문"을 빠짐없이 실어야 하기 때문이다.
        """
        ...

    def find_contested_subject_node_ids(
        self,
        *,
        workspace_id: int,
    ) -> frozenset[uuid.UUID]:
        """pending 모순이 걸린 subject 노드 id 집합을 만든다.

        모순 proposal의 값 후보 claim들이 가리키는 subject를 노드로
        해소해 모은다. 검토 큐가 "이 문서에 충돌이 걸렸는가"를 표시하는
        재료다.

        판정 근거의 subject_key를 그대로 읽지 않는다. 아직 노드가 없던
        대상은 key가 병합 계획서를 가리키는데(`proposal:<id>`), 그 뒤에
        후보가 노드로 해소되면 key는 낡은 채 남는다. claim에서 노드로
        되짚으면 두 경우가 하나의 규칙으로 모인다.
        """
        ...

    def list_pending_duplicates(
        self,
        *,
        workspace_id: int,
    ) -> list[StoredMergeProposal]:
        """검토 대기 중인 병합 안건을 후보 상세와 함께 모은다.

        사람이 안건을 도메인 언어로 읽으려면 후보의 이름과 종류가
        필요하다. 후보 순서는 operations의 sequence를 따른다 — 첫
        후보가 대표다.
        """
        ...

    def mark_merge_approved(
        self,
        *,
        workspace_id: int,
        proposal_id: uuid.UUID,
        reviewer: str,
    ) -> None:
        """병합 안건을 승인으로 끝맺는다.

        pending인 duplicate 행 하나만 갱신한다. 대상이 없으면 —
        이미 결정됐거나, 없는 안건이거나, 병합 안건이 아니면 —
        `MergeProposalAlreadyDecided`를 던진다.

        Raises:
            MergeProposalAlreadyDecided: 계류 중인 병합 안건이 아니다.
        """
        ...

    def mark_merge_rejected(
        self,
        *,
        workspace_id: int,
        proposal_id: uuid.UUID,
        reviewer: str,
        reason: str,
    ) -> None:
        """병합 안건을 사유와 함께 반려로 끝맺는다.

        사유는 DB CHECK가 요구한다. 이유 없는 반려는 같은 안건을
        다시 판단하게 만들기 때문이다.

        Raises:
            MergeProposalAlreadyDecided: 계류 중인 병합 안건이 아니다.
        """
        ...

    def list_pending_contradictions(
        self,
        *,
        workspace_id: int,
    ) -> list[StoredContradictionProposal]:
        """검토 대기 중인 모순 안건을 값 후보와 함께 모은다.

        사람이 "어느 값이 맞나"를 고르려면 값과 그 근거 문장, 관찰
        시각이 함께 보여야 한다. 승자로 지정할 claim id도 여기서 나온다.
        """
        ...

    def get_contradiction_status(
        self,
        *,
        workspace_id: int,
        proposal_id: uuid.UUID,
    ) -> str | None:
        """모순 안건 하나의 현재 상태를 읽는다. 없으면 None이다.

        계류 목록만으로는 "없는 안건"과 "이미 결정된 안건"이 한 사실로
        보인다. 소비자가 할 일은 그 둘에서 다르므로(식별자를 고칠지, 큐를
        다시 읽을지) 상태를 한 건씩 읽을 자리를 둔다.
        """
        ...

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

        결정 내용(승자·패자·닫을 시각)은 resolver_metadata의 decision
        키에 병합한다. 안건 종류마다 결정의 형태가 달라 컬럼으로 두면
        대부분이 비는 표가 되기 때문이다. 기존 키는 보존한다.

        같은 transaction에서 패자마다 supersede_claim operation을
        sequence 1..N으로 만든다. 결정이 명령을 만드는 유일한 자리이며,
        그 뒤로 Applier는 저널만 소비한다.

        Raises:
            MergeProposalAlreadyDecided: 계류 중인 모순 안건이 아니다.
        """
        ...

    def find_approved_proposals_with_operations(
        self,
        *,
        workspace_id: int,
    ) -> list[tuple[uuid.UUID, tuple[StoredOperation, ...]]]:
        """승인됐지만 아직 적용되지 않은 안건을 명령과 함께 모은다.

        Applier의 입력이다. operations는 sequence 순서로 담는다.
        """
        ...

    def mark_applied(
        self,
        *,
        workspace_id: int,
        proposal_id: uuid.UUID,
    ) -> None:
        """안건을 적용 완료로 끝맺고 applied_at을 기록한다.

        approved 행 하나만 갱신한다. 결정 없이 적용되는 경로를 DB
        수준에서 막기 위해서다.

        Raises:
            MergeProposalAlreadyDecided: approved 상태가 아니다.
        """
        ...

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

        operation은 두 종류다. 대표 후보의 create_entity가 1번이고,
        나머지 후보의 merge_entity가 그 뒤를 따르며 1번이 만들 노드를
        가리킨다.

        같은 key의 행이 이미 결정돼 있으면(approved·applied·rejected)
        되살리지 않고 그 id를 그대로 돌려준다 — 사람은 같은 사실에
        대해 한 번만 결정한다. 계류·접힘 행만 내용을 갈아끼워 되살리고,
        되살릴 때 이전 결정 흔적(reviewer·reviewed_at·rejection_reason·
        applied_at)을 지운다.
        """
        ...

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

        operation을 만들지 않는다. 어느 값이 맞는지는 자동으로 정할 수
        없고, 사람이 판단할 때까지 적용 명령을 만들면 안 되기 때문이다.
        """
        ...
