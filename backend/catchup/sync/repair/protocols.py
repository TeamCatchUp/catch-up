from __future__ import annotations

from typing import Protocol

from catchup.server.sync.schemas import SyncRecordGapResponse
from catchup.server.sync.schemas import SyncRecordRetryRequest
from catchup.server.sync.schemas import SyncRecordRetryResponse
from catchup.sync.repair.context import RecordRepairContext


class RecordRepairHandler(Protocol):
    """Connector-specific record gap detection and partial retry handler."""

    async def get_record_gaps(
        self,
        *,
        repair_context: RecordRepairContext,
    ) -> SyncRecordGapResponse: ...

    async def retry_records(
        self,
        *,
        request: SyncRecordRetryRequest,
        repair_context: RecordRepairContext,
    ) -> SyncRecordRetryResponse: ...
