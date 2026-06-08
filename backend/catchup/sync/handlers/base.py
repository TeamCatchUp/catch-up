from __future__ import annotations

from catchup.db.models import SyncType
from catchup.sync.common.protocols import IngestionHandlerProtocol
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import TargetSyncResult


class BaseFullSyncHandler(IngestionHandlerProtocol):
    """
    Full sync handler base implementation.

    - Shared cache key convention: connector:scope_id
    - Default no-op lifecycle hooks
    """

    connector: str
    sync_type = SyncType.FULL

    def _cache_key(self, scope_id: str) -> str:
        return f"{self.connector}:{scope_id}"

    def _result(
        self,
        *,
        synced_count: int = 0,
        error_count: int = 0,
        skipped: bool = False,
    ) -> TargetSyncResult:
        return TargetSyncResult(
            synced_count=synced_count,
            error_count=error_count,
            skipped=skipped,
        )

    async def on_job_started(
        self,
        *,
        context: FullSyncContext,
        total_targets: int,
    ) -> None:
        return None

    async def on_target_started(
        self,
        *,
        context: FullSyncContext,
    ) -> None:
        return None

    async def on_target_requeued(
        self,
        *,
        context: FullSyncContext,
        next_attempt: int,
        error_summary: str,
    ) -> None:
        return None

    async def on_target_failed(
        self,
        *,
        context: FullSyncContext,
        next_attempt: int,
        error_summary: str,
        retryable: bool,
    ) -> None:
        return None

    async def on_target_completed(
        self,
        *,
        context: FullSyncContext,
        result: TargetSyncResult,
    ) -> None:
        return None

    async def on_job_completed(
        self,
        *,
        context: FullSyncContext,
        total_targets: int,
        completed_targets: int,
        failed_targets: int,
        requeued_targets: int,
    ) -> None:
        return None

    async def on_job_failed(
        self,
        *,
        context: FullSyncContext,
        total_targets: int,
        failed_targets: int,
    ) -> None:
        return None
