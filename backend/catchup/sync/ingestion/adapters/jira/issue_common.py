from __future__ import annotations

import logging

from langchain_core.documents import Document

from catchup.components.summarizer import SummarizeRequest
from catchup.sync.ingestion.adapters.jira.issue_dependencies import (
    JiraIssueIngestionDependencies,
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
from catchup.sync.ingestion.schemas import SyncWindow

logger = logging.getLogger(__name__)


def build_jira_issue_jql(*, project_key: str, sync_window: SyncWindow) -> str:
    since_str = sync_window.window_start.strftime("%Y-%m-%d %H:%M")
    return (
        f'updated >= "{since_str}" AND project = "{project_key}" '
        "ORDER BY updated DESC"
    )


class JiraIssueIngestionAdapterBase:
    def __init__(
        self,
        *,
        dependencies: JiraIssueIngestionDependencies,
        enable_summarization: bool = True,
    ) -> None:
        self._dependencies = dependencies
        self._enable_summarization = enable_summarization

    async def transform_documents(
        self,
        *,
        issues: tuple[dict, ...],
    ) -> JiraIssueTransformResult:
        documents: list[Document] = []
        doc_ids: list[str] = []
        issue_count = 0
        error_count = 0

        for issue_data in issues:
            issue_key = issue_data.get("key", "<unknown>")
            try:
                doc = self._dependencies.transformer.transform_issue(
                    issue_data,
                    self._dependencies.site_url,
                )
            except Exception:
                logger.exception(
                    "jira_issue_transform_failed",
                    extra={
                        "cloud_id": self._dependencies.cloud_id,
                        "issue_key": issue_key,
                    },
                )
                error_count += 1
                continue

            documents.append(doc)
            if doc.id:
                doc_ids.append(doc.id)
            issue_count += 1

        return JiraIssueTransformResult(
            documents=tuple(documents),
            prepared_document_ids=tuple(doc_ids),
            issue_count=issue_count,
            error_count=error_count,
        )

    async def summarize_documents(
        self,
        *,
        project_key: str,
        transformed: JiraIssueTransformResult,
        audit_context,
    ) -> JiraIssueSummaryResult:
        documents = list(transformed.documents)
        if (
            not self._enable_summarization
            or self._dependencies.summarizer is None
            or not documents
        ):
            return JiraIssueSummaryResult(
                summary_applied=False,
                document_count=len(documents),
            )

        requests = [
            SummarizeRequest(
                content=doc.metadata.get("contextual_content", doc.page_content),
                source_type=f"jira_{doc.metadata.get('entity_type', 'issue')}",
            )
            for doc in documents
        ]
        summarized = await self._dependencies.summarizer.summarize_batch(
            requests,
            audit_context=audit_context,
            context=(
                f"entity_type=issue,project_key={project_key},"
                f"doc_count={len(documents)}"
            ),
        )
        for doc, summary in zip(documents, summarized):
            doc.page_content = summary

        return JiraIssueSummaryResult(
            summary_applied=True,
            document_count=len(documents),
        )

    async def persist_documents(
        self,
        *,
        project_key: str,
        transformed: JiraIssueTransformResult,
        audit_context,
    ) -> JiraIssuePersistResult:
        documents = list(transformed.documents)
        doc_ids = [doc.id for doc in documents if doc.id]
        persisted_ids = await self._dependencies.repository.upsert_documents(
            documents,
            doc_ids,
            audit_context=audit_context,
            context=(
                f"entity_type=issue,project_key={project_key},"
                f"doc_count={len(documents)}"
            ),
        )
        return JiraIssuePersistResult(
            persisted_count=len(persisted_ids),
            persisted_ids=tuple(persisted_ids),
        )

    def build_common_result(
        self,
        *,
        tenant_id: str,
        fetched: JiraIssueFetchedIssuesResult,
        transformed: JiraIssueTransformResult,
        summary: JiraIssueSummaryResult,
        persisted: JiraIssuePersistResult,
        skipped: bool = False,
    ) -> JiraIssueSyncExecutionResult:
        _ = summary
        return JiraIssueSyncExecutionResult(
            tenant_id=tenant_id,
            fetched_count=fetched.fetched_count,
            document_count=transformed.document_count,
            persisted_count=persisted.persisted_count,
            issue_count=transformed.issue_count,
            deleted_count=persisted.deleted_count,
            error_count=transformed.error_count,
            skipped=skipped,
            batch_index=getattr(fetched, "batch_index", 0),
            is_last=getattr(fetched, "is_last", True),
            next_page_token=getattr(fetched, "next_page_token", None),
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=persisted,
        )
