from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StoredBlockVerdict:
    """저장된 블록 결정 한 건을 담는다.

    Attributes:
        proposal_id: 이 결정이 붙은 변경안을 가리킨다.
        block_index: 변경안 안에서 몇 번째 블록인지 나타낸다.
        block_content_hash: 결정 당시 블록 내용의 지문을 보존한다.
            본문이 바뀌면 지문이 달라져 옛 결정이 되살아나지 않는다.
        verdict: approved 또는 rejected를 담는다.
        rejection_reason: 반려 사유를 보존한다. 승인이면 없다.
        chosen_winner_claim_id: 다툼 블록에서 사람이 고른 claim을 가리킨다.
        reviewer: 결정을 내린 사람을 나타낸다.
        reviewed_at: 결정을 내린 시각을 나타낸다.
    """

    proposal_id: uuid.UUID
    block_index: int
    block_content_hash: str
    verdict: str
    rejection_reason: str | None
    chosen_winner_claim_id: uuid.UUID | None
    reviewer: str
    reviewed_at: datetime


class BlockVerdictRepository(Protocol):
    """블록 결정 저널의 영속성 기능을 정의한다.

    workspace 범위는 저장소를 만들 때 정해진다. 변경안 식별자는 단일 컬럼
    FK라 DB가 workspace 교차 참조를 막지 못하므로, 고정된 workspace가
    읽기와 쓰기 양쪽의 울타리다.
    """

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

        블록당 한 줄만 산다. 사람이 마음을 바꿔 다시 누르면 유일 제약
        위에서 갱신으로 흡수된다.

        Raises:
            ValueError: 변경안이 저장소가 고정한 workspace에 없을 때
                던진다.
        """
        ...

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

        이미 결정이 있으면 아무것도 바꾸지 않고 False를 돌려준다. 사람의
        결정은 불변이므로 일괄 처리 경로는 이 함수만 쓴다. 목록을 읽어
        미결정을 고른 뒤 쓰기까지 사이에 사람이 단건 결정을 저장해도, 그
        결정이 그대로 남는다.

        Raises:
            ValueError: 변경안이 저장소가 고정한 workspace에 없을 때
                던진다.
        """
        ...

    def list_for_proposal(
        self, *, proposal_id: uuid.UUID
    ) -> tuple[StoredBlockVerdict, ...]:
        """변경안에 달린 결정을 block_index 순으로 읽는다."""
        ...

    def find_rejected_hashes(
        self, *, artifact_id: uuid.UUID
    ) -> dict[str, str]:
        """artifact의 과거 반려 블록을 hash에서 사유로 모은다.

        결정 행은 변경안에만 매달려 있으므로 변경안을 거쳐 문서로
        올라간다. 같은 내용이 다시 컴파일돼 올라오는 좀비 블록을 막는
        재료이며, 같은 지문에 반려가 여럿이면 마지막 결정의 사유를
        남긴다.
        """
        ...
