from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from catchup.db.atlassian.oauth_repository import get_token_by_cloud_id
from catchup.db.confluence import domain_repository as confluence_entities
from catchup.sync.common.schemas import FullSyncDispatchRequest
from catchup.sync.services.full_sync_orchestrator import (
    FullSyncResolvedTargets,
    FullSyncTarget,
    FullSyncTargetResolverProtocol,
)

logger = logging.getLogger(__name__)


class ConfluenceFullSyncResolverValidationError(Exception):
    """Confluence full sync resolver validation error."""

    def __init__(self, detail: dict[str, object]):
        super().__init__(str(detail))
        self.detail = detail


class ConfluenceFullSyncTargetResolver(FullSyncTargetResolverProtocol):
    async def resolve_full_sync_targets(
        self,
        *,
        db: Session,
        request: FullSyncDispatchRequest,
        sync_from: str,
    ) -> FullSyncResolvedTargets:
        cloud_id = request.scope_id.strip()
        if not cloud_id:
            raise ConfluenceFullSyncResolverValidationError(
                detail={
                    "scope_id": request.scope_id,
                    "message": "scope_id is required",
                }
            )

        token = get_token_by_cloud_id(db, cloud_id)
        if token is None:
            raise ConfluenceFullSyncResolverValidationError(
                detail={
                    "scope_id": request.scope_id,
                    "cloud_id": cloud_id,
                    "message": "confluence cloud is not connected",
                }
            )

        spaces = confluence_entities.get_spaces_by_cloud_id(db, cloud_id)
        if request.target_ids:
            requested_space_keys = [item.strip() for item in request.target_ids if item and item.strip()]
            requested_space_key_set = set(requested_space_keys)

            resolved_spaces = [
                space
                for space in spaces
                if (space.space_key or "").strip() in requested_space_key_set
            ]
            resolved_space_key_set = {(space.space_key or "").strip() for space in resolved_spaces}
            invalid_target_ids = [
                space_key
                for space_key in requested_space_keys
                if space_key not in resolved_space_key_set
            ]
        else:
            resolved_spaces = spaces
            invalid_target_ids = []

        if not resolved_spaces:
            raise ConfluenceFullSyncResolverValidationError(
                detail={
                    "scope_id": request.scope_id,
                    "cloud_id": cloud_id,
                    "message": "no syncable spaces found",
                    "requested_target_ids": request.target_ids or [],
                }
            )

        targets = [
            FullSyncTarget(
                target_type="space",
                target_id=(space.space_key or "").strip(),
                target_name=(space.space_name or space.space_key or "").strip(),
                metadata={
                    "space_id": str(space.space_id),
                    "space_key": (space.space_key or "").strip(),
                    "space_name": (space.space_name or space.space_key or "").strip(),
                    "sync_from": sync_from,
                },
            )
            for space in resolved_spaces
            if (space.space_key or "").strip()
        ]

        logger.info(
            "[CONFLUENCE][FULL SYNC][RESOLVER] Targets resolved: cloud_id=%s, resolved=%s, invalid=%s",
            cloud_id,
            len(targets),
            len(invalid_target_ids),
        )

        return FullSyncResolvedTargets(
            targets=targets,
            invalid_target_ids=invalid_target_ids,
            scope_metadata={"cloud_id": cloud_id},
        )


_confluence_full_sync_target_resolver = ConfluenceFullSyncTargetResolver()


def get_confluence_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _confluence_full_sync_target_resolver
