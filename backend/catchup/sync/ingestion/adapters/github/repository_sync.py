from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Literal

from fastapi.concurrency import run_in_threadpool
from langchain_core.documents import Document
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import ValidationInfo
from pydantic import computed_field
from pydantic import field_validator

from catchup.connectors.github.client import GitHubRateLimitError
from catchup.connectors.github.service import GithubIngestionService
from catchup.connectors.github.service import SyncOperation
from catchup.db.models import GithubEntityType
from catchup.db.models import SyncConnector
from catchup.sync.audit import SyncAuditContext
from catchup.sync.ingestion.schemas import SyncExecutionRequest
from catchup.sync.ingestion.schemas import SyncExecutionResult
from catchup.sync.ingestion.schemas import SyncWindow
from catchup.utils.validation import require_text

GithubRecordType = Literal["issue", "pull_request"]
GithubIncrementalEventKind = Literal["created", "updated", "deleted"]


class GithubRepositoryFullSyncExecutionRequest(SyncExecutionRequest):
    model_config = ConfigDict(extra="forbid")

    connector: Literal[SyncConnector.GITHUB] = SyncConnector.GITHUB
    target: Literal["repository"] = "repository"
    repo_id: int
    repo_full_name: str
    owner: str
    repo: str
    record_type: GithubRecordType
    batch_index: int = 0
    after_cursor: str | None = None
    records: tuple[dict[str, Any], ...] = ()
    sync_from_dt: datetime | None = None
    audit_context: SyncAuditContext | None = None

    @field_validator("repo_full_name", "owner", "repo")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    def log_context(self) -> dict[str, object]:
        return {
            "repo_id": self.repo_id,
            "repo_full_name": self.repo_full_name,
            "record_type": self.record_type,
            "batch_index": self.batch_index,
            "after_cursor_present": self.after_cursor is not None,
            "record_count": len(self.records),
            "sync_from_dt_present": self.sync_from_dt is not None,
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
    documents: tuple[Document, ...] = ()
    document_ids: tuple[str, ...] = ()
    error_count: int = 0
    failed_record_ids: tuple[str, ...] = ()
    owner: str | None = None
    repo: str | None = None
    repo_full_name: str | None = None

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "document_count": len(self.documents),
            "error_count": self.error_count,
            "failed_record_count": len(self.failed_record_ids),
        }


class GithubRepositorySummaryResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    summary_applied: bool = False
    documents: tuple[Document, ...] = ()
    document_ids: tuple[str, ...] = ()


class GithubRepositoryPersistResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persisted_count: int = 0
    deleted_count: int = 0
    error_count: int = 0
    skipped: bool = False

    def connector_log_summary(self) -> dict[str, object]:
        return {
            "persisted_count": self.persisted_count,
            "deleted_count": self.deleted_count,
            "error_count": self.error_count,
            "skipped": self.skipped,
        }


class GithubRepositorySyncExecutionResult(SyncExecutionResult):
    connector: Literal[SyncConnector.GITHUB] = SyncConnector.GITHUB
    target: Literal["repository"] = "repository"
    persisted_count: int = 0
    deleted_count: int = 0
    failed_count: int = 0
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
            "skipped": self.skipped,
            "record_type": self.record_type,
            "batch_index": self.batch_index,
            "is_last": self.is_last,
            "next_cursor_present": self.next_cursor is not None,
            "stopped_by_since": self.stopped_by_since,
        }


class GithubRepositorySyncAdapter:
    """Bounded GitHub repository or exact record execution adapter."""

    def __init__(self, *, service: GithubIngestionService) -> None:
        self._service = service
        self._started_full_keys: set[tuple[int, GithubRecordType]] = set()
        self._pending_full_completion_keys: set[tuple[int, GithubRecordType]] = set()
        self._persisted_by_key: dict[tuple[int, GithubRecordType], int] = {}

    async def fetch(
        self,
        *,
        execution: GithubRepositoryFullSyncExecutionRequest
        | GithubRepositoryIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
    ) -> GithubRepositoryFetchResult:
        _ = sync_window
        if isinstance(execution, GithubRepositoryFullSyncExecutionRequest):
            return await self._fetch_full_sync_page(execution)
        return await self._fetch_incremental_record(execution)

    async def transform(
        self,
        *,
        execution: GithubRepositoryFullSyncExecutionRequest
        | GithubRepositoryIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        fetched: GithubRepositoryFetchResult,
    ) -> GithubRepositoryTransformResult:
        _ = sync_window
        if isinstance(execution, GithubRepositoryFullSyncExecutionRequest):
            if execution.record_type == "issue":
                documents, document_ids, error_count = await run_in_threadpool(
                    self._service._build_issue_batch_documents_sync,
                    execution.owner,
                    execution.repo,
                    list(fetched.records),
                )
            else:
                documents, document_ids, error_count = await run_in_threadpool(
                    self._service._build_pull_request_batch_documents_sync,
                    execution.owner,
                    execution.repo,
                    list(fetched.records),
                )
            return GithubRepositoryTransformResult(
                requested_count=fetched.requested_count,
                documents=tuple(documents),
                document_ids=tuple(document_ids),
                error_count=error_count + len(fetched.failed_record_ids),
                failed_record_ids=fetched.failed_record_ids,
                owner=execution.owner,
                repo=execution.repo,
                repo_full_name=execution.repo_full_name,
            )

        if execution.is_delete_event:
            return GithubRepositoryTransformResult(
                requested_count=fetched.requested_count,
                owner=fetched.owner,
                repo=fetched.repo,
                repo_full_name=fetched.repo_full_name,
            )

        if execution.record_type == "issue":
            documents, failed_ids = await run_in_threadpool(
                self._service._build_issue_documents_sync,
                fetched.owner or "",
                fetched.repo or "",
                list(fetched.exact_items),
            )
        else:
            documents, failed_ids = await run_in_threadpool(
                self._service._build_pull_request_documents_sync,
                fetched.owner or "",
                fetched.repo or "",
                list(fetched.exact_items),
            )
        failed_record_ids = tuple((*fetched.failed_record_ids, *failed_ids))
        return GithubRepositoryTransformResult(
            requested_count=fetched.requested_count,
            documents=tuple(documents),
            document_ids=tuple(doc.id for doc in documents),
            error_count=len(set(failed_record_ids)),
            failed_record_ids=failed_record_ids,
            owner=fetched.owner,
            repo=fetched.repo,
            repo_full_name=fetched.repo_full_name,
        )

    async def summarize(
        self,
        *,
        execution: GithubRepositoryFullSyncExecutionRequest
        | GithubRepositoryIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        transformed: GithubRepositoryTransformResult,
    ) -> GithubRepositorySummaryResult:
        _ = sync_window
        if isinstance(execution, GithubRepositoryFullSyncExecutionRequest):
            documents = list(transformed.documents)
            summarizer = getattr(self._service, "summarizer", None)
            if summarizer and documents:
                documents = await self._service._summarize_documents(
                    documents,
                    repo_full_name=execution.repo_full_name,
                    entity_type=execution.record_type,
                    audit_context=execution.audit_context,
                )
            return GithubRepositorySummaryResult(
                summary_applied=bool(summarizer and documents),
                documents=tuple(documents),
                document_ids=tuple(doc.id for doc in documents),
            )

        documents = list(transformed.documents)
        summarizer = getattr(self._service, "summarizer", None)
        if summarizer and documents:
            documents = await self._service._summarize_documents(
                documents,
                repo_full_name=transformed.repo_full_name or str(execution.repo_id),
                entity_type=execution.record_type,
                audit_context=execution.audit_context,
            )
        return GithubRepositorySummaryResult(
            summary_applied=bool(summarizer and documents),
            documents=tuple(documents),
            document_ids=tuple(doc.id for doc in documents),
        )

    async def persist(
        self,
        *,
        execution: GithubRepositoryFullSyncExecutionRequest
        | GithubRepositoryIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        transformed: GithubRepositoryTransformResult,
        summary: GithubRepositorySummaryResult,
    ) -> GithubRepositoryPersistResult:
        _ = sync_window
        if isinstance(execution, GithubRepositoryFullSyncExecutionRequest):
            error_count = transformed.error_count
            documents = list(summary.documents)
            document_ids = list(summary.document_ids)
            if not documents:
                self._complete_full_sync_if_pending(execution)
                return GithubRepositoryPersistResult(error_count=error_count)

            await self._service.repository.upsert_documents(
                documents,
                document_ids,
                audit_context=execution.audit_context,
                context=(
                    f"entity_type={execution.record_type},"
                    f"repo={execution.repo_full_name},"
                    f"batch={execution.batch_index},"
                    f"doc_count={len(documents)}"
                ),
            )
            key = (execution.repo_id, execution.record_type)
            self._persisted_by_key[key] = (
                self._persisted_by_key.get(key, 0) + len(documents)
            )
            self._complete_full_sync_if_pending(execution)
            return GithubRepositoryPersistResult(
                persisted_count=len(documents),
                error_count=error_count,
            )

        if execution.is_delete_event:
            doc_id = self._document_id_for_incremental_delete(
                execution=execution,
                owner=transformed.owner or "",
                repo=transformed.repo or "",
            )
            await self._service.repository.delete_documents([doc_id])
            return GithubRepositoryPersistResult(deleted_count=1)

        error_count = transformed.error_count
        documents = list(summary.documents)
        if not documents:
            return GithubRepositoryPersistResult(error_count=max(1, error_count))

        await self._service.repository.upsert_documents(
            documents,
            list(summary.document_ids),
            audit_context=execution.audit_context,
            context=(
                f"entity_type={execution.record_type},"
                f"repo={transformed.repo_full_name or execution.repo_id},"
                "mode=incremental_exact,"
                f"doc_count={len(documents)}"
            ),
        )
        return GithubRepositoryPersistResult(
            persisted_count=len(documents),
            error_count=error_count,
        )

    def build_result(
        self,
        *,
        execution: GithubRepositoryFullSyncExecutionRequest
        | GithubRepositoryIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        fetched: GithubRepositoryFetchResult,
        transformed: GithubRepositoryTransformResult,
        summary: GithubRepositorySummaryResult,
        persisted: GithubRepositoryPersistResult,
    ) -> GithubRepositorySyncExecutionResult:
        _ = sync_window
        return GithubRepositorySyncExecutionResult(
            tenant_id=execution.tenant_id,
            persisted_count=persisted.persisted_count,
            deleted_count=persisted.deleted_count,
            failed_count=persisted.error_count,
            skipped=persisted.skipped,
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=persisted,
            record_type=fetched.record_type,
            batch_index=fetched.batch_index,
            is_last=fetched.is_last,
            checkpoint=fetched.checkpoint,
            next_cursor=fetched.next_cursor,
            stopped_by_since=fetched.stopped_by_since,
            metadata={
                "record_type": fetched.record_type,
                "batch_index": fetched.batch_index,
                "is_last": fetched.is_last,
                "checkpoint": fetched.checkpoint,
                "next_cursor": fetched.next_cursor,
                "stopped_by_since": fetched.stopped_by_since,
            },
        )

    async def _fetch_full_sync_page(
        self,
        execution: GithubRepositoryFullSyncExecutionRequest,
    ) -> GithubRepositoryFetchResult:
        if execution.records:
            return GithubRepositoryFetchResult(
                requested_count=1,
                records=execution.records,
                record_type=execution.record_type,
                batch_index=execution.batch_index,
                is_last=True,
                checkpoint=execution.batch_index,
            )

        self._ensure_full_sync_started(execution)

        try:
            if execution.record_type == "issue":
                page = await self._service.client.fetch_issues_graphql_page(
                    owner=execution.owner,
                    repo=execution.repo,
                    after_cursor=execution.after_cursor,
                    since=execution.sync_from_dt,
                )
            else:
                page = await self._service.client.fetch_pull_requests_graphql_page(
                    owner=execution.owner,
                    repo=execution.repo,
                    after_cursor=execution.after_cursor,
                    since=execution.sync_from_dt,
                )
            if page.is_last:
                key = (execution.repo_id, execution.record_type)
                self._pending_full_completion_keys.add(key)
            return GithubRepositoryFetchResult(
                requested_count=1,
                records=page.nodes,
                record_type=execution.record_type,
                batch_index=execution.batch_index,
                is_last=page.is_last,
                checkpoint=execution.batch_index,
                next_cursor=page.next_cursor,
                stopped_by_since=page.stopped_by_since,
            )
        except GitHubRateLimitError as exc:
            self._handle_full_sync_rate_limit(execution, exc)
            raise

    async def _fetch_incremental_record(
        self,
        execution: GithubRepositoryIncrementalSyncExecutionRequest,
    ) -> GithubRepositoryFetchResult:
        repo_ref = await self._service._get_repo_ref(execution.repo_id)
        if execution.is_delete_event:
            return GithubRepositoryFetchResult(
                requested_count=1,
                record_type=execution.record_type,
                owner=repo_ref.owner,
                repo=repo_ref.repo,
                repo_full_name=repo_ref.full_name,
            )

        if execution.record_type == "issue":
            items, failed_ids = await self._service._fetch_issue_nodes(
                owner=repo_ref.owner,
                repo=repo_ref.repo,
                issue_ids=[execution.record_id],
            )
        else:
            items, failed_ids = await self._service._fetch_pull_request_nodes(
                owner=repo_ref.owner,
                repo=repo_ref.repo,
                pull_request_ids=[execution.record_id],
            )
        return GithubRepositoryFetchResult(
            requested_count=1,
            exact_items=tuple(items),
            failed_record_ids=tuple(failed_ids),
            record_type=execution.record_type,
            owner=repo_ref.owner,
            repo=repo_ref.repo,
            repo_full_name=repo_ref.full_name,
        )

    def _ensure_full_sync_started(
        self,
        execution: GithubRepositoryFullSyncExecutionRequest,
    ) -> None:
        key = (execution.repo_id, execution.record_type)
        if key in self._started_full_keys:
            return
        entity_type, operation = self._full_sync_observability(execution.record_type)
        self._service._start_sync(execution.repo_full_name, entity_type, operation)
        self._started_full_keys.add(key)

    def _complete_full_sync(
        self,
        execution: GithubRepositoryFullSyncExecutionRequest,
    ) -> None:
        key = (execution.repo_id, execution.record_type)
        entity_type, operation = self._full_sync_observability(execution.record_type)
        self._service._complete_sync(
            execution.repo_full_name,
            entity_type,
            self._persisted_by_key.get(key, 0),
            operation,
        )

    def _complete_full_sync_if_pending(
        self,
        execution: GithubRepositoryFullSyncExecutionRequest,
    ) -> None:
        key = (execution.repo_id, execution.record_type)
        if key not in self._pending_full_completion_keys:
            return
        self._complete_full_sync(execution)
        self._pending_full_completion_keys.remove(key)

    def _handle_full_sync_rate_limit(
        self,
        execution: GithubRepositoryFullSyncExecutionRequest,
        exc: GitHubRateLimitError,
    ) -> None:
        entity_type, operation = self._full_sync_observability(execution.record_type)
        self._service._handle_rate_limit(
            execution.repo_full_name,
            entity_type,
            exc,
            operation,
        )

    def mark_full_sync_failed(
        self,
        *,
        execution: GithubRepositoryFullSyncExecutionRequest,
        exc: Exception,
    ) -> None:
        entity_type, operation = self._full_sync_observability(execution.record_type)
        self._service._fail_sync(
            execution.repo_full_name,
            entity_type,
            str(exc),
            operation,
        )

    @staticmethod
    def _full_sync_observability(
        record_type: GithubRecordType,
    ) -> tuple[GithubEntityType, str]:
        if record_type == "issue":
            return GithubEntityType.ISSUE, SyncOperation.ISSUE_SYNC
        return GithubEntityType.PULL_REQUEST, SyncOperation.PR_SYNC

    @staticmethod
    def _document_id_for_incremental_delete(
        *,
        execution: GithubRepositoryIncrementalSyncExecutionRequest,
        owner: str,
        repo: str,
    ) -> str:
        if execution.record_type == "issue":
            return f"github:issue:{owner}/{repo}:{execution.record_id}"
        return f"github:pr:{owner}/{repo}:{execution.record_id}"
