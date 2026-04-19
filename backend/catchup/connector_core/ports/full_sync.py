from __future__ import annotations

from typing import Protocol


class FullSyncPort(Protocol):
    """추후 connector별 전체 동기화 구현이 맞춰야 할 최소 계약."""

    async def run_full_sync(self) -> object: ...
