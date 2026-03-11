from __future__ import annotations

from datetime import datetime, timedelta, timezone

from catchup.configs.config import settings
from catchup.sync.common.protocols import IngestionHandlerProtocol
from catchup.sync.common.schemas import SyncEventContext


class BaseIncrementalHandler(IngestionHandlerProtocol):
    connector: str
    sync_type = "incremental"

    def _cache_key(self, scope_id: str) -> str:
        return f"{self.connector}:{scope_id}"

    def _resolve_since(self, context: SyncEventContext) -> datetime:
        raw = context.batch_sync_from or context.last_event_at or context.sync_from
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
        context: SyncEventContext,
        total_targets: int,
    ) -> None:
        return None

    async def on_target_started(
        self,
        *,
        context: SyncEventContext,
    ) -> None:
        return None

    async def on_target_requeued(
        self,
        *,
        context: SyncEventContext,
        next_attempt: int,
        error_summary: str,
    ) -> None:
        return None

    async def on_target_failed(
        self,
        *,
        context: SyncEventContext,
        next_attempt: int,
        error_summary: str,
        retryable: bool,
    ) -> None:
        return None

    async def on_target_completed(
        self,
        *,
        context: SyncEventContext,
        result: dict[str, int | bool],
    ) -> None:
        return None

    async def on_job_completed(
        self,
        *,
        context: SyncEventContext,
        total_targets: int,
        completed_targets: int,
        failed_targets: int,
        requeued_targets: int,
    ) -> None:
        return None

    async def on_job_failed(
        self,
        *,
        context: SyncEventContext,
        total_targets: int,
        failed_targets: int,
    ) -> None:
        return None
