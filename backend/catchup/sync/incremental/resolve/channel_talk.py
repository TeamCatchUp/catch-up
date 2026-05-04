from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Mapping

from catchup.db.models import SyncConnector
from catchup.sync.incremental.schemas import RecordChange


@dataclass(slots=True, frozen=True)
class ChannelTalkResolveResult:
    changes: list[RecordChange]
    reason: str | None = None


def resolve_channel_talk_user_chat_event(
    *,
    trusted_channel_id: str,
    payload: Mapping[str, Any],
) -> ChannelTalkResolveResult:
    channel_id = trusted_channel_id.strip()
    if not channel_id:
        return ChannelTalkResolveResult(changes=[], reason="missing_channel_id")

    entity = payload.get("entity")
    if not isinstance(entity, Mapping):
        return ChannelTalkResolveResult(changes=[], reason="missing_entity")

    payload_channel_id = _text(entity.get("channelId") or entity.get("channel_id"))
    if payload_channel_id and payload_channel_id != channel_id:
        return ChannelTalkResolveResult(changes=[], reason="channel_mismatch")

    event_type = _text(payload.get("type")).lower()
    if event_type == "message":
        return _resolve_message_event(channel_id=channel_id, entity=entity)
    if event_type in {"userchat", "user_chat"}:
        return _resolve_user_chat_event(channel_id=channel_id, entity=entity)
    return ChannelTalkResolveResult(changes=[], reason="unsupported_type")


def build_channel_talk_document_article_change(
    *,
    channel_id: str,
    space_id: str,
    article_id: str,
    last_event_at: datetime,
) -> RecordChange:
    return RecordChange(
        connector=SyncConnector.CHANNEL_TALK,
        scope_id=channel_id.strip(),
        record_type="document_article",
        record_id=article_id.strip(),
        parent_type="space",
        parent_id=space_id.strip(),
        event_kind="updated",
        last_event_at=_to_utc(last_event_at),
    )


def _resolve_message_event(
    *,
    channel_id: str,
    entity: Mapping[str, Any],
) -> ChannelTalkResolveResult:
    chat_type = _text(entity.get("chatType") or entity.get("chat_type"))
    if chat_type != "userChat":
        return ChannelTalkResolveResult(changes=[], reason="unsupported_chat_type")

    chat_id = _text(entity.get("chatId") or entity.get("chat_id"))
    if not chat_id:
        return ChannelTalkResolveResult(changes=[], reason="missing_chat_id")

    return ChannelTalkResolveResult(
        changes=[
            _build_user_chat_change(
                channel_id=channel_id,
                user_chat_id=chat_id,
                event_kind="updated",
                last_event_at=_read_event_at(entity),
            )
        ]
    )


def _resolve_user_chat_event(
    *,
    channel_id: str,
    entity: Mapping[str, Any],
) -> ChannelTalkResolveResult:
    user_chat_id = _text(
        entity.get("id") or entity.get("chatId") or entity.get("chat_id")
    )
    if not user_chat_id:
        return ChannelTalkResolveResult(changes=[], reason="missing_user_chat_id")

    return ChannelTalkResolveResult(
        changes=[
            _build_user_chat_change(
                channel_id=channel_id,
                user_chat_id=user_chat_id,
                event_kind="updated",
                last_event_at=_read_event_at(entity),
            )
        ]
    )


def _build_user_chat_change(
    *,
    channel_id: str,
    user_chat_id: str,
    event_kind: str,
    last_event_at: datetime,
) -> RecordChange:
    return RecordChange(
        connector=SyncConnector.CHANNEL_TALK,
        scope_id=channel_id,
        record_type="user_chat",
        record_id=user_chat_id,
        parent_type="channel",
        parent_id=channel_id,
        event_kind=event_kind,
        last_event_at=last_event_at,
    )


def _read_event_at(entity: Mapping[str, Any]) -> datetime:
    for key in ("updatedAt", "createdAt", "expiresAt", "updated_at", "created_at"):
        if (value := _parse_channel_talk_timestamp(entity.get(key))) is not None:
            return value
    return datetime.now(timezone.utc)


def _parse_channel_talk_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _to_utc(value)
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    text = _text(value)
    if not text:
        return None
    try:
        numeric = float(text)
    except ValueError:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(
                timezone.utc
            )
        except ValueError:
            return None
    if numeric > 10_000_000_000:
        numeric = numeric / 1000
    return datetime.fromtimestamp(numeric, tz=timezone.utc)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _text(value: Any) -> str:
    return str(value or "").strip()
