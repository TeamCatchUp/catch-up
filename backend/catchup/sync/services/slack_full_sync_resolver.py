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
)
from catchup.sync.services.full_sync_target_normalizer import (
    resolve_full_sync_targets_from_rows,
)

logger = logging.getLogger(__name__)


class SlackFullSyncTargetResolver(FullSyncTargetResolverProtocol):
    async def resolve_full_sync_targets(
        self,
        *,
        db: Session,
        request: FullSyncDispatchRequest,
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
        requested_target_ids, resolved_targets = resolve_full_sync_targets_from_rows(
            request_target_ids=request.target_ids,
            rows=channels,
            target_type="channel",
            key_getter=lambda channel: channel.id,
            name_getter=lambda channel: channel.name or channel.id,
            error_message="requested target_ids contain unknown channels",
            error_metadata={"team_id": team_id},
            log_context={
                "connector": "slack",
                "team_id": team_id,
                "target_type": "channel",
            },
        )

        logger.info(
            "[SLACK][FULL SYNC][RESOLVER] Targets resolved: team_id=%s, requested=%s, resolved=%s",
            team_id,
            len(requested_target_ids),
            len(resolved_targets.targets),
        )

        return resolved_targets


_slack_full_sync_target_resolver = SlackFullSyncTargetResolver()


def get_slack_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _slack_full_sync_target_resolver
