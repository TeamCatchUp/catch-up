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
from catchup.connector_core.adapters.confluence import (
    ConfluenceSpaceFullSyncExecutionRequest,
)
from catchup.connector_core.adapters.confluence import (
    ConfluenceSpaceIncrementalSyncExecutionRequest,
)
from catchup.connector_core.adapters.confluence import ConfluenceSpaceSyncAdapter
from catchup.connectors.confluence.factory import create_confluence_ingestion_service
from catchup.sync.audit import SyncAuditContext
from catchup.sync.common.exceptions import SyncInternalException
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import IncrementalSyncContext
from catchup.sync.common.schemas import TargetSyncResult
from catchup.sync.handlers.base import BaseFullSyncHandler
from catchup.sync.handlers.base import BaseIncrementalHandler
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.sync.ingestion.schemas import SyncWindow

logger = structlog.get_logger(__name__)


class ConfluenceFullSyncHandler(BaseFullSyncHandler):
    connector = "confluence"

    async def _get_service(self, scope_id: str, cache: dict[str, object]):
        cloud_id = scope_id.strip()
        cache_key = self._cache_key(cloud_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        if not cloud_id:
            raise ValueError("confluence cloud_id(scope_id) is empty")

        service = await create_confluence_ingestion_service(cloud_id=cloud_id)
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

        space_key = context.target_id.strip()
        if not space_key:
            raise ValueError("confluence space_key(target_id) is empty")

        record_type = str(
            context.metadata.get("record_type")
            or context.metadata.get("content_type")
            or ""
        ).strip()
        if record_type not in {"page", "blogpost"}:
            logger.error(
                "confluence_full_sync_missing_content_metadata",
                connector="confluence",
                sync_type="full",
                scope_id=context.scope_id,
                space_key=space_key,
                job_id=context.job_id,
                event_id=context.event_id,
                record_type=record_type,
            )
            raise RuntimeError("confluence_full_sync_missing_content_metadata")

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
        adapter = ConfluenceSpaceSyncAdapter(service=service)
        synced_count = 0
        error_count = 0
        batch_index = 0
        while True:
            result = await run_sync_ingestion(
                port=adapter,
                execution=ConfluenceSpaceFullSyncExecutionRequest(
                    tenant_id=context.scope_id,
                    space_key=space_key,
                    space_name=str(context.metadata.get("space_name") or context.target_name).split(" / ", 1)[0],
                    record_type=record_type,
                    batch_index=batch_index,
                    sync_from_dt=sync_from_dt,
                    audit_context=audit_context,
                ),
                sync_window=sync_window,
            )
            synced_count += result.persisted_count + result.deleted_count
            error_count += result.failed_count
            if result.is_last or result.transformed.stop_after_batch:
                break
            batch_index += 1

        if error_count > 0:
            logger.error(
                "confluence_full_sync_failed",
                connector="confluence",
                sync_type="full",
                scope_id=context.scope_id,
                space_key=space_key,
                job_id=context.job_id,
                event_id=context.event_id,
                error_count=error_count,
            )
            raise RuntimeError("confluence_full_sync_failed")
        return TargetSyncResult(
            synced_count=synced_count,
            error_count=error_count,
        )


class ConfluenceIncrementalHandler(BaseIncrementalHandler):
    connector = "confluence"

    async def _get_service(self, scope_id: str, cache: dict[str, object]):
        cloud_id = scope_id.strip()
        if not cloud_id:
            raise ValueError("confluence cloud_id(scope_id) is empty")

        cache_key = self._cache_key(cloud_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        service = await create_confluence_ingestion_service(cloud_id=cloud_id)
        cache[cache_key] = service
        return service

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
        service = await self._get_service(context.scope_id, service_cache)
        space_key = context.parent_id or context.target_id
        if not space_key:
            raise ValueError("confluence space key is empty")

        since = self._resolve_since(context)
        result = await run_sync_ingestion(
            port=ConfluenceSpaceSyncAdapter(service=service),
            execution=ConfluenceSpaceIncrementalSyncExecutionRequest(
                tenant_id=context.scope_id,
                space_key=space_key,
                record_type=context.record_type or "",
                record_id=context.record_id or "",
                event_kind=context.event_kind or "updated",
                since=since,
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
                "confluence incremental sync failed",
                metadata={"record_key": context.record_key},
            )
        return TargetSyncResult(
            synced_count=result.persisted_count + result.deleted_count,
            error_count=result.failed_count,
            skipped=result.skipped,
        )
