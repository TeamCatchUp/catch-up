from __future__ import annotations

from catchup.sync.ingestion.adapters.jira.issue_common import (
    JiraIssueIngestionAdapterBase,
)
from catchup.sync.ingestion.adapters.jira.issue_common import build_jira_issue_jql
from catchup.sync.ingestion.adapters.jira.issue_execution import (
    JiraIssueFullSyncExecutionRequest,
)
from catchup.sync.ingestion.adapters.jira.issue_execution import (
    JiraIssueFullSyncFetchResult,
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


class JiraIssueFullSyncIngestionAdapter(JiraIssueIngestionAdapterBase):
    async def fetch(
        self,
        *,
        execution: JiraIssueFullSyncExecutionRequest,
        sync_window: SyncWindow,
    ) -> JiraIssueFullSyncFetchResult:
        response = await self._dependencies.client.search_issues(
            jql=build_jira_issue_jql(
                project_key=execution.project_key,
                sync_window=sync_window,
            ),
            fields=None,
            max_results=execution.max_results,
            next_page_token=execution.next_page_token,
        )
        issues = tuple(response.get("issues", ()))
        return JiraIssueFullSyncFetchResult(
            issues=issues,
            fetched_record_ids=tuple(
                issue.get("key", "") for issue in issues if issue.get("key")
            ),
            batch_index=execution.batch_index,
            is_last=bool(response.get("isLast", True)),
            next_page_token=response.get("nextPageToken"),
        )

    async def transform(
        self,
        *,
        execution: JiraIssueFullSyncExecutionRequest,
        sync_window: SyncWindow,
        fetched: JiraIssueFullSyncFetchResult,
    ) -> JiraIssueTransformResult:
        _ = execution
        _ = sync_window
        return await self.transform_documents(issues=fetched.issues)

    async def summarize(
        self,
        *,
        execution: JiraIssueFullSyncExecutionRequest,
        sync_window: SyncWindow,
        transformed: JiraIssueTransformResult,
    ) -> JiraIssueSummaryResult:
        _ = sync_window
        return await self.summarize_documents(
            project_key=execution.project_key,
            transformed=transformed,
            audit_context=execution.audit_context,
        )

    async def persist(
        self,
        *,
        execution: JiraIssueFullSyncExecutionRequest,
        sync_window: SyncWindow,
        transformed: JiraIssueTransformResult,
        summary: JiraIssueSummaryResult,
    ) -> JiraIssuePersistResult:
        _ = sync_window
        _ = summary
        return await self.persist_documents(
            project_key=execution.project_key,
            transformed=transformed,
            audit_context=execution.audit_context,
        )

    def build_result(
        self,
        *,
        execution: JiraIssueFullSyncExecutionRequest,
        sync_window: SyncWindow,
        fetched: JiraIssueFullSyncFetchResult,
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


JiraIssueFullSyncAdapter = JiraIssueFullSyncIngestionAdapter
