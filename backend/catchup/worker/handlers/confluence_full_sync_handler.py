from __future__ import annotations

import logging

from catchup.connectors.confluence.factory import create_confluence_ingestion_service
from catchup.sync.common.schemas import SyncEventContext
from catchup.worker.handlers.base_full_sync_handler import BaseFullSyncHandler

logger = logging.getLogger(__name__)


class ConfluenceFullSyncHandler(BaseFullSyncHandler):
    connector = "confluence"

    async def _get_service(self, scope_id: str, cache: dict[str, object]):
        cloud_id = scope_id.strip()
        cache_key = self._cache_key(cloud_id)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        if not cloud_id:
            raise ValueError("confluence cloud_id(scope_id) is empty")

        from catchup.db.engine import SessionLocal

        with SessionLocal() as db:
            service = await create_confluence_ingestion_service(
                db=db,
                cloud_id=cloud_id,
            )
        cache[cache_key] = service
        return service

    async def handle(
        self,
        *,
        context: SyncEventContext,
        service_cache: dict[str, object],
    ) -> dict[str, int | bool]:
        service = await self._get_service(context.scope_id, service_cache)
        sync_days = self._resolve_sync_days(context)

        space_key = context.target_id.strip()
        if not space_key:
            raise ValueError("confluence space_key(target_id) is empty")

        from catchup.db.engine import SessionLocal

        with SessionLocal() as db:
            result = await service.full_sync(
                db=db,
                space_keys=[space_key],
                sync_days=sync_days,
            )

        pages = result.get("pages", {})
        blogposts = result.get("blogposts", {})

        synced_count = self._as_int(pages.get("synced", 0)) + self._as_int(
            blogposts.get("synced", 0)
        )
        error_count = self._as_int(pages.get("errors", 0)) + self._as_int(
            blogposts.get("errors", 0)
        )

        if error_count > 0:
            raise RuntimeError(
                "[CONFLUENCE][FULL SYNC][WORKER] Target sync failed: "
                f"scope_id={context.scope_id}, space_key={space_key}, errors={error_count}"
            )

        logger.info(
            "[CONFLUENCE][FULL SYNC][WORKER] Target synced: scope_id=%s, space_key=%s, synced=%s, sync_days=%s",
            context.scope_id,
            space_key,
            synced_count,
            sync_days,
        )
        return {
            "synced": synced_count,
            "errors": error_count,
            "skipped": False,
        }
