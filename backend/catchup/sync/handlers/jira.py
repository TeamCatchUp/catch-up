from __future__ import annotations

import asyncio
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from catchup.audit.actions import FullSyncAction
from catchup.audit.actions import IncrementalSyncAction
from catchup.audit.metadata import FullSyncEventAuditMetadata
from catchup.audit.metadata import IncrementalRecordAuditMetadata
from catchup.audit.utils import audit_log
from catchup.configs.config import settings
from catchup.sync.ingestion.adapters.jira import JiraIssueFullSyncAdapter
from catchup.sync.ingestion.adapters.jira import JiraIssueFullSyncExecutionRequest
from catchup.sync.ingestion.adapters.jira import JiraIssueIncrementalAdapter
from catchup.sync.ingestion.adapters.jira import (
    JiraIssueIncrementalSyncExecutionRequest,
)
from catchup.sync.ingestion.adapters.jira import (
    create_jira_issue_ingestion_dependencies,
)
from catchup.sync.ingestion.adapters.jira import prepare_jira_issue_transform_context
from catchup.sync.audit import SyncAuditContext
from catchup.sync.common.exceptions import SyncInternalException
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import IncrementalSyncContext
from catchup.sync.common.schemas import TargetSyncResult
from catchup.sync.handlers.base import BaseFullSyncHandler
from catchup.sync.handlers.base import BaseIncrementalHandler
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.sync.ingestion.schemas import SyncWindow


class JiraFullSyncHandler(BaseFullSyncHandler):
    connector = "jira"

    async def _get_dependencies(self, scope_id: str, cache: dict[str, object]):
        cloud_id = scope_id.strip()
        cache_key = self._cache_key(cloud_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        if not cloud_id:
            raise ValueError("jira cloud_id(scope_id) is empty")

        dependencies = await create_jira_issue_ingestion_dependencies(cloud_id=cloud_id)
        cache[cache_key] = dependencies
        return dependencies

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
        dependencies = await self._get_dependencies(context.scope_id, service_cache)
        sync_from_dt = (
            datetime.fromtimestamp(float(context.sync_from_ts), tz=timezone.utc)
            if context.sync_from_ts is not None
            else datetime.now(timezone.utc) - timedelta(days=settings.DEFAULT_SYNC_DAYS)
        )

        project_key = context.target_id.strip()
        if not project_key:
            raise ValueError("jira project_key(target_id) is empty")

        window_end = datetime.now(timezone.utc)
        sync_window = SyncWindow(
            window_start=sync_from_dt,
            window_end=window_end,
        )
        audit_context = SyncAuditContext(
            connector=context.connector,
            scope_id=context.scope_id,
            target_id=context.target_id,
            job_id=context.job_id,
            task_id=context.event_id,
        )
        adapter = JiraIssueFullSyncAdapter(
            dependencies=dependencies,
        )
        await prepare_jira_issue_transform_context(
            dependencies=dependencies,
            project_key=project_key,
        )

        synced_count = 0
        error_count = 0
        next_page_token: str | None = None
        batch_index = 0
        max_results = int(settings.JIRA_SYNC_BATCH_SIZE)

        while True:
            batch_result = await run_sync_ingestion(
                port=adapter,
                execution=JiraIssueFullSyncExecutionRequest(
                    tenant_id=context.scope_id,
                    project_key=project_key,
                    batch_index=batch_index,
                    next_page_token=next_page_token,
                    max_results=max_results,
                    audit_context=audit_context,
                ),
                sync_window=sync_window,
            )
            synced_count += batch_result.persisted_count
            error_count += batch_result.error_count

            if batch_result.is_last or not batch_result.next_page_token:
                break

            next_page_token = batch_result.next_page_token
            batch_index += 1
            await asyncio.sleep(settings.JIRA_API_RATE_LIMIT_DELAY)

        result = TargetSyncResult(
            synced_count=synced_count,
            error_count=error_count,
        )

        if error_count > 0:
            raise RuntimeError(
                "jira full sync target completed with errors: "
                f"scope_id={context.scope_id}, project_key={project_key}, errors={result.error_count}"
            )
        return result


class JiraIncrementalHandler(BaseIncrementalHandler):
    connector = "jira"

    async def _get_dependencies(self, scope_id: str, cache: dict[str, object]):
        cloud_id = scope_id.strip()
        if not cloud_id:
            raise ValueError("jira cloud_id(scope_id) is empty")

        cache_key = self._cache_key(cloud_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        dependencies = await create_jira_issue_ingestion_dependencies(cloud_id=cloud_id)
        cache[cache_key] = dependencies
        return dependencies

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
        dependencies = await self._get_dependencies(context.scope_id, service_cache)
        project_key = context.parent_id or context.target_id
        if not project_key:
            raise ValueError("jira project key is empty")

        issue_key = (context.record_id or "").strip()
        if not issue_key:
            raise ValueError("jira issue_key(record_id) is empty")

        window_start = self._resolve_since(context)
        sync_window = SyncWindow(
            window_start=window_start,
            window_end=datetime.now(timezone.utc),
        )
        adapter = JiraIssueIncrementalAdapter(
            dependencies=dependencies,
        )
        event_kind = context.event_kind.value if context.event_kind else "updated"
        await prepare_jira_issue_transform_context(
            dependencies=dependencies,
            project_key=project_key,
        )
        result = await run_sync_ingestion(
            port=adapter,
            execution=JiraIssueIncrementalSyncExecutionRequest(
                tenant_id=context.scope_id,
                project_key=project_key,
                issue_key=issue_key,
                event_kind=event_kind,
                audit_context=SyncAuditContext(
                    connector=context.connector,
                    scope_id=context.scope_id,
                    target_id=context.target_id,
                    job_id=context.job_id,
                    task_id=context.event_id,
                ),
            ),
            sync_window=sync_window,
        )

        error_count = int(result.error_count)
        if error_count > 0:
            raise SyncInternalException(
                "jira incremental sync failed",
                metadata={"record_key": context.record_key},
            )
        return TargetSyncResult(
            synced_count=int(result.persisted_count + result.deleted_count),
            error_count=error_count,
            skipped=bool(result.skipped),
        )
