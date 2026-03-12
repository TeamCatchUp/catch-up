from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from catchup.db.atlassian.oauth_repository import get_token_by_cloud_id
from catchup.db.confluence import domain_repository as confluence_entities
from catchup.sync.common.exceptions import SyncRequestError
from catchup.sync.common.protocols import FullSyncTargetResolverProtocol
from catchup.sync.common.schemas import (
    FullSyncResolvedTargets,
    FullSyncDispatchRequest,
)
from catchup.sync.services.full_sync_target_normalizer import (
    build_full_sync_targets,
    index_targets,
    normalize_target_ids,
    resolve_requested_targets,
)

logger = logging.getLogger(__name__)


class ConfluenceFullSyncTargetResolver(FullSyncTargetResolverProtocol):
    async def resolve_full_sync_targets(
        self,
        *,
        db: Session,
        request: FullSyncDispatchRequest,
    ) -> FullSyncResolvedTargets:
        cloud_id = request.scope_id.strip()
        if not cloud_id:
            raise SyncRequestError("scope_id is required")

        token = get_token_by_cloud_id(db, cloud_id)
        if token is None:
            raise SyncRequestError(
                "confluence cloud is not connected",
                metadata={"cloud_id": cloud_id},
            )

        spaces = confluence_entities.get_spaces_by_cloud_id(db, cloud_id)
        requested_space_keys = normalize_target_ids(request.target_ids)
        space_map = index_targets(
            spaces,
            key_getter=lambda space: space.space_key,
        )
        resolved_spaces = resolve_requested_targets(
            requested_space_keys,
            target_index=space_map,
            error_message="requested target_ids contain unknown spaces",
            error_metadata={"cloud_id": cloud_id},
        )

        targets = build_full_sync_targets(
            resolved_spaces,
            target_type="space",
            id_getter=lambda space: space.space_key,
            name_getter=lambda space: space.space_name or space.space_key,
        )

        logger.info(
            "[CONFLUENCE][FULL SYNC][RESOLVER] Targets resolved: cloud_id=%s, requested=%s, resolved=%s",
            cloud_id,
            len(requested_space_keys),
            len(targets),
        )

        return FullSyncResolvedTargets(targets=targets)


_confluence_full_sync_target_resolver = ConfluenceFullSyncTargetResolver()


def get_confluence_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _confluence_full_sync_target_resolver
