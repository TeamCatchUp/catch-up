from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from catchup.configs.config import settings
from catchup.db.models import SyncType
from catchup.sync.common.protocols import IngestionHandlerProtocol
from catchup.sync.common.schemas import IncrementalSyncContext
from catchup.sync.common.schemas import TargetSyncResult


class BaseIncrementalHandler(IngestionHandlerProtocol):
    connector: str
    sync_type = SyncType.INCREMENTAL

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

    def _resolve_since(self, context: IncrementalSyncContext) -> datetime:
        raw = context.last_event_at
        if raw:
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(
                    timezone.utc
                )
            except ValueError:
                pass

        return datetime.now(timezone.utc) - timedelta(
            hours=max(1, int(settings.SYNC_INCREMENTAL_FALLBACK_HOURS))
        )

    async def on_job_started(
        self,
        *,
        context: IncrementalSyncContext,
        total_targets: int,
    ) -> None:
        return None

    async def on_target_started(
        self,
        *,
        context: IncrementalSyncContext,
    ) -> None:
        return None

    async def on_target_requeued(
        self,
        *,
        context: IncrementalSyncContext,
        next_attempt: int,
        error_summary: str,
    ) -> None:
        return None

    async def on_target_failed(
        self,
        *,
        context: IncrementalSyncContext,
        next_attempt: int,
        error_summary: str,
        retryable: bool,
    ) -> None:
        return None

    async def on_target_completed(
        self,
        *,
        context: IncrementalSyncContext,
        result: TargetSyncResult,
    ) -> None:
        return None

    async def on_job_completed(
        self,
        *,
        context: IncrementalSyncContext,
        total_targets: int,
        completed_targets: int,
        failed_targets: int,
        requeued_targets: int,
    ) -> None:
        return None

    async def on_job_failed(
        self,
        *,
        context: IncrementalSyncContext,
        total_targets: int,
        failed_targets: int,
    ) -> None:
        return None
