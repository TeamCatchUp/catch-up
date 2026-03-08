from __future__ import annotations

import logging

from catchup.connectors.github.factory import create_github_ingestion_service
from catchup.sync.common.schemas import SyncEventContext
from catchup.worker.handlers.base_full_sync_handler import BaseFullSyncHandler

logger = logging.getLogger(__name__)


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

        from catchup.db.engine import SessionLocal

        with SessionLocal() as db:
            service = await create_github_ingestion_service(
                db=db,
                installation_id=installation_id,
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

        normalized_target_id = context.target_id.strip()
        if not normalized_target_id:
            raise ValueError("github repository_id(target_id) is empty")

        try:
            repo_id = int(normalized_target_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid github repository_id: {context.target_id}") from exc

        from catchup.db.engine import SessionLocal

        with SessionLocal() as db:
            result = await service.full_sync(
                db=db,
                repo_ids=[repo_id],
                sync_days=sync_days,
            )

        repositories = result.get("repositories", {})
        issues = result.get("issues", {})
        pull_requests = result.get("pull_requests", {})

        synced_count = self._as_int(issues.get("synced", 0)) + self._as_int(
            pull_requests.get("synced", 0)
        )
        error_count = (
            self._as_int(repositories.get("errors", 0))
            + self._as_int(issues.get("errors", 0))
            + self._as_int(pull_requests.get("errors", 0))
        )

        if error_count > 0:
            raise RuntimeError(
                "[GITHUB][FULL SYNC][WORKER] Target sync failed: "
                f"scope_id={context.scope_id}, repository_id={context.target_id}, errors={error_count}"
            )

        logger.info(
            "[GITHUB][FULL SYNC][WORKER] Target synced: scope_id=%s, repository_id=%s, synced=%s, sync_days=%s",
            context.scope_id,
            context.target_id,
            synced_count,
            sync_days,
        )
        return {
            "synced": synced_count,
            "errors": error_count,
            "skipped": False,
        }
