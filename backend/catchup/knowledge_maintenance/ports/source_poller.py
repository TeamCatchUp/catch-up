"""소스 중립 폴링 계약. 커넥터가 늘면 이 Protocol의 구현만 추가된다."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import Protocol

from catchup.knowledge_maintenance.contracts.source_change import SourceChangeEnvelope


@dataclass(frozen=True, slots=True)
class SkippedItem:
    """이번 회차에 수집하지 못한 원본 한 건이다.

    폴러가 빠뜨린 건을 조용히 삼키면 안 된다. 러너의 증분 커서는 저장된
    원문의 최신 `source_updated_at`에서 도출되므로, 빠진 건보다 최신인
    원본을 먼저 저장하면 커서가 빠진 건을 지나쳐 영구 누락이 된다.
    `ordering_marker`는 그 커서 안전 판단의 기준점이다.
    """

    item_id: str
    ordering_marker: datetime | None
    reason: str


@dataclass(frozen=True, slots=True)
class SourcePollResult:
    """폴링 한 회차의 결과와 부분 수집 신호를 함께 낸다.

    `list_truncated`는 변경 목록 자체가 페이지 상한에 잘렸다는 뜻이다.
    이때는 창 하단에 무엇이 남았는지조차 모르므로 어떤 건도 안전하지 않다.
    """

    envelopes: list[SourceChangeEnvelope] = field(default_factory=list)
    skipped: list[SkippedItem] = field(default_factory=list)
    list_truncated: bool = False


class SourceChangePoller(Protocol):
    """외부 소스의 변경을 수집 계약 envelope로 옮기는 생산자다."""

    async def poll(
        self,
        *,
        workspace_id: int,
        lookback_start: datetime,
        limit: int,
        max_pages: int,
        states: Sequence[str],
    ) -> SourcePollResult:
        """lookback_start 이후 변경된 원본을 수집 계약 envelope로 변환한다.

        수집하지 못한 건과 목록 잘림 여부를 함께 낸다. 부분 수집 신호를
        버리면 러너의 DB 파생 커서가 미수집 원본을 지나쳐 영구 누락이 된다.
        """
        ...
