from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone

import structlog

from catchup.audit.actions import FullSyncAction
from catchup.audit.actions import IncrementalSyncAction
from catchup.audit.metadata import FullSyncEventAuditMetadata
from catchup.audit.metadata import IncrementalRecordAuditMetadata
from catchup.audit.utils import audit_log
from catchup.configs.config import settings
from catchup.sync.audit import SyncAuditContext
from catchup.sync.common.exceptions import SyncInternalException
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import IncrementalSyncContext
from catchup.sync.common.schemas import TargetSyncResult
from catchup.sync.handlers.base import BaseFullSyncHandler
from catchup.sync.handlers.base import BaseIncrementalHandler
from catchup.sync.ingestion.adapters.slack import SlackMessageFullSyncExecutionRequest
from catchup.sync.ingestion.adapters.slack import (
    SlackMessageIncrementalSyncExecutionRequest,
)
from catchup.sync.ingestion.factories.slack import (
    create_slack_message_full_sync_adapter,
)
from catchup.sync.ingestion.factories.slack import (
    create_slack_message_incremental_sync_adapter,
)
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.sync.ingestion.schemas import SyncWindow

logger = structlog.get_logger(__name__)


class SlackFullSyncHandler(BaseFullSyncHandler):
    connector = "slack"

    async def _get_adapter(self, scope_id: str, cache: dict[str, object]):
        normalized_scope_id = scope_id.strip()
        if not normalized_scope_id:
            raise ValueError("slack team_id(scope_id) is empty")

        cache_key = self._cache_key(normalized_scope_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        adapter = await create_slack_message_full_sync_adapter(normalized_scope_id)
        cache[cache_key] = adapter
        return adapter

    @audit_log(
        FullSyncAction.EVENT,
        metadata_factory=FullSyncEventAuditMetadata.from_audit,
        emit_attempt=True,
    )
    async def handle(
        self,
        *,
        context: FullSyncContext,
        service_cache: dict[str, object],
    ) -> TargetSyncResult:
        adapter = await self._get_adapter(context.scope_id, service_cache)
        sync_from_dt = (
            datetime.fromtimestamp(float(context.sync_from_ts), tz=timezone.utc)
            if context.sync_from_ts is not None
            else datetime.now(timezone.utc) - timedelta(days=settings.DEFAULT_SYNC_DAYS)
        )
        audit_context = SyncAuditContext(
            connector=context.connector,
            scope_id=context.scope_id,
            target_id=context.target_id,
            job_id=context.job_id,
            task_id=context.event_id,
        )
        sync_window = SyncWindow(
            window_start=sync_from_dt,
            window_end=datetime.now(timezone.utc),
        )
        synced_count = 0
        error_count = 0
        v2_failed_count = 0
        v2_failed_ids: list[str] = []
        batch_index = 0
        cursor: str | None = None
        while True:
            result = await run_sync_ingestion(
                port=adapter,
                execution=SlackMessageFullSyncExecutionRequest(
                    tenant_id=context.scope_id,
                    channel_id=context.target_id,
                    channel_name=context.target_name,
                    skip_delete=True,
                    batch_index=batch_index,
                    cursor=cursor,
                    audit_context=audit_context,
                ),
                sync_window=sync_window,
            )
            synced_count += result.persisted_count + result.deleted_count
            error_count += result.failed_count
            v2_failed_count += getattr(result, "v2_failed_count", 0)
            v2_failed_ids.extend(getattr(result, "v2_failed_ids", ()))
            if result.is_last:
                break
            cursor = result.next_cursor
            batch_index += 1

        if error_count > 0:
            logger.error(
                "slack_full_sync_failed",
                connector="slack",
                sync_type="full",
                scope_id=context.scope_id,
                channel_id=context.target_id,
                job_id=context.job_id,
                event_id=context.event_id,
                error_count=error_count,
                v2_failed_count=v2_failed_count,
                v2_failed_ids=v2_failed_ids,
            )
            raise SyncInternalException(
                "slack full sync failed",
                metadata={
                    "job_id": context.job_id,
                    "scope_id": context.scope_id,
                    "target_id": context.target_id,
                    "v2_failed_count": v2_failed_count,
                    "v2_failed_ids": v2_failed_ids,
                },
            )
        return TargetSyncResult(
            synced_count=synced_count,
            error_count=error_count,
        )


class SlackIncrementalHandler(BaseIncrementalHandler):
    connector = "slack"

    async def _get_adapter(self, scope_id: str, cache: dict[str, object]):
        team_id = scope_id.strip()
        if not team_id:
            raise ValueError("slack team_id(scope_id) is empty")

        cache_key = self._cache_key(team_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        adapter = await create_slack_message_incremental_sync_adapter(team_id)
        cache[cache_key] = adapter
        return adapter

    @audit_log(
        IncrementalSyncAction.RECORD,
        metadata_factory=IncrementalRecordAuditMetadata.from_audit,
        emit_attempt=True,
    )
    async def handle(
        self,
        *,
        context: IncrementalSyncContext,
        service_cache: dict[str, object],
    ) -> TargetSyncResult:
        adapter = await self._get_adapter(context.scope_id, service_cache)
        channel_id = context.parent_id or context.target_id
        if not channel_id:
            raise ValueError("slack channel id is empty")

        since = self._resolve_since(context)
        result = await run_sync_ingestion(
            port=adapter,
            execution=SlackMessageIncrementalSyncExecutionRequest(
                tenant_id=context.scope_id,
                channel_id=channel_id,
                record_id=context.record_id or "",
                event_kind=context.event_kind or "updated",
                audit_context=SyncAuditContext(
                    connector=context.connector,
                    scope_id=context.scope_id,
                    target_id=context.target_id,
                    job_id=context.job_id,
                    task_id=context.event_id,
                ),
            ),
            sync_window=SyncWindow(
                window_start=since,
                window_end=datetime.now(timezone.utc),
            ),
        )

        if result.failed_count > 0:
            raise SyncInternalException(
                "slack incremental sync failed",
                metadata={
                    "record_key": context.record_key,
                    "v2_failed_count": result.v2_failed_count,
                    "v2_failed_ids": list(result.v2_failed_ids),
                },
            )
        return TargetSyncResult(
            synced_count=result.persisted_count + result.deleted_count,
            error_count=result.failed_count,
            skipped=result.skipped,
        )
