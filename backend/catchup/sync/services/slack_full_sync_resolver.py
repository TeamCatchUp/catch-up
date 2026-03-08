from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from catchup.db.slack import domain_repository as slack_entities
from catchup.db.slack import oauth_repository as slack_oauth_repository
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

        token = slack_oauth_repository.get_slack_token_by_team_id(db, team_id)
        if token is None:
            raise SyncRequestError(
                "slack team is not connected",
                metadata={"team_id": team_id},
            )

        channels = slack_entities.get_channels_by_team(db, team_id)
        requested_target_ids = _normalize_requested_channel_ids(request.target_ids)
        channel_map = {
            (channel.id or "").strip(): channel
            for channel in channels
            if (channel.id or "").strip()
        }
        invalid_target_ids = [
            channel_id
            for channel_id in requested_target_ids
            if channel_id not in channel_map
        ]
        if invalid_target_ids:
            raise SyncRequestError(
                "requested target_ids contain unknown channels",
                metadata={
                    "team_id": team_id,
                    "requested_target_ids": requested_target_ids,
                    "invalid_target_ids": invalid_target_ids,
                },
            )

        resolved_channels = [
            channel_map[channel_id]
            for channel_id in requested_target_ids
        ]

        targets = [
            FullSyncTarget(
                target_type="channel",
                target_id=(channel.id or "").strip(),
                target_name=((channel.name or channel.id or "").strip()),
                metadata={
                    "channel_name": ((channel.name or channel.id or "").strip()),
                    "sync_from": sync_from,
                },
            )
            for channel in resolved_channels
            if (channel.id or "").strip()
        ]

        logger.info(
            "[SLACK][FULL SYNC][RESOLVER] Targets resolved: team_id=%s, requested=%s, resolved=%s",
            team_id,
            len(requested_target_ids),
            len(targets),
        )

        return FullSyncResolvedTargets(
            targets=targets,
            invalid_target_ids=[],
            scope_metadata={"team_id": team_id},
        )


_slack_full_sync_target_resolver = SlackFullSyncTargetResolver()


def get_slack_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _slack_full_sync_target_resolver
