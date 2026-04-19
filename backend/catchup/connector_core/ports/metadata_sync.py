from __future__ import annotations

from typing import Protocol


class MetadataSyncPort(Protocol):
    """ metadata 선행 동기화 기능을 connector별로 동일한 형태로 노출한다."""

    async def sync_metadata(self) -> object: ...
