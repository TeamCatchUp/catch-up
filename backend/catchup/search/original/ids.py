from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from catchup.db.models import SourceType

CHANNEL_TALK_USER_CHAT_ENTITY_TYPE: Final[str] = "user_chat"
SLACK_MESSAGE_ENTITY_TYPE: Final[str] = "message"
CONFLUENCE_PAGE_ENTITY_TYPE: Final[str] = "page"
CONFLUENCE_BLOGPOST_ENTITY_TYPE: Final[str] = "blogpost"


class OriginalDocumentIdError(ValueError):
    """Raised when an original-content document id cannot be routed."""


@dataclass(frozen=True)
class OriginalDocumentRef:
    connector: SourceType
    entity_type: str
    document_id: str
    identifiers: dict[str, str]


def parse_original_document_id(
    *,
    connector: SourceType,
    document_id: str,
) -> OriginalDocumentRef:
    segments = document_id.split(":")
    if len(segments) < 2:
        raise OriginalDocumentIdError("document_id must include connector and entity_type")

    source, entity_type, *rest = segments
    if source != connector.value:
        raise OriginalDocumentIdError("document_id connector does not match request connector")

    if connector == SourceType.CHANNEL_TALK:
        return _parse_channel_talk_document_id(
            entity_type=entity_type,
            rest=rest,
            document_id=document_id,
        )

    if connector == SourceType.SLACK:
        return _parse_slack_document_id(
            entity_type=entity_type,
            rest=rest,
            document_id=document_id,
        )

    if connector == SourceType.CONFLUENCE:
        return _parse_confluence_document_id(
            entity_type=entity_type,
            rest=rest,
            document_id=document_id,
        )

    raise OriginalDocumentIdError(f"unsupported connector: {connector.value}")


def _parse_channel_talk_document_id(
    *,
    entity_type: str,
    rest: list[str],
    document_id: str,
) -> OriginalDocumentRef:
    if entity_type != CHANNEL_TALK_USER_CHAT_ENTITY_TYPE:
        raise OriginalDocumentIdError(f"unsupported channel_talk entity_type: {entity_type}")
    if len(rest) != 2:
        raise OriginalDocumentIdError(
            "channel_talk user_chat document_id must be "
            "channel_talk:user_chat:{channel_id}:{user_chat_id}"
        )

    channel_id, user_chat_id = rest
    if not channel_id or not user_chat_id:
        raise OriginalDocumentIdError("channel_id and user_chat_id are required")

    return OriginalDocumentRef(
        connector=SourceType.CHANNEL_TALK,
        entity_type=CHANNEL_TALK_USER_CHAT_ENTITY_TYPE,
        document_id=document_id,
        identifiers={
            "channel_id": channel_id,
            "user_chat_id": user_chat_id,
        },
    )


def _parse_slack_document_id(
    *,
    entity_type: str,
    rest: list[str],
    document_id: str,
) -> OriginalDocumentRef:
    if entity_type != SLACK_MESSAGE_ENTITY_TYPE:
        raise OriginalDocumentIdError(f"unsupported slack entity_type: {entity_type}")
    if len(rest) != 3:
        raise OriginalDocumentIdError(
            "slack message document_id must be "
            "slack:message:{team_id}:{channel_id}:{ts}"
        )

    team_id, channel_id, ts = rest
    if not team_id or not channel_id or not ts:
        raise OriginalDocumentIdError("team_id, channel_id, and ts are required")

    return OriginalDocumentRef(
        connector=SourceType.SLACK,
        entity_type=SLACK_MESSAGE_ENTITY_TYPE,
        document_id=document_id,
        identifiers={
            "team_id": team_id,
            "channel_id": channel_id,
            "ts": ts,
        },
    )


def _parse_confluence_document_id(
    *,
    entity_type: str,
    rest: list[str],
    document_id: str,
) -> OriginalDocumentRef:
    if entity_type not in {
        CONFLUENCE_PAGE_ENTITY_TYPE,
        CONFLUENCE_BLOGPOST_ENTITY_TYPE,
    }:
        raise OriginalDocumentIdError(f"unsupported confluence entity_type: {entity_type}")
    if len(rest) != 3 or rest[1] != "chunk":
        raise OriginalDocumentIdError(
            "confluence document_id must be "
            "confluence:{page|blogpost}:{content_id}:chunk:{chunk_index}"
        )

    content_id, _, chunk_index = rest
    if not content_id or not chunk_index:
        raise OriginalDocumentIdError("content_id and chunk_index are required")
    if not chunk_index.isdigit():
        raise OriginalDocumentIdError("chunk_index must be a non-negative integer")

    return OriginalDocumentRef(
        connector=SourceType.CONFLUENCE,
        entity_type=entity_type,
        document_id=document_id,
        identifiers={
            "content_id": content_id,
            "chunk_index": chunk_index,
        },
    )
