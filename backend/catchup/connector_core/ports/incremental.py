from __future__ import annotations

from typing import Protocol


class IncrementalIngressPort(Protocol):
    """webhook/event 기반 incremental 진입점을 공통 port로 분리한다."""

    async def handle_incremental_event(self, payload: object) -> object: ...
