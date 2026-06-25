from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Protocol

from pydantic import BaseModel
from pydantic import Field

from catchup.sync.metadata.schemas import MetadataSyncRequest
from catchup.sync.metadata.schemas import MetadataSyncResult


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MetadataSyncExecutionRecord(BaseModel):
    """Metadata sync execution observability envelope."""

    connector: str
    tenant_id: str
    target_id: str | None = None
    status: str
    failure_reason: str | None = None
    started_at: datetime = Field(default_factory=_utc_now)
    completed_at: datetime | None = None
    last_success_at: datetime | None = None


class MetadataSyncResultStore(Protocol):
    """Persistence boundary for metadata sync execution state."""

    async def record_started(self, request: MetadataSyncRequest) -> None: ...

    async def record_succeeded(self, result: MetadataSyncResult) -> None: ...

    async def record_failed(
        self,
        request: MetadataSyncRequest,
        error: BaseException,
    ) -> None: ...


class NoopMetadataSyncResultStore:
    """Default store until a DB-backed metadata sync status model is introduced."""

    async def record_started(self, request: MetadataSyncRequest) -> None:
        _ = request

    async def record_succeeded(self, result: MetadataSyncResult) -> None:
        _ = result

    async def record_failed(
        self,
        request: MetadataSyncRequest,
        error: BaseException,
    ) -> None:
        _ = (request, error)
