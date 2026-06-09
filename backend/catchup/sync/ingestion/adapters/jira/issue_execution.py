from __future__ import annotations

from typing import Literal

from langchain_core.documents import Document
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationInfo
from pydantic import computed_field
from pydantic import field_validator

from catchup.db.models import SyncConnector
from catchup.sync.audit import SyncAuditContext
from catchup.sync.ingestion.schemas import SyncExecutionRequest
from catchup.sync.ingestion.schemas import SyncExecutionResult
from catchup.utils.validation import require_text

JiraIssueIncrementalEventKind = Literal[
    "created",
    "updated",
    "deleted",
    "comment_created",
    "comment_updated",
    "comment_deleted",
]


class JiraIssueFullSyncExecutionRequest(SyncExecutionRequest):
    connector: Literal[SyncConnector.JIRA] = SyncConnector.JIRA
    target: Literal["issue"] = "issue"
    project_key: str
    batch_index: int = Field(ge=0)
    next_page_token: str | None = None
    max_results: int = Field(gt=0)
    audit_context: SyncAuditContext | None = None

    @field_validator("project_key")
    @classmethod
    def _validate_project_key(cls, value: str) -> str:
        return require_text(value, "project_key")

    def log_context(self) -> dict[str, object]:
        return {
            "project_key": self.project_key,
            "batch_index": self.batch_index,
            "max_results": self.max_results,
            "request_next_page_token_present": bool(self.next_page_token),
        }


class JiraIssueIncrementalSyncExecutionRequest(SyncExecutionRequest):
    connector: Literal[SyncConnector.JIRA] = SyncConnector.JIRA
    target: Literal["issue"] = "issue"
    project_key: str
    issue_key: str
    event_kind: JiraIssueIncrementalEventKind = "updated"
    audit_context: SyncAuditContext | None = None

    @field_validator("project_key", "issue_key")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @computed_field
    @property
    def is_delete_event(self) -> bool:
        return self.event_kind == "deleted"

    def log_context(self) -> dict[str, object]:
        return {
            "project_key": self.project_key,
            "issue_key": self.issue_key,
            "event_kind": self.event_kind,
        }


class JiraIssueFetchedIssuesResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: tuple[dict, ...] = ()
    fetched_record_ids: tuple[str, ...] = ()

    @property
    def fetched_count(self) -> int:
        return len(self.issues)

    def connector_log_summary(self) -> dict[str, object]:
        return {"fetched_count": self.fetched_count}


class JiraIssueFullSyncFetchResult(JiraIssueFetchedIssuesResult):
    batch_index: int = 0
    is_last: bool = True
    next_page_token: str | None = None

    @property
    def next_page_token_present(self) -> bool:
        return bool(self.next_page_token)

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "fetched_count": self.fetched_count,
            "is_last": self.is_last,
            "response_next_page_token_present": self.next_page_token_present,
        }


class JiraIssueIncrementalFetchResult(JiraIssueFetchedIssuesResult):
    pass


class JiraIssueTransformResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    documents: tuple[Document, ...] = ()
    prepared_document_ids: tuple[str, ...] = ()
    issue_count: int = 0
    error_count: int = 0

    @property
    def document_count(self) -> int:
        return len(self.documents)

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "document_count": self.document_count,
            "issue_count": self.issue_count,
            "error_count": self.error_count,
        }


class JiraIssueSummaryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary_applied: bool = False
    document_count: int = 0


class JiraIssuePersistResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted_count: int = 0
    persisted_ids: tuple[str, ...] = ()
    deleted_count: int = 0

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "persisted_count": self.persisted_count,
            "deleted_count": self.deleted_count,
        }


class JiraIssueSyncExecutionResult(SyncExecutionResult):
    connector: Literal[SyncConnector.JIRA] = SyncConnector.JIRA
    target: Literal["issue"] = "issue"
    fetched_count: int = 0
    document_count: int = 0
    persisted_count: int = 0
    issue_count: int = 0
    deleted_count: int = 0
    error_count: int = 0
    skipped: bool = False
    batch_index: int = 0
    is_last: bool = True
    next_page_token: str | None = None
    fetched: JiraIssueFetchedIssuesResult
    transformed: JiraIssueTransformResult
    summary: JiraIssueSummaryResult
    persisted: JiraIssuePersistResult

    @property
    def next_page_token_present(self) -> bool:
        return bool(self.next_page_token)

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "fetched_count": self.fetched_count,
            "document_count": self.document_count,
            "persisted_count": self.persisted_count,
            "issue_count": self.issue_count,
            "deleted_count": self.deleted_count,
            "error_count": self.error_count,
            "is_last": self.is_last,
            "response_next_page_token_present": self.next_page_token_present,
        }
