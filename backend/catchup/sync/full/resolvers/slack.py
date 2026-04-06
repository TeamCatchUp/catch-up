from __future__ import annotations

import asyncio

from fastapi.concurrency import run_in_threadpool
import structlog

from catchup.db.engine import SessionLocal
from catchup.db.slack import domain_repository as slack_entities
from catchup.db.slack import oauth_repository as slack_oauth_repository
from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.common.protocols import FullSyncTargetResolverProtocol
from catchup.sync.common.schemas import (
    FullSyncDispatchRequest,
    FullSyncResolvedTargets,
)
from catchup.sync.full.targets import (
    resolve_full_sync_targets_from_rows,
)

logger = structlog.get_logger(__name__)


class SlackFullSyncTargetResolver(FullSyncTargetResolverProtocol):
    def _load_token_sync(self, team_id: str):
        with SessionLocal() as db:
            return slack_oauth_repository.get_slack_token_by_team_id(db, team_id)

    def _load_channels_sync(self, team_id: str):
        with SessionLocal() as db:
            return slack_entities.get_channels_by_team(db, team_id)

    async def resolve_full_sync_targets(
        self,
        *,
        request: FullSyncDispatchRequest,
    ) -> FullSyncResolvedTargets:
        team_id = request.scope_id.strip()
        if not team_id:
            raise SyncRequestException("scope_id is required")

        token, channels = await asyncio.gather(
            run_in_threadpool(self._load_token_sync, team_id),
            run_in_threadpool(self._load_channels_sync, team_id),
        )
        if token is None:
            raise SyncRequestException(
                "slack team is not connected",
                metadata={"team_id": team_id},
            )

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
            "slack_full_sync_targets_resolved",
            team_id=team_id,
            requested_count=len(requested_target_ids),
            resolved_count=len(resolved_targets.targets),
        )

        return resolved_targets


_slack_full_sync_target_resolver = SlackFullSyncTargetResolver()


def get_slack_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _slack_full_sync_target_resolver
