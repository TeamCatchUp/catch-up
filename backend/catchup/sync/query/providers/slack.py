from __future__ import annotations

from catchup.connectors.slack.factory import create_slack_metadata_service
from catchup.db.models import SyncConnector
from catchup.sync.query.providers.common import build_targets_result
from catchup.sync.query.types import SyncTargetResult
from catchup.sync.query.types import SyncTargetsResult


async def list_slack_targets(*, scope_id: str) -> SyncTargetsResult:
    metadata_service = await create_slack_metadata_service(team_id=scope_id)
    channels = await metadata_service.sync_target_channels()
    channels = sorted(channels, key=lambda channel: channel.name)

    targets = [
        SyncTargetResult(
            target_id=channel.id,
            display_name=channel.name or channel.id,
            target_type="channel",
            is_accessible=bool(channel.is_member),
            metadata={
                "channel_kind": str(channel.channel_type),
                "is_private": bool(channel.is_private),
                "is_member": bool(channel.is_member),
                "member_count": int(channel.member_count),
            },
        )
        for channel in channels
    ]
    return build_targets_result(
        connector=SyncConnector.SLACK,
        scope_id=scope_id,
        targets=targets,
    )
