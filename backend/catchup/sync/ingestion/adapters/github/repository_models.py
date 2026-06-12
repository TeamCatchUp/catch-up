from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import Any
from typing import Literal

from langchain_core.documents import Document
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import ValidationInfo
from pydantic import computed_field
from pydantic import field_validator

from catchup.connectors.github.schemas import GithubPullRequest
from catchup.db.models import SyncConnector
from catchup.sync.audit import SyncAuditContext
from catchup.sync.ingestion.schemas import SyncExecutionRequest
from catchup.sync.ingestion.schemas import SyncExecutionResult
from catchup.utils.validation import require_text

GithubRecordType = Literal["issue", "pull_request"]
GithubIncrementalEventKind = Literal["created", "updated", "deleted"]


class SyncOperation:
    ISSUE_SYNC = "ISSUE_SYNC"
    PR_SYNC = "PR_SYNC"


@dataclass(slots=True, frozen=True)
class GithubRepoRef:
    repo_id: int
    full_name: str
    owner: str
    repo: str


@dataclass(slots=True, frozen=True)
class GithubRecordGapItem:
    record_type: str
    expected_count: int = 0
    stored_count: int = 0
    missing_count: int = 0
    missing_ids: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class GithubRecordGapReport:
    records: list[GithubRecordGapItem] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class GithubRecordRetryItem:
    record_type: str
    requested_ids: list[str] = field(default_factory=list)
    retried_count: int = 0
    succeeded_count: int = 0
    failed_ids: list[str] = field(default_factory=list)
    remaining_missing_ids: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class GithubRecordRetryResult:
    records: list[GithubRecordRetryItem] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class GithubPrDocumentBundle:
    pull_request: GithubPullRequest
    document: Document


@dataclass(slots=True, frozen=True)
class GithubRepositoryDualWriteResult:
    persisted_ids: list[str] = field(default_factory=list)
    v2_failed_ids: tuple[str, ...] = ()


class GithubPrV2BackfillSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    langchain_id: str
    record_id: str
    content: str
    embedding: list[float]

    @field_validator("langchain_id", "record_id")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @field_validator("embedding")
    @classmethod
    def _validate_embedding(cls, value: list[float]) -> list[float]:
        if not value:
            raise ValueError("embedding must not be empty")
        return value


class GithubPrV2BackfillExecutionRequest(SyncExecutionRequest):
    model_config = ConfigDict(extra="forbid")

    connector: Literal[SyncConnector.GITHUB] = SyncConnector.GITHUB
    target: Literal["repository_pr_v2_backfill"] = "repository_pr_v2_backfill"
    owner: str
    repo: str
    seeds: tuple[GithubPrV2BackfillSeed, ...]
    audit_context: SyncAuditContext | None = None

    @field_validator("owner", "repo")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @computed_field
    @property
    def repo_full_name(self) -> str:
        return f"{self.owner}/{self.repo}"

    def log_context(self) -> dict[str, object]:
        return {
            "repo_full_name": self.repo_full_name,
            "record_type": "pull_request",
            "seed_count": len(self.seeds),
        }


class GithubRepositoryFullSyncExecutionRequest(SyncExecutionRequest):
    model_config = ConfigDict(extra="forbid")

    connector: Literal[SyncConnector.GITHUB] = SyncConnector.GITHUB
    target: Literal["repository"] = "repository"
    owner: str
    repo: str
    record_type: GithubRecordType
    batch_index: int = 0
    after_cursor: str | None = None
    audit_context: SyncAuditContext | None = None

    @field_validator("owner", "repo")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @computed_field
    @property
    def repo_full_name(self) -> str:
        return f"{self.owner}/{self.repo}"

    def log_context(self) -> dict[str, object]:
        return {
            "repo_full_name": self.repo_full_name,
            "record_type": self.record_type,
            "batch_index": self.batch_index,
            "after_cursor_present": self.after_cursor is not None,
        }


class GithubRepositoryIncrementalSyncExecutionRequest(SyncExecutionRequest):
    connector: Literal[SyncConnector.GITHUB] = SyncConnector.GITHUB
    target: Literal["repository"] = "repository"
    repo_id: int
    record_type: GithubRecordType
    record_id: str
    event_kind: GithubIncrementalEventKind = "updated"
    since: datetime | None = None
    audit_context: SyncAuditContext | None = None

    @field_validator("record_id")
    @classmethod
    def _validate_record_id(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @computed_field
    @property
    def is_delete_event(self) -> bool:
        return self.event_kind == "deleted"

    def log_context(self) -> dict[str, object]:
        return {
            "repo_id": self.repo_id,
            "record_type": self.record_type,
            "record_id": self.record_id,
            "event_kind": self.event_kind,
        }


class GithubRepositoryFetchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_count: int = 1
    records: tuple[dict[str, Any], ...] = ()
    exact_items: tuple[tuple[str, dict[str, Any]], ...] = ()
    failed_record_ids: tuple[str, ...] = ()
    record_type: GithubRecordType | None = None
    owner: str | None = None
    repo: str | None = None
    repo_full_name: str | None = None
    batch_index: int = 0
    is_last: bool = True
    checkpoint: int | None = None
    next_cursor: str | None = None
    stopped_by_since: bool = False

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "record_type": self.record_type,
            "batch_index": self.batch_index,
            "record_count": len(self.records),
            "failed_record_count": len(self.failed_record_ids),
            "is_last": self.is_last,
            "next_cursor_present": self.next_cursor is not None,
            "stopped_by_since": self.stopped_by_since,
        }


class GithubRepositoryTransformResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    requested_count: int = 1
    v1_documents: tuple[Document, ...] = ()
    v2_documents: tuple[Document, ...] = ()
    document_ids: tuple[str, ...] = ()
    error_count: int = 0
    failed_record_ids: tuple[str, ...] = ()
    owner: str | None = None
    repo: str | None = None
    repo_full_name: str | None = None

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "document_count": len(self.v1_documents),
            "v2_document_count": len(self.v2_documents),
            "error_count": self.error_count,
            "failed_record_count": len(self.failed_record_ids),
        }


class GithubRepositorySummaryResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    summary_applied: bool = False
    v1_documents: tuple[Document, ...] = ()
    v2_documents: tuple[Document, ...] = ()
    document_ids: tuple[str, ...] = ()


class GithubRepositoryPersistResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted_count: int = 0
    deleted_count: int = 0
    error_count: int = 0
    v2_error_count: int = 0
    v2_failed_ids: tuple[str, ...] = ()
    skipped: bool = False

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "persisted_count": self.persisted_count,
            "deleted_count": self.deleted_count,
            "error_count": self.error_count,
            "v2_error_count": self.v2_error_count,
            "v2_failed_count": len(self.v2_failed_ids),
            "skipped": self.skipped,
        }


class GithubRepositorySyncExecutionResult(SyncExecutionResult):
    connector: Literal[SyncConnector.GITHUB] = SyncConnector.GITHUB
    target: Literal["repository", "repository_pr_v2_backfill"] = "repository"
    persisted_count: int = 0
    deleted_count: int = 0
    failed_count: int = 0
    v2_failed_count: int = 0
    v2_failed_ids: tuple[str, ...] = ()
    skipped: bool = False
    fetched: GithubRepositoryFetchResult
    transformed: GithubRepositoryTransformResult
    summary: GithubRepositorySummaryResult
    persisted: GithubRepositoryPersistResult
    record_type: GithubRecordType | None = None
    batch_index: int = 0
    is_last: bool = True
    checkpoint: int | None = None
    next_cursor: str | None = None
    stopped_by_since: bool = False

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "persisted_count": self.persisted_count,
            "deleted_count": self.deleted_count,
            "failed_count": self.failed_count,
            "v2_failed_count": self.v2_failed_count,
            "skipped": self.skipped,
            "record_type": self.record_type,
            "batch_index": self.batch_index,
            "is_last": self.is_last,
            "next_cursor_present": self.next_cursor is not None,
            "stopped_by_since": self.stopped_by_since,
        }
