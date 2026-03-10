from __future__ import annotations

from catchup.connectors.slack.factory import create_slack_ingestion_service
from catchup.worker.handlers.base_incremental_handler import BaseIncrementalHandler


class SlackIncrementalHandler(BaseIncrementalHandler):
    connector = "slack"

    async def _get_service(self, scope_id: str, cache: dict[str, object]):
        team_id = scope_id.strip()
        if not team_id:
            raise ValueError("slack team_id(scope_id) is empty")

        cache_key = self._cache_key(team_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        from catchup.db.engine import SessionLocal

        with SessionLocal() as db:
            service = await create_slack_ingestion_service(db, team_id)

        cache[cache_key] = service
        return service

    async def handle(
        self,
        *,
        context,
        service_cache: dict[str, object],
    ) -> dict[str, int | bool]:
        service = await self._get_service(context.scope_id, service_cache)
        channel_id = context.parent_id or context.target_id
        if not channel_id:
            raise ValueError("slack channel id is empty")

        sync_from = None
        since = self._resolve_since(context)
        sync_from = f"{since.timestamp():.6f}"

        from catchup.db.engine import SessionLocal

        with SessionLocal() as db:
            result = await service.incremental_sync(
                db=db,
                channel_id=channel_id,
                record_id=context.record_id or "",
                event_kind=context.event_kind or "updated",
                sync_from=sync_from,
            )

        if int(result.get("errors", 0)) > 0:
            raise RuntimeError(f"slack incremental sync failed: record_key={context.record_key}")
        return result
