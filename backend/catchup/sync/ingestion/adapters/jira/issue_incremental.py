from __future__ import annotations

import structlog

from catchup.sync.ingestion.adapters.jira.issue_common import (
    JiraIssueIngestionAdapterBase,
)
from catchup.sync.ingestion.adapters.jira.issue_execution import (
    JiraIssueIncrementalFetchResult,
)
from catchup.sync.ingestion.adapters.jira.issue_execution import (
    JiraIssueIncrementalSyncExecutionRequest,
)
from catchup.sync.ingestion.adapters.jira.issue_execution import JiraIssuePersistResult
from catchup.sync.ingestion.adapters.jira.issue_execution import JiraIssueSummaryResult
from catchup.sync.ingestion.adapters.jira.issue_execution import (
    JiraIssueSyncExecutionResult,
)
from catchup.sync.ingestion.adapters.jira.issue_execution import (
    JiraIssueTransformResult,
)
from catchup.sync.ingestion.schemas import SyncWindow

logger = structlog.get_logger(__name__)


class JiraIssueIncrementalIngestionAdapter(JiraIssueIngestionAdapterBase):
    async def fetch(
        self,
        *,
        execution: JiraIssueIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
    ) -> JiraIssueIncrementalFetchResult:
        _ = sync_window
        if execution.is_delete_event:
            return JiraIssueIncrementalFetchResult(
                issues=(),
                fetched_record_ids=(execution.issue_key,),
            )

        issue = await self._dependencies.client.get_issue(execution.issue_key)
        return JiraIssueIncrementalFetchResult(
            issues=(issue,),
            fetched_record_ids=(execution.issue_key,),
        )

    async def transform(
        self,
        *,
        execution: JiraIssueIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        fetched: JiraIssueIncrementalFetchResult,
    ) -> JiraIssueTransformResult:
        _ = sync_window
        if execution.is_delete_event:
            return JiraIssueTransformResult()
        return await self.transform_documents(issues=fetched.issues)

    async def summarize(
        self,
        *,
        execution: JiraIssueIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        transformed: JiraIssueTransformResult,
    ) -> JiraIssueSummaryResult:
        _ = sync_window
        if execution.is_delete_event:
            return JiraIssueSummaryResult(summary_applied=False, document_count=0)
        return await self.summarize_documents(
            project_key=execution.project_key,
            transformed=transformed,
            audit_context=execution.audit_context,
        )

    async def persist(
        self,
        *,
        execution: JiraIssueIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        transformed: JiraIssueTransformResult,
        summary: JiraIssueSummaryResult,
    ) -> JiraIssuePersistResult:
        _ = sync_window
        _ = summary
        if execution.is_delete_event:
            v1_doc_ids = [
                f"jira:issue:{execution.issue_key}",
                f"jira:epic:{execution.issue_key}",
            ]
            await self._dependencies.repository.delete_documents(v1_doc_ids)
            v2_failed_ids: tuple[str, ...] = ()
            if self._dependencies.vector_store is not None:
                v2_doc_ids = [
                    (
                        "jira:issue:"
                        f"{execution.tenant_id}:{execution.project_key}:"
                        f"{execution.issue_key}"
                    ),
                    (
                        "jira:epic:"
                        f"{execution.tenant_id}:{execution.project_key}:"
                        f"{execution.issue_key}"
                    ),
                ]
                try:
                    await self._dependencies.vector_store.delete(v2_doc_ids)
                except Exception as exc:
                    logger.warning(
                        "jira_issue_v2_delete_failed",
                        cloud_id=execution.tenant_id,
                        project_key=execution.project_key,
                        issue_key=execution.issue_key,
                        document_ids=v2_doc_ids,
                        error=str(exc),
                        exc_info=True,
                    )
                    v2_failed_ids = tuple(v2_doc_ids)
            return JiraIssuePersistResult(
                deleted_count=1,
                v2_error_count=len(v2_failed_ids),
                v2_failed_ids=v2_failed_ids,
            )

        return await self.persist_summary_documents(
            project_key=execution.project_key,
            transformed=transformed,
            summary=summary,
            audit_context=execution.audit_context,
        )

    def build_result(
        self,
        *,
        execution: JiraIssueIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        fetched: JiraIssueIncrementalFetchResult,
        transformed: JiraIssueTransformResult,
        summary: JiraIssueSummaryResult,
        persisted: JiraIssuePersistResult,
    ) -> JiraIssueSyncExecutionResult:
        _ = sync_window
        return self.build_common_result(
            tenant_id=execution.tenant_id,
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=persisted,
        )


JiraIssueIncrementalAdapter = JiraIssueIncrementalIngestionAdapter
