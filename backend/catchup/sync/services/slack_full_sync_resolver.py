from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from catchup.connectors.slack.factory import create_slack_ingestion_service
from catchup.sync.common.protocols import FullSyncTargetResolverProtocol
from catchup.sync.common.schemas import (
    FullSyncResolvedTargets,
    FullSyncDispatchRequest,
    FullSyncTarget,
)

logger = logging.getLogger(__name__)


class SlackFullSyncResolverValidationError(Exception):
    """Slack full sync resolver validation error."""

    def __init__(self, detail: dict[str, object]):
        super().__init__(str(detail))
        self.detail = detail


class SlackFullSyncTargetResolver(FullSyncTargetResolverProtocol):
    async def resolve_full_sync_targets(
        self,
        *,
        db: Session,
        request: FullSyncDispatchRequest,
        sync_from: str,
    ) -> FullSyncResolvedTargets:
        team_id = request.scope_id
        requested_target_ids = request.target_ids

        service = await create_slack_ingestion_service(db, team_id)
        channels = await service.list_syncable_channels()

        if requested_target_ids is None:
            resolved_channels = channels
            invalid_target_ids: list[str] = []
        else:
            requested_ids = [item.strip() for item in requested_target_ids if item and item.strip()]
            requested_id_set = set(requested_ids)

            resolved_channels = [
                channel
                for channel in channels
                if (channel.get("id") or "").strip() in requested_id_set
            ]
            resolved_id_set = {(channel.get("id") or "").strip() for channel in resolved_channels}
            invalid_target_ids = [
                target_id for target_id in requested_ids if target_id not in resolved_id_set
            ]

            if not resolved_channels:
                raise SlackFullSyncResolverValidationError(
                    detail={
                        "team_id": team_id,
                        "message": "no syncable channels matched the requested target_ids",
                        "requested_target_ids": requested_ids,
                    }
                )

        targets = [
            FullSyncTarget(
                target_type="channel",
                target_id=(channel.get("id") or "").strip(),
                target_name=((channel.get("name") or channel.get("id") or "").strip()),
                metadata={
                    "channel_name": ((channel.get("name") or channel.get("id") or "").strip()),
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
