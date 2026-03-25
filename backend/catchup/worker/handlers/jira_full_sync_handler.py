from __future__ import annotations

from datetime import datetime
from datetime import timezone

import structlog

from catchup.connectors.jira.factory import create_jira_ingestion_service
from catchup.sync.audit import SyncAuditContext
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import TargetSyncResult
from catchup.worker.handlers.base_full_sync_handler import BaseFullSyncHandler

logger = structlog.get_logger()


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
    
    def _get_range_start(self, context: FullSyncContext) -> datetime:
        raw = context.metadata.get("range_start")
        if raw is None:
            raise ValueError("jira full sync range_start is missing")

        value = str(raw).strip()
        if not value:
            raise ValueError("jira full sync range_start is empty")

        return datetime.fromisoformat(value).astimezone(timezone.utc)

    def _get_range_end(self, context: FullSyncContext) -> datetime:
        raw = context.metadata.get("range_end")
        if raw is None:
            raise ValueError("jira full sync range_end is missing")

        value = str(raw).strip()
        if not value:
            raise ValueError("jira full sync range_end is empty")

        return datetime.fromisoformat(value).astimezone(timezone.utc)
    
    async def collect_identifiers(
        self,
        *,
        context: FullSyncContext,
        service_cache: dict[str, object],
    ) -> list[str]:
        service = await self._get_service(context.scope_id, service_cache)

        project_key = context.target_id.strip()
        if not project_key:
            raise ValueError("jira project key is empty")

        if context.metadata.get("stage") != "issue":
            raise ValueError(
                f"jira full sync collect does not support stage={context.metadata.get('stage')}"
            )

        range_start = self._get_range_start(context)
        range_end = self._get_range_end(context)

        identifiers = await service.collect_issue_identifiers(
            project_key=project_key,
            range_start=range_start,
            range_end=range_end,
        )

        logger.info(
            "jira_full_sync_identifiers_collected",
            scope_id=context.scope_id,
            project_key=project_key,
            event_id=context.event_id,
            stage="issue",
            range_start=range_start.isoformat(),
            range_end=range_end.isoformat(),
            expected_count=len(identifiers),
        )

        return identifiers


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
                "jira_full_sync_target_failed: "
                f"scope_id={context.scope_id}, project_key={project_key}, "
                f"errors={result.error_count}"
            )

        logger.info(
            "jira_full_sync_target_synced",
            scope_id=context.scope_id,
            project_key=project_key,
            event_id=context.event_id,
            synced_count=result.synced_count,
            sync_from_ts=context.sync_from_ts,
        )
        return result
