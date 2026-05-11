from __future__ import annotations

from datetime import datetime
from datetime import timezone

from catchup.audit.actions import IncrementalSyncAction
from catchup.audit.metadata import IncrementalRecordAuditMetadata
from catchup.audit.utils import audit_log
from catchup.connector_core.adapters.jira import JiraIssueIncrementalAdapter
from catchup.connector_core.adapters.jira import (
    JiraIssueIncrementalSyncExecutionRequest,
)
from catchup.connector_core.adapters.jira import (
    create_jira_issue_ingestion_dependencies,
)
from catchup.connector_core.adapters.jira import prepare_jira_issue_transform_context
from catchup.connector_core.application.sync_ingestion import run_sync_ingestion
from catchup.connector_core.ports.sync_ingestion import SyncWindow
from catchup.sync.audit import SyncAuditContext
from catchup.sync.common.exceptions import SyncInternalException
from catchup.sync.common.schemas import IncrementalSyncContext
from catchup.sync.common.schemas import TargetSyncResult
from catchup.worker.handlers.base_incremental_handler import BaseIncrementalHandler
from catchup.worker.handlers.incremental_success_scope import IncrementalSuccessScope


class JiraIncrementalHandler(BaseIncrementalHandler):
    connector = "jira"
    incremental_success_scope = IncrementalSuccessScope.RECORD

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
