from __future__ import annotations

from datetime import datetime, timezone

from catchup.audit.actions import FullSyncAction
from catchup.audit.metadata import FullSyncEventAuditMetadata
from catchup.audit.utils import audit_log
from catchup.connectors.jira.factory import create_jira_ingestion_service
from catchup.sync.audit import SyncAuditContext
from catchup.sync.common.schemas import FullSyncContext, TargetSyncResult
from catchup.worker.handlers.base_full_sync_handler import BaseFullSyncHandler

class JiraFullSyncHandler(BaseFullSyncHandler):
    connector = "jira"

    async def _get_service(self, scope_id: str, cache: dict[str, object]):
        cloud_id = scope_id.strip()
        cache_key = self._cache_key(cloud_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        if not cloud_id:
            raise ValueError("jira cloud_id(scope_id) is empty")

        service = await create_jira_ingestion_service(cloud_id=cloud_id)
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
            else None
        )

        project_key = context.target_id.strip()
        if not project_key:
            raise ValueError("jira project_key(target_id) is empty")

        result = await service.full_sync(
            project_keys=[project_key],
            sync_from_dt=sync_from_dt,
            audit_context=SyncAuditContext(
                connector=context.connector,
                scope_id=context.scope_id,
                target_id=context.target_id,
                job_id=context.job_id,
                task_id=context.event_id,
            ),
        )

        if result.error_count > 0:
            raise RuntimeError(
                "[JIRA][FULL SYNC][WORKER] Target sync failed: "
                f"scope_id={context.scope_id}, project_key={project_key}, errors={result.error_count}"
            )
        return result
