"""소스 중립 폴링 계약. 커넥터가 늘면 이 Protocol의 구현만 추가된다."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from catchup.knowledge_maintenance.contracts.source_change import SourceChangeEnvelope


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
    ) -> list[SourceChangeEnvelope]:
        """lookback_start 이후 변경된 원본을 수집 계약 envelope로 변환한다."""
        ...
