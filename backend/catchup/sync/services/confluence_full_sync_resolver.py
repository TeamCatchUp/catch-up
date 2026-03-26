from __future__ import annotations

import asyncio
import logging

from fastapi.concurrency import run_in_threadpool

from catchup.db.atlassian.oauth_repository import get_token_by_cloud_id
from catchup.db.confluence import domain_repository as confluence_entities
from catchup.db.engine import SessionLocal
from catchup.sync.common.exceptions import SyncRequestError
from catchup.sync.common.protocols import FullSyncTargetResolverProtocol
from catchup.sync.common.schemas import (
    FullSyncResolvedTargets,
    FullSyncDispatchRequest,
)
from catchup.sync.services.full_sync_target_normalizer import (
    resolve_full_sync_targets_from_rows,
)

logger = logging.getLogger(__name__)


class ConfluenceFullSyncTargetResolver(FullSyncTargetResolverProtocol):
    def _load_token_sync(self, cloud_id: str):
        with SessionLocal() as db:
            return get_token_by_cloud_id(db, cloud_id)

    def _load_spaces_sync(self, cloud_id: str):
        with SessionLocal() as db:
            return confluence_entities.get_spaces_by_cloud_id(db, cloud_id)

    async def resolve_full_sync_targets(
        self,
        *,
        request: FullSyncDispatchRequest,
    ) -> FullSyncResolvedTargets:
        cloud_id = request.scope_id.strip()
        if not cloud_id:
            raise SyncRequestError("scope_id is required")

        token, spaces = await asyncio.gather(
            run_in_threadpool(self._load_token_sync, cloud_id),
            run_in_threadpool(self._load_spaces_sync, cloud_id),
        )
        if token is None:
            raise SyncRequestError(
                "confluence cloud is not connected",
                metadata={"cloud_id": cloud_id},
            )

        requested_space_keys, resolved_targets = resolve_full_sync_targets_from_rows(
            request_target_ids=request.target_ids,
            rows=spaces,
            target_type="space",
            key_getter=lambda space: space.space_key,
            name_getter=lambda space: space.space_name or space.space_key,
            error_message="requested target_ids contain unknown spaces",
            error_metadata={"cloud_id": cloud_id},
            log_context={
                "connector": "confluence",
                "cloud_id": cloud_id,
                "target_type": "space",
            },
        )

        logger.info(
            "[CONFLUENCE][FULL SYNC][RESOLVER] Targets resolved: cloud_id=%s, requested=%s, resolved=%s",
            cloud_id,
            len(requested_space_keys),
            len(resolved_targets.targets),
        )

        return resolved_targets


_confluence_full_sync_target_resolver = ConfluenceFullSyncTargetResolver()


def get_confluence_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _confluence_full_sync_target_resolver
