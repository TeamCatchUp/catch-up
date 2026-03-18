from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from catchup.db.models import SyncConnector
from catchup.server.sync.schemas import (
    SyncRecordGapResponse,
    SyncRecordRetryRequest,
    SyncRecordRetryResponse,
)
from catchup.sync.common.exceptions import SyncRequestError
from catchup.sync.repair.github_record_repair_service import (
    get_github_record_repair_service,
)


class RecordRepairHandler(Protocol):
    async def get_record_gaps(
        self,
        *,
        scope_id: str,
        target_id: str,
        sync_days: int | None,
    ) -> SyncRecordGapResponse: ...

    async def retry_records(
        self,
        *,
        request: SyncRecordRetryRequest,
    ) -> SyncRecordRetryResponse: ...


class RecordRepairService:
    def __init__(
        self,
        *,
        github_handler: RecordRepairHandler,
    ):
        self._github_handler = github_handler

    def _resolve_handler(
        self,
        connector: SyncConnector,
    ) -> RecordRepairHandler:
        if connector == SyncConnector.GITHUB:
            return self._github_handler

        raise SyncRequestError(
            "record repair not supported for this connector",
            code="unsupported_connector",
            metadata={"connector": connector.value},
        )

    async def get_record_gaps(
        self,
        *,
        connector: SyncConnector,
        scope_id: str,
        target_id: str,
        sync_days: int | None,
    ) -> SyncRecordGapResponse:
        handler = self._resolve_handler(connector)
        return await handler.get_record_gaps(
            scope_id=scope_id,
            target_id=target_id,
            sync_days=sync_days,
        )

    async def retry_records(
        self,
        *,
        request: SyncRecordRetryRequest,
    ) -> SyncRecordRetryResponse:
        handler = self._resolve_handler(request.connector)
        return await handler.retry_records(
            request=request,
        )


@lru_cache(maxsize=1)
def get_record_repair_service() -> RecordRepairService:
    return RecordRepairService(
        github_handler=get_github_record_repair_service(),
    )
