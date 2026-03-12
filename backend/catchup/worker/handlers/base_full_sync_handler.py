from __future__ import annotations

import math
from datetime import datetime, timezone

from catchup.configs.config import settings
from catchup.db.models import SyncType
from catchup.sync.common.protocols import IngestionHandlerProtocol
from catchup.sync.common.schemas import FullSyncContext, TargetSyncResult


class BaseFullSyncHandler(IngestionHandlerProtocol):
    """
    Full Sync 핸들러 공통 기본 구현.

    - cache key 규칙 통일 (connector:scope_id)
    - sync_from(metadata) -> sync_days 환산
    - lifecycle hook 기본 no-op
    """

    connector: str
    sync_type = SyncType.FULL

    def _as_int(self, value: object, default: int = 0) -> int:
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default

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

    def _resolve_sync_days(self, context: FullSyncContext) -> int:
        default_days = max(1, int(settings.DEFAULT_SYNC_DAYS))
        raw_sync_from = context.sync_from
        if raw_sync_from is None:
            return default_days

        try:
            sync_from_ts = float(raw_sync_from)
        except (TypeError, ValueError):
            return default_days

        now_ts = datetime.now(timezone.utc).timestamp()
        if sync_from_ts >= now_ts:
            return 1

        elapsed_days = math.ceil((now_ts - sync_from_ts) / 86400)
        return max(1, elapsed_days)

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
