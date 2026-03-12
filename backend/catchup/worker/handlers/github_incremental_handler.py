from __future__ import annotations

from catchup.connectors.github.factory import create_github_ingestion_service
from catchup.sync.common.exceptions import SyncInternalError
from catchup.sync.common.schemas import IncrementalSyncContext, TargetSyncResult
from catchup.worker.handlers.base_incremental_handler import BaseIncrementalHandler


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

        from catchup.db.engine import SessionLocal

        with SessionLocal() as db:
            service = await create_github_ingestion_service(
                db=db,
                installation_id=int(normalized_scope_id),
            )

        cache[cache_key] = service
        return service

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

        from catchup.db.engine import SessionLocal

        with SessionLocal() as db:
            result = await service.incremental_sync(
                db=db,
                repo_id=int(parent_id),
                record_type=context.record_type or "",
                record_id=context.record_id or "",
                event_kind=context.event_kind or "updated",
                since=self._resolve_since(context),
            )

        if int(result.get("errors", 0)) > 0:
            raise SyncInternalError(
                "github incremental sync failed",
                metadata={"record_key": context.record_key},
            )
        return TargetSyncResult.from_mapping(result)
