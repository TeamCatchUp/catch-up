from __future__ import annotations

import structlog
from langchain_core.documents import Document

from catchup.sync.ingestion.adapters.jira.issue_execution import ParsedJiraIssueDocument
from catchup.sync.ingestion.vector_records.jira_issue_mapper import (
    JiraIssueV2RecordMapper,
)

logger = structlog.get_logger(__name__)


class JiraIssueV2DocumentBuilder:
    """Build Jira Issue v2 documents while keeping v1/v2 id mapping explicit."""

    def __init__(
        self,
        *,
        mapper: JiraIssueV2RecordMapper | None = None,
    ) -> None:
        self.mapper = mapper or JiraIssueV2RecordMapper()

    def build_from_parsed_documents(
        self,
        parsed_documents: tuple[ParsedJiraIssueDocument, ...],
        *,
        cloud_id: str,
    ) -> tuple[list[Document], list[str], tuple[str, ...]]:
        documents: list[Document] = []
        source_ids: list[str] = []
        failed_document_ids: list[str] = []

        for parsed in parsed_documents:
            if not parsed.document.id:
                continue
            try:
                documents.append(
                    self.mapper.to_document(
                        parsed.issue,
                        cloud_id=cloud_id,
                        content=parsed.document.page_content,
                    )
                )
                source_ids.append(parsed.document.id)
            except Exception as exc:
                logger.warning(
                    "jira_issue_v2_document_build_failed",
                    cloud_id=cloud_id,
                    project_key=parsed.issue.project_key,
                    issue_key=parsed.issue.key,
                    document_id=parsed.document.id,
                    error=str(exc),
                    exc_info=True,
                )
                failed_document_ids.append(parsed.document.id)

        return documents, source_ids, tuple(dict.fromkeys(failed_document_ids))
