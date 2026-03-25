from __future__ import annotations

from datetime import datetime
from datetime import timezone

from catchup.audit.enums import AuditEventStatus
from catchup.audit.enums import AuditLevel
from catchup.connectors.jira.factory import create_jira_ingestion_service
from catchup.connectors.jira.issue_query import build_full_sync_audit_context
from catchup.events.enums import SyncIngestionEventAction
from catchup.sync.audit import emit_sync_ingestion_audit
from catchup.sync.audit import SyncAuditContext
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import FullSyncRepairResult
from catchup.sync.common.schemas import FullSyncValidationResult
from catchup.sync.common.schemas import TargetSyncResult
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
        return identifiers


    async def handle(
        self,
        *,
        context: FullSyncContext,
        service_cache: dict[str, object],
    ) -> TargetSyncResult:
        service = await self._get_service(context.scope_id, service_cache)

        project_key = context.target_id.strip()
        if not project_key:
            raise ValueError("jira project_key(target_id) is empty")

        if context.metadata.get("stage") != "issue":
            raise ValueError(
                f"jira full sync handle does not support stage={context.metadata.get('stage')}"
            )

        range_start = self._get_range_start(context)
        range_end = self._get_range_end(context)

        return await service.sync_issue_range(
            project_key=project_key,
            range_start=range_start,
            range_end=range_end,
            audit_context=SyncAuditContext(
                connector=context.connector,
                scope_id=context.scope_id,
                target_id=context.target_id,
                job_id=context.job_id,
                task_id=context.event_id,
            ),
        )

    async def validate_sync_result(
        self,
        *,
        context: FullSyncContext,
        expected_ids: list[str],
        service_cache: dict[str, object],
    ) -> FullSyncValidationResult:
        service = await self._get_service(context.scope_id, service_cache)
        return await service.validate_issue_range(
            project_key=context.target_id.strip(),
            range_start=self._get_range_start(context),
            range_end=self._get_range_end(context),
            expected_ids=expected_ids,
        )

    async def repair_missing_records(
        self,
        *,
        context: FullSyncContext,
        validation_result: FullSyncValidationResult,
        service_cache: dict[str, object],
    ) -> FullSyncRepairResult:
        service = await self._get_service(context.scope_id, service_cache)
        return await service.repair_issue_range_missing_records(
            project_key=context.target_id.strip(),
            missing_ids=validation_result.missing_ids,
        )

    async def on_target_completed(
        self,
        *,
        context: FullSyncContext,
        result: TargetSyncResult,
    ) -> None:
        emit_sync_ingestion_audit(
            action=SyncIngestionEventAction.FULL_SYNC,
            status=AuditEventStatus.SUCCESS,
            audit_context=SyncAuditContext(
                connector=context.connector,
                scope_id=context.scope_id,
                target_id=context.target_id,
                job_id=context.job_id,
                task_id=context.event_id,
            ),
            context=build_full_sync_audit_context(
                project_key=context.target_id,
                range_start=self._get_range_start(context),
                range_end=self._get_range_end(context),
                synced_count=result.synced_count,
                error_count=result.error_count,
                missing_count=int(context.metadata.get("missing_count") or 0),
                repair_status=str(context.metadata.get("repair_status") or "not_needed"),
            ),
        )

    async def on_target_failed(
        self,
        *,
        context: FullSyncContext,
        next_attempt: int,
        error_summary: str,
        retryable: bool,
    ) -> None:
        emit_sync_ingestion_audit(
            action=SyncIngestionEventAction.FULL_SYNC,
            status=AuditEventStatus.FAIL,
            audit_context=SyncAuditContext(
                connector=context.connector,
                scope_id=context.scope_id,
                target_id=context.target_id,
                job_id=context.job_id,
                task_id=context.event_id,
            ),
            context=build_full_sync_audit_context(
                project_key=context.target_id,
                range_start=self._get_range_start(context),
                range_end=self._get_range_end(context),
                synced_count=int(context.metadata.get("synced_count") or 0),
                error_count=int(context.metadata.get("error_count") or 0),
                missing_count=int(context.metadata.get("missing_count") or 0),
                repair_status=str(context.metadata.get("repair_status") or "failed"),
                error=error_summary,
            ),
            level=AuditLevel.ERROR,
        )
