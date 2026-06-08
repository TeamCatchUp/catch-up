from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone

import structlog

from catchup.audit.actions import FullSyncAction
from catchup.audit.actions import IncrementalSyncAction
from catchup.audit.metadata import FullSyncEventAuditMetadata
from catchup.audit.metadata import IncrementalRecordAuditMetadata
from catchup.audit.utils import audit_log
from catchup.configs.config import settings
from catchup.connector_core.adapters.github import (
    GithubRepositoryFullSyncExecutionRequest,
)
from catchup.connector_core.adapters.github import (
    GithubRepositoryIncrementalSyncExecutionRequest,
)
from catchup.connector_core.adapters.github import GithubRepositorySyncAdapter
from catchup.connectors.github.client import GitHubRateLimitError
from catchup.connectors.github.factory import create_github_ingestion_service
from catchup.sync.audit import SyncAuditContext
from catchup.sync.common.exceptions import SyncInternalException
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import IncrementalSyncContext
from catchup.sync.common.schemas import TargetSyncResult
from catchup.sync.handlers.base import BaseFullSyncHandler
from catchup.sync.handlers.base import BaseIncrementalHandler
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.sync.ingestion.schemas import SyncWindow

logger = structlog.get_logger(__name__)


class GithubFullSyncHandler(BaseFullSyncHandler):
    connector = "github"

    async def _get_service(self, scope_id: str, cache: dict[str, object]):
        normalized_scope_id = scope_id.strip()
        cache_key = self._cache_key(normalized_scope_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        if not normalized_scope_id:
            raise ValueError("github installation_id(scope_id) is empty")

        try:
            installation_id = int(normalized_scope_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid github installation_id: {scope_id}") from exc

        service = await create_github_ingestion_service(installation_id=installation_id)
        cache[cache_key] = service
        return service

    @audit_log(
        FullSyncAction.EVENT,
        metadata_factory=FullSyncEventAuditMetadata.from_audit,
        emit_attempt=True,
    )
    async def handle(
        self,
        *,
        context: FullSyncContext,
        service_cache: dict[str, object],
    ) -> TargetSyncResult:
        service = await self._get_service(context.scope_id, service_cache)
        sync_from_dt = (
            datetime.fromtimestamp(float(context.sync_from_ts), tz=timezone.utc)
            if context.sync_from_ts is not None
            else datetime.now(timezone.utc) - timedelta(days=settings.DEFAULT_SYNC_DAYS)
        )

        normalized_target_id = context.target_id.strip()
        if not normalized_target_id:
            raise ValueError("github repository_id(target_id) is empty")

        try:
            repo_id = int(normalized_target_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid github repository_id: {context.target_id}") from exc

        record_type = str(
            context.metadata.get("record_type")
            or context.metadata.get("stream_type")
            or ""
        ).strip()
        if record_type not in {"issue", "pull_request"}:
            logger.error(
                "github_full_sync_missing_stream_metadata",
                connector="github",
                sync_type="full",
                scope_id=context.scope_id,
                repository_id=context.target_id,
                job_id=context.job_id,
                event_id=context.event_id,
                record_type=record_type,
            )
            raise RuntimeError("github_full_sync_missing_stream_metadata")

        repo_full_name = str(
            context.metadata.get("repo_full_name")
            or context.target_name.split(" / ", 1)[0]
        ).strip()
        if "/" not in repo_full_name:
            logger.error(
                "github_full_sync_invalid_repository_metadata",
                connector="github",
                sync_type="full",
                scope_id=context.scope_id,
                repository_id=context.target_id,
                job_id=context.job_id,
                event_id=context.event_id,
                repo_full_name=repo_full_name,
            )
            raise RuntimeError("github_full_sync_invalid_repository_metadata")
        owner, repo = repo_full_name.split("/", 1)

        audit_context = SyncAuditContext(
            connector=context.connector,
            scope_id=context.scope_id,
            target_id=context.target_id,
            job_id=context.job_id,
            task_id=context.event_id,
        )
        sync_window = SyncWindow(
            window_start=sync_from_dt,
            window_end=datetime.now(timezone.utc),
        )
        adapter = GithubRepositorySyncAdapter(service=service)
        synced_count = 0
        error_count = 0
        batch_index = 0
        after_cursor: str | None = None
        while True:
            execution = GithubRepositoryFullSyncExecutionRequest(
                tenant_id=context.scope_id,
                repo_id=repo_id,
                repo_full_name=repo_full_name,
                owner=owner,
                repo=repo,
                record_type=record_type,
                batch_index=batch_index,
                after_cursor=after_cursor,
                sync_from_dt=sync_from_dt,
                audit_context=audit_context,
            )
            try:
                result = await run_sync_ingestion(
                    port=adapter,
                    execution=execution,
                    sync_window=sync_window,
                )
            except GitHubRateLimitError:
                raise
            except Exception as exc:
                adapter.mark_full_sync_failed(execution=execution, exc=exc)
                raise

            synced_count += result.persisted_count + result.deleted_count
            error_count += result.failed_count
            if result.is_last:
                break
            after_cursor = result.next_cursor
            if after_cursor is None:
                logger.error(
                    "github_full_sync_missing_next_cursor",
                    connector="github",
                    sync_type="full",
                    scope_id=context.scope_id,
                    repository_id=context.target_id,
                    job_id=context.job_id,
                    event_id=context.event_id,
                    record_type=record_type,
                    batch_index=batch_index,
                )
                raise RuntimeError("github_full_sync_missing_next_cursor")
            batch_index += 1

        if error_count > 0:
            logger.error(
                "github_full_sync_failed",
                connector="github",
                sync_type="full",
                scope_id=context.scope_id,
                repository_id=context.target_id,
                job_id=context.job_id,
                event_id=context.event_id,
                error_count=error_count,
            )
            raise RuntimeError("github_full_sync_failed")
        return TargetSyncResult(
            synced_count=synced_count,
            error_count=error_count,
        )


class GithubIncrementalHandler(BaseIncrementalHandler):
    connector = "github"

    async def _get_service(self, scope_id: str, cache: dict[str, object]):
        normalized_scope_id = scope_id.strip()
        if not normalized_scope_id:
            raise ValueError("github installation_id(scope_id) is empty")

        cache_key = self._cache_key(normalized_scope_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        service = await create_github_ingestion_service(
            installation_id=int(normalized_scope_id),
        )
        cache[cache_key] = service
        return service

    @audit_log(
        IncrementalSyncAction.RECORD,
        metadata_factory=IncrementalRecordAuditMetadata.from_audit,
        emit_attempt=True,
    )
    async def handle(
        self,
        *,
        context: IncrementalSyncContext,
        service_cache: dict[str, object],
    ) -> TargetSyncResult:
        service = await self._get_service(context.scope_id, service_cache)
        parent_id = context.parent_id or context.target_id
        if not parent_id:
            raise ValueError("github repository id is empty")

        since = self._resolve_since(context)
        result = await run_sync_ingestion(
            port=GithubRepositorySyncAdapter(service=service),
            execution=GithubRepositoryIncrementalSyncExecutionRequest(
                tenant_id=context.scope_id,
                repo_id=int(parent_id),
                record_type=context.record_type or "",
                record_id=context.record_id or "",
                event_kind=context.event_kind or "updated",
                since=since,
                audit_context=SyncAuditContext(
                    connector=context.connector,
                    scope_id=context.scope_id,
                    target_id=context.target_id,
                    job_id=context.job_id,
                    task_id=context.event_id,
                ),
            ),
            sync_window=SyncWindow(
                window_start=since,
                window_end=datetime.now(timezone.utc),
            ),
        )

        if result.failed_count > 0:
            raise SyncInternalException(
                "github incremental sync failed",
                metadata={"record_key": context.record_key},
            )
        return TargetSyncResult(
            synced_count=result.persisted_count + result.deleted_count,
            error_count=result.failed_count,
            skipped=result.skipped,
        )
