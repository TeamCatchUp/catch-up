from __future__ import annotations

from catchup.audit.actions import IncrementalSyncAction
from catchup.audit.metadata import IncrementalRecordAuditMetadata
from catchup.audit.utils import audit_log
from catchup.connectors.confluence.factory import create_confluence_ingestion_service
from catchup.sync.audit import SyncAuditContext
from catchup.sync.common.exceptions import SyncInternalException
from catchup.sync.common.schemas import IncrementalSyncContext
from catchup.sync.common.schemas import TargetSyncResult
from catchup.worker.handlers.base_incremental_handler import BaseIncrementalHandler
from catchup.worker.handlers.incremental_success_scope import IncrementalSuccessScope


class ConfluenceIncrementalHandler(BaseIncrementalHandler):
    connector = "confluence"
    incremental_success_scope = IncrementalSuccessScope.RECORD

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

        result = await service.incremental_sync(
            space_key=space_key,
            record_type=context.record_type or "",
            record_id=context.record_id or "",
            event_kind=context.event_kind or "updated",
            since=self._resolve_since(context),
            audit_context=SyncAuditContext(
                connector=context.connector,
                scope_id=context.scope_id,
                target_id=context.target_id,
                job_id=context.job_id,
                task_id=context.event_id,
            ),
        )

        error_count = int(result.get("errors", 0))
        if error_count > 0:
            raise SyncInternalException(
                "confluence incremental sync failed",
                metadata={"record_key": context.record_key},
            )
        return TargetSyncResult(
            synced_count=int(result.get("synced", 0)),
            error_count=error_count,
            skipped=bool(result.get("skipped", False)),
        )
