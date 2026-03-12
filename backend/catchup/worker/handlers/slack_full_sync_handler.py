from __future__ import annotations

from catchup.connectors.slack.factory import create_slack_ingestion_service
from catchup.sync.common.schemas import FullSyncContext, TargetSyncResult
from catchup.worker.handlers.base_full_sync_handler import BaseFullSyncHandler


class SlackFullSyncHandler(BaseFullSyncHandler):
    connector = "slack"

    async def _get_service(self, scope_id: str, cache: dict[str, object]):
        normalized_scope_id = scope_id.strip()
        if not normalized_scope_id:
            raise ValueError("slack team_id(scope_id) is empty")

        cache_key = self._cache_key(normalized_scope_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        # 순환 import 방지를 위해 런타임 시점에 SessionLocal을 로드한다.
        from catchup.db.engine import SessionLocal

        with SessionLocal() as db:
            service = await create_slack_ingestion_service(db, normalized_scope_id)

        cache[cache_key] = service
        return service

    async def handle(
        self,
        *,
        context: FullSyncContext,
        service_cache: dict[str, object],
    ) -> TargetSyncResult:
        service = await self._get_service(context.scope_id, service_cache)

        from catchup.db.engine import SessionLocal

        with SessionLocal() as db:
            result = await service.sync_channel_messages(
                channel_id=context.target_id,
                channel_name=context.target_name,
                sync_from=context.sync_from,
                db=db,
                skip_delete=True,
            )

        return TargetSyncResult.from_mapping(result)
