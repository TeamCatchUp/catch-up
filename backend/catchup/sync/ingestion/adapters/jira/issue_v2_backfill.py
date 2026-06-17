from __future__ import annotations

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.sync.ingestion.adapters.jira.issue_common import (
    JiraIssueIngestionAdapterBase,
)
from catchup.sync.ingestion.adapters.jira.issue_execution import (
    JiraIssueFetchedIssuesResult,
)
from catchup.sync.ingestion.adapters.jira.issue_execution import JiraIssuePersistResult
from catchup.sync.ingestion.adapters.jira.issue_execution import JiraIssueSummaryResult
from catchup.sync.ingestion.adapters.jira.issue_execution import (
    JiraIssueSyncExecutionResult,
)
from catchup.sync.ingestion.adapters.jira.issue_execution import (
    JiraIssueTransformResult,
)
from catchup.sync.ingestion.adapters.jira.issue_execution import (
    JiraIssueV2BackfillExecutionRequest,
)
from catchup.sync.ingestion.adapters.jira.issue_execution import JiraIssueV2BackfillSeed
from catchup.sync.ingestion.schemas import SyncWindow

logger = structlog.get_logger(__name__)


class JiraIssueV2BackfillAdapter(JiraIssueIngestionAdapterBase):
    """Backfill Jira Issue v2 records by hydrating v1 seeds through Jira API."""

    async def fetch(
        self,
        *,
        execution: JiraIssueV2BackfillExecutionRequest,
        sync_window: SyncWindow,
    ) -> JiraIssueFetchedIssuesResult:
        _ = sync_window
        issues: list[dict] = []
        failed_record_ids: list[str] = []

        for seed in execution.seeds:
            try:
                issues.append(await self._dependencies.client.get_issue(seed.record_id))
            except Exception as exc:
                logger.warning(
                    "jira_issue_v2_backfill_hydrate_failed",
                    cloud_id=execution.tenant_id,
                    project_key=execution.project_key,
                    issue_key=seed.record_id,
                    document_id=seed.langchain_id,
                    error=str(exc),
                    exc_info=True,
                )
                failed_record_ids.append(seed.record_id)

        return JiraIssueFetchedIssuesResult(
            issues=tuple(issues),
            fetched_record_ids=tuple(
                issue.get("key", "") for issue in issues if issue.get("key")
            ),
            failed_record_ids=tuple(dict.fromkeys(failed_record_ids)),
            fetch_error_count=len(set(failed_record_ids)),
        )

    async def transform(
        self,
        *,
        execution: JiraIssueV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        fetched: JiraIssueFetchedIssuesResult,
    ) -> JiraIssueTransformResult:
        _ = sync_window
        seed_by_issue_key = {seed.record_id: seed for seed in execution.seeds}
        seed_langchain_id_by_issue_key = {
            seed.record_id: seed.langchain_id for seed in execution.seeds
        }

        parsed_issues, parse_failed_ids = await run_in_threadpool(
            self._parse_fetched_issues,
            tuple(fetched.issues),
        )

        if self._dependencies.v2_document_builder is None:
            v2_failed_ids = tuple(seed.langchain_id for seed in execution.seeds)
            return JiraIssueTransformResult(
                v2_failed_ids=v2_failed_ids,
                error_count=len(v2_failed_ids),
            )

        v2_documents, document_ids, build_failed_ids = (
            self._dependencies.v2_document_builder.build_from_backfill_seeds(
                tuple(parsed_issues),
                cloud_id=execution.tenant_id,
                seed_by_issue_key=seed_by_issue_key,
            )
        )
        failed_record_ids = tuple(
            dict.fromkeys(
                (
                    *fetched.failed_record_ids,
                    *parse_failed_ids,
                    *build_failed_ids,
                )
            )
        )
        v2_failed_ids = tuple(
            dict.fromkeys(
                seed_langchain_id_by_issue_key.get(record_id, record_id)
                for record_id in failed_record_ids
            )
        )
        return JiraIssueTransformResult(
            v2_documents=tuple(v2_documents),
            prepared_document_ids=tuple(document_ids),
            error_count=len(failed_record_ids),
            v2_failed_ids=v2_failed_ids,
            issue_count=len(parsed_issues),
        )

    async def summarize(
        self,
        *,
        execution: JiraIssueV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        transformed: JiraIssueTransformResult,
    ) -> JiraIssueSummaryResult:
        _ = execution, sync_window
        return JiraIssueSummaryResult(
            summary_applied=False,
            document_count=len(transformed.v2_documents),
            v2_documents=transformed.v2_documents,
            document_ids=transformed.prepared_document_ids,
        )

    async def persist(
        self,
        *,
        execution: JiraIssueV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        transformed: JiraIssueTransformResult,
        summary: JiraIssueSummaryResult,
    ) -> JiraIssuePersistResult:
        _ = sync_window
        document_ids = list(summary.document_ids)
        v2_documents = list(summary.v2_documents)
        upstream_v2_failed_ids = tuple(transformed.v2_failed_ids)
        seed_by_langchain_id = _seed_by_langchain_id(execution.seeds)

        if not document_ids:
            return JiraIssuePersistResult(
                v2_error_count=len(upstream_v2_failed_ids),
                v2_failed_ids=upstream_v2_failed_ids,
            )

        if self._dependencies.vector_store is None:
            v2_failed_ids = tuple(dict.fromkeys((*upstream_v2_failed_ids, *document_ids)))
            return JiraIssuePersistResult(
                v2_error_count=len(v2_failed_ids),
                v2_failed_ids=v2_failed_ids,
            )

        embeddings = [seed_by_langchain_id[doc_id].embedding for doc_id in document_ids]
        try:
            persisted_ids = await self._dependencies.vector_store.upsert_documents(
                v2_documents,
                ids=document_ids,
                embeddings=embeddings,
            )
        except Exception as exc:
            logger.warning(
                "jira_issue_v2_backfill_upsert_failed",
                cloud_id=execution.tenant_id,
                project_key=execution.project_key,
                document_ids=document_ids,
                error=str(exc),
                exc_info=True,
            )
            v2_failed_ids = tuple(dict.fromkeys((*upstream_v2_failed_ids, *document_ids)))
            return JiraIssuePersistResult(
                v2_error_count=len(v2_failed_ids),
                v2_failed_ids=v2_failed_ids,
            )

        persisted_id_set = {str(persisted_id) for persisted_id in persisted_ids or []}
        write_failed_ids = tuple(
            doc_id for doc_id in document_ids if doc_id not in persisted_id_set
        )
        v2_failed_ids = tuple(
            dict.fromkeys((*upstream_v2_failed_ids, *write_failed_ids))
        )
        return JiraIssuePersistResult(
            persisted_count=len(document_ids) - len(write_failed_ids),
            persisted_ids=tuple(document_ids),
            v2_error_count=len(v2_failed_ids),
            v2_failed_ids=v2_failed_ids,
        )

    def build_result(
        self,
        *,
        execution: JiraIssueV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        fetched: JiraIssueFetchedIssuesResult,
        transformed: JiraIssueTransformResult,
        summary: JiraIssueSummaryResult,
        persisted: JiraIssuePersistResult,
    ) -> JiraIssueSyncExecutionResult:
        _ = sync_window
        failed_ids = tuple(
            dict.fromkeys((*transformed.v2_failed_ids, *persisted.v2_failed_ids))
        )
        v2_failed_ids = tuple(
            dict.fromkeys((*transformed.v2_failed_ids, *persisted.v2_failed_ids))
        )
        return JiraIssueSyncExecutionResult(
            tenant_id=execution.tenant_id,
            target=execution.target,
            persisted_count=persisted.persisted_count,
            deleted_count=persisted.deleted_count,
            failed_count=len(failed_ids),
            v2_failed_count=len(v2_failed_ids),
            v2_failed_ids=v2_failed_ids,
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=persisted,
            issue_count=transformed.issue_count,
            document_count=len(summary.v2_documents),
            error_count=transformed.error_count,
            metadata={
                "project_key": execution.project_key,
                "requested_count": len(execution.seeds),
                "failed_ids": list(failed_ids),
                "failed_record_ids": list(transformed.v2_failed_ids),
                "v2_failed_ids": list(v2_failed_ids),
            },
        )

    def _parse_fetched_issues(
        self,
        issues: tuple[dict, ...],
    ):
        parsed_issues = []
        failed_issue_keys: list[str] = []
        for issue_data in issues:
            issue_key = str(issue_data.get("key") or "")
            try:
                parsed_issues.append(
                    self._dependencies.transformer.parse_issue(
                        issue_data,
                        self._dependencies.site_url,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "jira_issue_v2_backfill_parse_failed",
                    cloud_id=self._dependencies.cloud_id,
                    issue_key=issue_key,
                    error=str(exc),
                    exc_info=True,
                )
                if issue_key:
                    failed_issue_keys.append(issue_key)
        return parsed_issues, tuple(dict.fromkeys(failed_issue_keys))


def _seed_by_langchain_id(
    seeds: tuple[JiraIssueV2BackfillSeed, ...],
) -> dict[str, JiraIssueV2BackfillSeed]:
    return {seed.langchain_id: seed for seed in seeds}

JiraIssueV2BackfillIngestionAdapter = JiraIssueV2BackfillAdapter
