from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from contextlib import nullcontext
from typing import Protocol

import structlog
from langchain_core.documents import Document
from sqlalchemy.orm import Session

from catchup.connectors.jira.schemas import JiraIssue
from catchup.db.engine import SessionLocal
from catchup.sync.ingestion.adapters.jira.issue_assignee_resolver import (
    JiraIssueAssigneeResolver,
)
from catchup.sync.ingestion.adapters.jira.issue_execution import ParsedJiraIssueDocument
from catchup.sync.ingestion.vector_records.jira_issue_mapper import (
    JiraIssueV2RecordMapper,
)

logger = structlog.get_logger(__name__)
SessionFactory = Callable[[], AbstractContextManager[Session]]


class JiraIssueV2DocumentBuilder:
    """Build Jira Issue v2 documents while keeping v1/v2 id mapping explicit."""

    def __init__(
        self,
        *,
        mapper: JiraIssueV2RecordMapper | None = None,
        assignee_resolver: JiraIssueAssigneeResolver | None = None,
        session_factory: SessionFactory = SessionLocal,
    ) -> None:
        self.mapper = mapper or JiraIssueV2RecordMapper()
        self.assignee_resolver = assignee_resolver or JiraIssueAssigneeResolver()
        self._session_factory = session_factory

    def build_from_parsed_documents(
        self,
        parsed_documents: tuple[ParsedJiraIssueDocument, ...],
        *,
        cloud_id: str,
    ) -> tuple[list[Document], list[str], tuple[str, ...]]:
        documents: list[Document] = []
        source_ids: list[str] = []
        failed_document_ids: list[str] = []

        with self._session_context_for_issues(
            tuple(parsed.issue for parsed in parsed_documents)
        ) as db:
            for parsed in parsed_documents:
                if not parsed.document.id:
                    continue
                try:
                    documents.append(
                        self._build_document(
                            db,
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

    def build_from_backfill_seeds(
        self,
        issues: tuple[JiraIssue, ...],
        *,
        cloud_id: str,
        seed_by_issue_key: dict[str, JiraIssueV2BackfillSeedLike],
    ) -> tuple[list[Document], list[str], tuple[str, ...]]:
        documents: list[Document] = []
        document_ids: list[str] = []
        failed_issue_keys: list[str] = []

        with self._session_context_for_issues(issues) as db:
            for issue in issues:
                seed = seed_by_issue_key.get(issue.key)
                if seed is None:
                    failed_issue_keys.append(issue.key)
                    continue
                try:
                    document = self._build_document(
                        db,
                        issue,
                        cloud_id=cloud_id,
                        content=seed.content,
                    )
                except Exception as exc:
                    logger.warning(
                        "jira_issue_v2_backfill_document_build_failed",
                        cloud_id=cloud_id,
                        project_key=issue.project_key,
                        issue_key=issue.key,
                        document_id=seed.langchain_id,
                        error=str(exc),
                        exc_info=True,
                    )
                    failed_issue_keys.append(issue.key)
                    continue
                documents.append(
                    Document(
                        id=seed.langchain_id,
                        page_content=document.page_content,
                        metadata=dict(document.metadata),
                    )
                )
                document_ids.append(seed.langchain_id)

        return documents, document_ids, tuple(dict.fromkeys(failed_issue_keys))

    def _build_document(
        self,
        db: Session | None,
        issue: JiraIssue,
        *,
        cloud_id: str,
        content: str,
    ) -> Document:
        mapped_issue = self._apply_assignee_internal_user_id(db, issue)
        return self.mapper.to_document(
            mapped_issue,
            cloud_id=cloud_id,
            content=content,
        )

    def _apply_assignee_internal_user_id(
        self,
        db: Session | None,
        issue: JiraIssue,
    ) -> JiraIssue:
        assignee = issue.assignee
        account_id = assignee.account_id if assignee else None
        if db is None or assignee is None or not account_id:
            return issue

        internal_author_id = self.assignee_resolver.resolve_catchup_user_id(
            db,
            account_id,
        )
        if not internal_author_id:
            return issue

        return issue.model_copy(
            update={
                "assignee": assignee.model_copy(
                    update={"catchup_user_id": internal_author_id}
                )
            }
        )

    def _session_context_for_issues(
        self,
        issues: tuple[JiraIssue, ...],
    ) -> AbstractContextManager[Session | None]:
        if any(issue.assignee and issue.assignee.account_id for issue in issues):
            return self._session_factory()
        return nullcontext(None)


class JiraIssueV2BackfillSeedLike(Protocol):
    langchain_id: str
    record_id: str
    content: str
