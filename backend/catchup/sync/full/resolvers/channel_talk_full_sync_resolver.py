from __future__ import annotations

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.connectors.channel_talk.full_sync_helper import (
    CHANNEL_TALK_FULL_SYNC_TARGET_ID,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    load_channel_talk_connection,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    require_channel_talk_channel_id,
)
from catchup.connectors.channel_talk.full_sync_target_contract import (
    CHANNEL_TALK_BOOTSTRAP_DISPLAY_NAME,
)
from catchup.connectors.channel_talk.full_sync_target_contract import (
    build_channel_talk_bootstrap_metadata,
)
from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.common.protocols import FullSyncTargetResolverProtocol
from catchup.sync.common.schemas import FullSyncDispatchRequest
from catchup.sync.common.schemas import FullSyncResolvedTargets
from catchup.sync.full.targets import resolve_full_sync_targets_from_rows

logger = structlog.get_logger(__name__)


class ChannelTalkFullSyncTargetResolver(FullSyncTargetResolverProtocol):
    async def resolve_full_sync_targets(
        self,
        *,
        request: FullSyncDispatchRequest,
    ) -> FullSyncResolvedTargets:
        try:
            channel_id = require_channel_talk_channel_id(
                request.scope_id,
                empty_message="scope_id is required",
            )
        except ValueError as exc:
            raise SyncRequestException(str(exc)) from exc

        connection = await run_in_threadpool(load_channel_talk_connection)
        if connection is None:
            raise SyncRequestException(
                "channel_talk is not connected",
                metadata={"scope_id": channel_id},
            )
        if connection.channel_id != channel_id:
            raise SyncRequestException(
                "Stored Channel Talk credentials do not match the requested channel",
                metadata={
                    "scope_id": channel_id,
                    "channel_id": connection.channel_id,
                },
            )

        requested_target_ids, resolved_targets = resolve_full_sync_targets_from_rows(
            request_target_ids=request.target_ids,
            rows=[CHANNEL_TALK_FULL_SYNC_TARGET_ID],
            target_type="resource",
            key_getter=lambda target_id: target_id,
            name_getter=lambda _: CHANNEL_TALK_BOOTSTRAP_DISPLAY_NAME,
            error_message="requested target_ids contain unknown channel_talk targets",
            error_metadata={"channel_id": channel_id},
            metadata_getter=lambda _: build_channel_talk_bootstrap_metadata(channel_id),
            log_context={
                "connector": "channel_talk",
                "channel_id": channel_id,
                "target_type": "resource",
            },
        )

        logger.info(
            "channel_talk_full_sync_targets_resolved",
            channel_id=channel_id,
            requested_count=len(requested_target_ids),
            resolved_count=len(resolved_targets.targets),
        )
        return resolved_targets


_channel_talk_full_sync_target_resolver = ChannelTalkFullSyncTargetResolver()


def get_channel_talk_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _channel_talk_full_sync_target_resolver
