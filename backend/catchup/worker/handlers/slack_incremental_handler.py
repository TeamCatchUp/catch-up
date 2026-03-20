from __future__ import annotations

from catchup.connectors.slack.factory import create_slack_ingestion_service
from catchup.sync.audit import SyncAuditContext
from catchup.sync.common.exceptions import SyncInternalError
from catchup.sync.common.schemas import IncrementalSyncContext, TargetSyncResult
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
        # 리팩토링: incremental path도 service 생성 시 외부 session을 넘기지 않는다.
        service = await create_slack_ingestion_service(team_id)

        cache[cache_key] = service
        return service

    async def handle(
        self,
        *,
        context: IncrementalSyncContext,
        service_cache: dict[str, object],
    ) -> TargetSyncResult:
        service = await self._get_service(context.scope_id, service_cache)
        channel_id = context.parent_id or context.target_id
        if not channel_id:
            raise ValueError("slack channel id is empty")

        sync_from = None
        since = self._resolve_since(context)
        sync_from = f"{since.timestamp():.6f}"
        result = await service.incremental_sync(
            channel_id=channel_id,
            record_id=context.record_id or "",
            event_kind=context.event_kind or "updated",
            sync_from=sync_from,
            audit_context=SyncAuditContext(
                connector=context.connector,
                scope_id=context.scope_id,
                target_id=context.target_id,
                job_id=context.job_id,
                task_id=context.event_id,
            ),
        )

        if result.error_count > 0:
            raise SyncInternalError(
                "slack incremental sync failed",
                metadata={"record_key": context.record_key},
            )
        return result
