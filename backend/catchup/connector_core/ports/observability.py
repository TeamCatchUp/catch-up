from __future__ import annotations

from typing import Protocol


class ObservabilityPort(Protocol):
    """connector runtime 상태 조회를 별도 capability port로 준비한다."""

    async def get_observability_snapshot(self) -> object: ...
