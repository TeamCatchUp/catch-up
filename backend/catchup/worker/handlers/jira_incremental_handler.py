from __future__ import annotations

from catchup.connectors.jira.factory import create_jira_ingestion_service
from catchup.sync.common.exceptions import SyncInternalError
from catchup.worker.handlers.base_incremental_handler import BaseIncrementalHandler


class JiraIncrementalHandler(BaseIncrementalHandler):
    connector = "jira"

    async def _get_service(self, scope_id: str, cache: dict[str, object]):
        cloud_id = scope_id.strip()
        if not cloud_id:
            raise ValueError("jira cloud_id(scope_id) is empty")

        cache_key = self._cache_key(cloud_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        from catchup.db.engine import SessionLocal

        with SessionLocal() as db:
            service = await create_jira_ingestion_service(db=db, cloud_id=cloud_id)

        cache[cache_key] = service
        return service

    async def handle(
        self,
        *,
        context,
        service_cache: dict[str, object],
    ) -> dict[str, int | bool]:
        service = await self._get_service(context.scope_id, service_cache)
        project_key = context.parent_id or context.target_id
        if not project_key:
            raise ValueError("jira project key is empty")

        from catchup.db.engine import SessionLocal

        with SessionLocal() as db:
            result = await service.incremental_sync(
                db=db,
                project_key=project_key,
                record_id=context.record_id or "",
                event_kind=context.event_kind or "updated",
                since=self._resolve_since(context),
            )

        if int(result.get("errors", 0)) > 0:
            raise SyncInternalError(
                "jira incremental sync failed",
                metadata={"record_key": context.record_key},
            )
        return result
