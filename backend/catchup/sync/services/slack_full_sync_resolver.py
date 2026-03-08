from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from catchup.connectors.slack.factory import create_slack_ingestion_service
from catchup.sync.common.exceptions import SyncRequestError
from catchup.sync.common.protocols import FullSyncTargetResolverProtocol
from catchup.sync.common.schemas import (
    FullSyncDispatchRequest,
    FullSyncResolvedTargets,
    FullSyncTarget,
)

logger = logging.getLogger(__name__)


def _normalize_requested_channel_ids(target_ids: list[str] | None) -> list[str]:
    if target_ids is None:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in target_ids:
        candidate = (item or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized


class SlackFullSyncTargetResolver(FullSyncTargetResolverProtocol):
    async def resolve_full_sync_targets(
        self,
        *,
        db: Session,
        request: FullSyncDispatchRequest,
        sync_from: str,
    ) -> FullSyncResolvedTargets:
        team_id = request.scope_id.strip()
        if not team_id:
            raise SyncRequestError("scope_id is required")

        service = await create_slack_ingestion_service(db, team_id)
        channels = await service.list_syncable_channels()
        requested_target_ids = _normalize_requested_channel_ids(request.target_ids)

        if request.target_ids is None:
            resolved_channels = channels
            invalid_target_ids: list[str] = []
        else:
            requested_ids = requested_target_ids
            if not requested_ids:
                raise SyncRequestError(
                    "target_ids is empty after normalization",
                    metadata={
                        "team_id": team_id,
                        "requested_target_ids": request.target_ids,
                    },
                )
            requested_id_set = set(requested_ids)

            resolved_channels = [
                channel
                for channel in channels
                if (channel.get("id") or "").strip() in requested_id_set
            ]
            resolved_id_set = {
                (channel.get("id") or "").strip() for channel in resolved_channels
            }
            invalid_target_ids = [
                target_id for target_id in requested_ids if target_id not in resolved_id_set
            ]

            if not resolved_channels:
                raise SyncRequestError(
                    "no syncable channels matched the requested target_ids",
                    metadata={
                        "team_id": team_id,
                        "requested_target_ids": requested_ids,
                    },
                )

        targets = [
            FullSyncTarget(
                target_type="channel",
                target_id=(channel.get("id") or "").strip(),
                target_name=((channel.get("name") or channel.get("id") or "").strip()),
                metadata={
                    "channel_name": (
                        (channel.get("name") or channel.get("id") or "").strip()
                    ),
                    "sync_from": sync_from,
                },
            )
            for channel in resolved_channels
            if (channel.get("id") or "").strip()
        ]

        logger.info(
            "[SLACK][FULL SYNC][RESOLVER] Targets resolved: team_id=%s, resolved=%s, invalid=%s",
            team_id,
            len(targets),
            len(invalid_target_ids),
        )

        return FullSyncResolvedTargets(
            targets=targets,
            invalid_target_ids=invalid_target_ids,
            scope_metadata={"team_id": team_id},
        )


_slack_full_sync_target_resolver = SlackFullSyncTargetResolver()


def get_slack_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _slack_full_sync_target_resolver
