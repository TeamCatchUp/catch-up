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
    FullSyncTarget,
)

logger = logging.getLogger(__name__)


def _normalize_requested_space_keys(target_ids: list[str] | None) -> list[str]:
    if target_ids is None:
        raise SyncRequestError("target_ids is required")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in target_ids:
        candidate = (item or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)

    if not normalized:
        raise SyncRequestError(
            "target_ids is empty after normalization",
            metadata={"requested_target_ids": target_ids},
        )

    return normalized


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
            raise SyncRequestError("scope_id is required")

        token = get_token_by_cloud_id(db, cloud_id)
        if token is None:
            raise SyncRequestError(
                "confluence cloud is not connected",
                metadata={"cloud_id": cloud_id},
            )

        spaces = confluence_entities.get_spaces_by_cloud_id(db, cloud_id)
        requested_space_keys = _normalize_requested_space_keys(request.target_ids)
        space_map = {
            (space.space_key or "").strip(): space
            for space in spaces
            if (space.space_key or "").strip()
        }
        invalid_target_ids = [
            space_key
            for space_key in requested_space_keys
            if space_key not in space_map
        ]
        if invalid_target_ids:
            raise SyncRequestError(
                "requested target_ids contain unknown spaces",
                metadata={
                    "cloud_id": cloud_id,
                    "requested_target_ids": requested_space_keys,
                    "invalid_target_ids": invalid_target_ids,
                },
            )

        resolved_spaces = [
            space_map[space_key]
            for space_key in requested_space_keys
        ]

        targets = [
            FullSyncTarget(
                target_type="space",
                target_id=(space.space_key or "").strip(),
                target_name=(space.space_name or space.space_key or "").strip(),
                metadata={},
            )
            for space in resolved_spaces
            if (space.space_key or "").strip()
        ]

        logger.info(
            "[CONFLUENCE][FULL SYNC][RESOLVER] Targets resolved: cloud_id=%s, requested=%s, resolved=%s",
            cloud_id,
            len(requested_space_keys),
            len(targets),
        )

        return FullSyncResolvedTargets(
            targets=targets,
            invalid_target_ids=[],
        )


_confluence_full_sync_target_resolver = ConfluenceFullSyncTargetResolver()


def get_confluence_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _confluence_full_sync_target_resolver
