from __future__ import annotations

from datetime import datetime, timezone

from catchup.audit.actions import FullSyncAction
from catchup.audit.metadata import FullSyncEventAuditMetadata
from catchup.audit.utils import audit_log
from catchup.connectors.github.factory import create_github_ingestion_service
from catchup.sync.common.schemas import FullSyncContext, TargetSyncResult
from catchup.sync.audit import SyncAuditContext
from catchup.worker.handlers.base_full_sync_handler import BaseFullSyncHandler

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
            else None
        )

        normalized_target_id = context.target_id.strip()
        if not normalized_target_id:
            raise ValueError("github repository_id(target_id) is empty")

        try:
            repo_id = int(normalized_target_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid github repository_id: {context.target_id}") from exc

        result = await service.full_sync(
            repo_ids=[repo_id],
            sync_from_dt=sync_from_dt,
            audit_context=SyncAuditContext(
                connector=context.connector,
                scope_id=context.scope_id,
                target_id=context.target_id,
                job_id=context.job_id,
                task_id=context.event_id,
            ),
        )

        if result.error_count > 0:
            raise RuntimeError(
                "[GITHUB][FULL SYNC][WORKER] Target sync failed: "
                f"scope_id={context.scope_id}, repository_id={context.target_id}, errors={result.error_count}"
            )
        return result
