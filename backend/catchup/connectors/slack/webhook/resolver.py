from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CHANNEL_UPSERT_EVENTS = frozenset(
    {"channel_created", "channel_rename", "group_created", "group_rename"}
)
CHANNEL_DELETE_EVENTS = frozenset({"channel_deleted", "group_deleted"})
CHANNEL_ARCHIVE_EVENTS = frozenset(
    {"channel_archive", "channel_unarchive", "group_archive", "group_unarchive"}
)
MEMBER_EVENTS = frozenset({"member_joined_channel", "member_left_channel"})
USER_EVENTS = frozenset({"team_join", "user_change"})


@dataclass(slots=True, frozen=True)
class SlackMetadataResolution:
    action: str | None
    ignored_reason: str | None = None


def resolve_slack_metadata_event(
    *,
    event_type: str,
    event: dict[str, Any],
) -> SlackMetadataResolution:
    if event_type in MEMBER_EVENTS and not _is_supported_channel_membership_event(
        event
    ):
        return SlackMetadataResolution(
            action=None,
            ignored_reason="unsupported_channel",
        )

    if event_type in CHANNEL_UPSERT_EVENTS:
        return SlackMetadataResolution(action="channel_upsert")

    if event_type in CHANNEL_DELETE_EVENTS:
        return SlackMetadataResolution(action="channel_delete")

    if event_type in CHANNEL_ARCHIVE_EVENTS:
        return SlackMetadataResolution(action="channel_archive")

    if event_type in MEMBER_EVENTS:
        return SlackMetadataResolution(action="member")

    if event_type in USER_EVENTS:
        return SlackMetadataResolution(action="user")

    return SlackMetadataResolution(
        action=None,
        ignored_reason="unsupported_event",
    )


def _is_supported_channel_membership_event(event: dict[str, Any]) -> bool:
    channel_type = str(event.get("channel_type") or "").strip().upper()
    if channel_type:
        return channel_type in {"C", "G"}

    channel_id = str(event.get("channel") or "").strip()
    return channel_id.startswith(("C", "G"))
