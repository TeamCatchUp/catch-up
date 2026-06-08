from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from catchup.audit.actions import FullSyncAction
from catchup.audit.metadata import FullSyncEventAuditMetadata
from catchup.audit.utils import audit_log
from catchup.configs.config import settings
from catchup.connector_core.adapters.slack import SlackMessageFullSyncExecutionRequest
from catchup.connector_core.adapters.slack import SlackMessageSyncAdapter
from catchup.connectors.slack.factory import create_slack_ingestion_service
from catchup.sync.audit import SyncAuditContext
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import TargetSyncResult
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.sync.ingestion.schemas import SyncWindow
from catchup.worker.handlers.base_full_sync_handler import BaseFullSyncHandler


class SlackFullSyncHandler(BaseFullSyncHandler):
    connector = "slack"

    async def _get_service(self, scope_id: str, cache: dict[str, object]):
        normalized_scope_id = scope_id.strip()
        if not normalized_scope_id:
            raise ValueError("slack team_id(scope_id) is empty")

        cache_key = self._cache_key(normalized_scope_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        service = await create_slack_ingestion_service(normalized_scope_id)
        cache[cache_key] = service
        return service

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
        service = await self._get_service(context.scope_id, service_cache)
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
        adapter = SlackMessageSyncAdapter(service=service)

        synced_count = 0
        error_count = 0
        batch_index = 0
        cursor: str | None = None
        while True:
            result = await run_sync_ingestion(
                port=adapter,
                execution=SlackMessageFullSyncExecutionRequest(
                    tenant_id=context.scope_id,
                    channel_id=context.target_id,
                    channel_name=context.target_name,
                    sync_from_ts=context.sync_from_ts,
                    skip_delete=True,
                    batch_index=batch_index,
                    cursor=cursor,
                    audit_context=audit_context,
                ),
                sync_window=sync_window,
            )
            synced_count += result.persisted_count + result.deleted_count
            error_count += result.failed_count
            if result.is_last:
                break
            cursor = result.next_cursor
            batch_index += 1

        if error_count > 0:
            raise RuntimeError(
                "[SLACK][FULL SYNC][WORKER] Target sync failed: "
                f"scope_id={context.scope_id}, channel_id={context.target_id}, errors={error_count}"
            )
        return TargetSyncResult(
            synced_count=synced_count,
            error_count=error_count,
        )
