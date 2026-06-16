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
from catchup.sync.ingestion.adapters.jira.issue_execution import ParsedJiraIssueDocument
from catchup.sync.ingestion.dual_write import DualWriter
from catchup.sync.ingestion.dual_write import apply_page_content_to_vector_content
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
        parsed_documents: list[ParsedJiraIssueDocument] = []
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
                doc.metadata["cloud_id"] = self._dependencies.cloud_id
                doc.metadata["scope_id"] = self._dependencies.cloud_id
                if (
                    self._dependencies.vector_store is not None
                    and self._dependencies.v2_document_builder is not None
                ):
                    issue = self._dependencies.transformer.parse_issue(
                        issue_data,
                        self._dependencies.site_url,
                    )
                    parsed_documents.append(
                        ParsedJiraIssueDocument(issue=issue, document=doc)
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

        v2_documents: list[Document] = []
        v2_source_ids: list[str] = []
        v2_failed_ids: tuple[str, ...] = ()
        if (
            parsed_documents
            and self._dependencies.vector_store is not None
            and self._dependencies.v2_document_builder is not None
        ):
            (
                v2_documents,
                v2_source_ids,
                v2_failed_ids,
            ) = self._dependencies.v2_document_builder.build_from_parsed_documents(
                tuple(parsed_documents),
                cloud_id=self._dependencies.cloud_id,
            )

        return JiraIssueTransformResult(
            documents=tuple(documents),
            v2_documents=tuple(v2_documents),
            v2_source_ids=tuple(v2_source_ids),
            prepared_document_ids=tuple(doc_ids),
            v2_failed_ids=v2_failed_ids,
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
            v2_documents = self._align_v2_documents_to_v1_content(
                v1_documents=documents,
                v2_documents=list(transformed.v2_documents),
                v2_source_ids=list(transformed.v2_source_ids),
                operation="jira_issue_summary_disabled_dual_write",
            )
            return JiraIssueSummaryResult(
                summary_applied=False,
                document_count=len(documents),
                documents=tuple(documents),
                v2_documents=tuple(v2_documents),
                document_ids=tuple(doc.id for doc in documents if doc.id),
                v2_source_ids=tuple(
                    self._v2_source_ids_for_documents(
                        v2_documents,
                        transformed.v2_documents,
                        transformed.v2_source_ids,
                    )
                ),
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

        v2_documents = self._align_v2_documents_to_v1_content(
            v1_documents=documents,
            v2_documents=list(transformed.v2_documents),
            v2_source_ids=list(transformed.v2_source_ids),
            operation="jira_issue_dual_write",
        )
        return JiraIssueSummaryResult(
            summary_applied=True,
            document_count=len(documents),
            documents=tuple(documents),
            v2_documents=tuple(v2_documents),
            document_ids=tuple(doc.id for doc in documents if doc.id),
            v2_source_ids=tuple(
                self._v2_source_ids_for_documents(
                    v2_documents,
                    transformed.v2_documents,
                    transformed.v2_source_ids,
                )
            ),
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

    async def persist_summary_documents(
        self,
        *,
        project_key: str,
        transformed: JiraIssueTransformResult,
        summary: JiraIssueSummaryResult,
        audit_context,
    ) -> JiraIssuePersistResult:
        documents = list(summary.documents or transformed.documents)
        doc_ids = list(summary.document_ids or transformed.prepared_document_ids)
        v2_documents = list(summary.v2_documents)
        v2_source_ids = list(summary.v2_source_ids)
        context = (
            f"entity_type=issue,project_key={project_key},"
            f"doc_count={len(documents)}"
        )
        if self._dependencies.vector_store is not None:
            result = await DualWriter(
                repository=self._dependencies.repository,
                vector_store=self._dependencies.vector_store,
            ).upsert_documents(
                source_documents=documents,
                vector_documents=v2_documents,
                ids=doc_ids,
                vector_source_ids=v2_source_ids,
                audit_context=audit_context,
                context=context,
            )
            v2_failed_ids = tuple(
                dict.fromkeys((*transformed.v2_failed_ids, *result.vector_failed_ids))
            )
            return JiraIssuePersistResult(
                persisted_count=len(result.persisted_ids),
                persisted_ids=tuple(result.persisted_ids),
                v2_error_count=len(v2_failed_ids),
                v2_failed_ids=v2_failed_ids,
            )

        persisted_ids = await self._dependencies.repository.upsert_documents(
            documents,
            doc_ids,
            audit_context=audit_context,
            context=context,
        )
        return JiraIssuePersistResult(
            persisted_count=len(persisted_ids),
            persisted_ids=tuple(persisted_ids),
            v2_error_count=len(transformed.v2_failed_ids),
            v2_failed_ids=transformed.v2_failed_ids,
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
            failed_count=transformed.error_count + persisted.v2_error_count,
            issue_count=transformed.issue_count,
            deleted_count=persisted.deleted_count,
            error_count=transformed.error_count,
            v2_failed_count=persisted.v2_error_count,
            v2_failed_ids=persisted.v2_failed_ids,
            skipped=skipped,
            batch_index=getattr(fetched, "batch_index", 0),
            is_last=getattr(fetched, "is_last", True),
            next_page_token=getattr(fetched, "next_page_token", None),
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=persisted,
            metadata={
                "v2_failed_ids": list(persisted.v2_failed_ids),
                "v2_document_count": len(transformed.v2_documents),
            },
        )

    @staticmethod
    def _align_v2_documents_to_v1_content(
        *,
        v1_documents: list[Document],
        v2_documents: list[Document],
        v2_source_ids: list[str],
        operation: str,
    ) -> list[Document]:
        source_id_by_vector_id = {
            vector_document.id: source_id
            for vector_document, source_id in zip(
                v2_documents,
                v2_source_ids,
                strict=True,
            )
        }
        return apply_page_content_to_vector_content(
            source_documents=v1_documents,
            vector_documents=v2_documents,
            connector="jira",
            entity_type="issue",
            operation=operation,
            source_id_by_vector_id=source_id_by_vector_id,
        )

    @staticmethod
    def _v2_source_ids_for_documents(
        aligned_documents: list[Document],
        original_documents: tuple[Document, ...],
        original_source_ids: tuple[str, ...],
    ) -> list[str]:
        source_by_vector_id = {
            document.id: source_id
            for document, source_id in zip(
                original_documents,
                original_source_ids,
                strict=True,
            )
        }
        return [source_by_vector_id[document.id] for document in aligned_documents]
