from datetime import datetime
from datetime import timezone

import pytest
from pydantic import ValidationError

from catchup.db.models import SourceType
from catchup.search.original.ids import OriginalDocumentRef
from catchup.search.original.registry import OriginalResolverNotFoundError
from catchup.search.original.registry import OriginalResolverRegistry
from catchup.search.original.schemas import OriginalContent
from catchup.search.original.schemas import OriginalItem
from catchup.search.original.schemas.channel_talk import ChannelTalkOriginalAuthor
from catchup.search.original.schemas.channel_talk import (
    ChannelTalkUserChatOriginalContent,
)
from catchup.search.original.schemas.channel_talk import ChannelTalkUserChatOriginalItem
from catchup.search.original.service import OriginalSearchService
from catchup.server.search.schemas import OriginalContentRequest
from catchup.server.search.schemas import OriginalContentResponse
from catchup.server.search.schemas import OriginalFileUrlRequest
from catchup.server.search.schemas import OriginalFileUrlResponse


class _RecordingResolver:
    def __init__(self) -> None:
        self.calls = []

    async def resolve(self, *, request, ref, db):
        self.calls.append((request, ref, db))
        return OriginalContentResponse(
            connector=ref.connector,
            entity_type=ref.entity_type,
            document_id=ref.document_id,
            title="Original",
            items=[],
            metadata={"channel_id": ref.identifiers["channel_id"]},
            next_cursor=None,
            fetched_at=datetime(2026, 5, 22, tzinfo=timezone.utc),
        )

    async def resolve_file_url(self, *, request, ref, db):
        self.calls.append((request, ref, db))
        return OriginalFileUrlResponse(
            connector=ref.connector,
            entity_type=ref.entity_type,
            document_id=ref.document_id,
            file_key=request.file_key,
            url="https://signed.example/file",
            fetched_at=datetime(2026, 5, 22, tzinfo=timezone.utc),
        )


def test_registry_returns_registered_connector_entity_resolver() -> None:
    registry = OriginalResolverRegistry()
    resolver = _RecordingResolver()

    registry.register(
        connector=SourceType.CHANNEL_TALK,
        entity_type="user_chat",
        resolver=resolver,
    )

    assert registry.get(
        connector=SourceType.CHANNEL_TALK,
        entity_type="user_chat",
    ) is resolver


def test_original_item_requires_contents_and_rejects_metadata() -> None:
    with pytest.raises(ValidationError):
        OriginalItem(id="msg-1", type="message")

    with pytest.raises(ValidationError):
        OriginalItem(
            id="msg-1",
            type="message",
            contents=[
                OriginalContent(
                    content_type="text",
                    payload={"text": "hello"},
                )
            ],
            metadata={},
        )


def test_original_content_is_connector_neutral_payload_envelope() -> None:
    content = OriginalContent(
        content_type="text",
        payload={"text": "hello"},
    )
    assert content.content_type == "text"
    assert content.payload == {"text": "hello"}

    assert OriginalContent(
        content_type="custom_connector_card",
        payload={"title": "Future connector content"},
    ).content_type == "custom_connector_card"

    with pytest.raises(ValidationError):
        OriginalContent(content_type="text", text="hello")


def test_channel_talk_content_restricts_content_type_values() -> None:
    assert ChannelTalkUserChatOriginalContent(
        content_type="file",
        payload={"files": []},
    ).content_type == "file"

    with pytest.raises(ValidationError):
        ChannelTalkUserChatOriginalContent(
            content_type="custom_connector_card",
            payload={},
        )


def test_channel_talk_item_fields_restrict_known_string_values() -> None:
    author = ChannelTalkOriginalAuthor(type="customer")
    assert author.type == "customer"

    item = ChannelTalkUserChatOriginalItem(
        id="msg-1",
        type="message",
        visibility="public",
        author=author,
        contents=[
            ChannelTalkUserChatOriginalContent(
                content_type="text",
                payload={"text": "hello"},
            )
        ],
    )
    assert item.type == "message"
    assert item.visibility == "public"

    with pytest.raises(ValidationError):
        ChannelTalkOriginalAuthor(type="bot")

    with pytest.raises(ValidationError):
        ChannelTalkUserChatOriginalItem(
            id="msg-1",
            type="log",
            visibility="public",
            contents=[],
        )

    with pytest.raises(ValidationError):
        ChannelTalkUserChatOriginalItem(
            id="msg-1",
            type="message",
            visibility="private",
            contents=[],
        )


def test_registry_rejects_unsupported_connector_entity_route() -> None:
    registry = OriginalResolverRegistry()

    with pytest.raises(OriginalResolverNotFoundError, match="channel_talk:user_chat"):
        registry.get(
            connector=SourceType.CHANNEL_TALK,
            entity_type="user_chat",
        )


@pytest.mark.asyncio
async def test_service_parses_document_id_and_delegates_to_registered_resolver() -> None:
    registry = OriginalResolverRegistry()
    resolver = _RecordingResolver()
    registry.register(
        connector=SourceType.CHANNEL_TALK,
        entity_type="user_chat",
        resolver=resolver,
    )
    service = OriginalSearchService(registry=registry)
    request = OriginalContentRequest(
        connector=SourceType.CHANNEL_TALK,
        document_id="channel_talk:user_chat:channel-123:chat-456",
    )

    response = await service.get_original(request=request)

    assert response.connector == SourceType.CHANNEL_TALK
    assert response.entity_type == "user_chat"
    assert response.metadata == {"channel_id": "channel-123"}
    assert len(resolver.calls) == 1
    _, ref, passed_db = resolver.calls[0]
    assert isinstance(ref, OriginalDocumentRef)
    assert ref.identifiers["user_chat_id"] == "chat-456"
    assert passed_db is None


@pytest.mark.asyncio
async def test_service_parses_document_id_and_delegates_file_url_request() -> None:
    registry = OriginalResolverRegistry()
    resolver = _RecordingResolver()
    registry.register(
        connector=SourceType.CHANNEL_TALK,
        entity_type="user_chat",
        resolver=resolver,
    )
    service = OriginalSearchService(registry=registry)
    request = OriginalFileUrlRequest(
        connector=SourceType.CHANNEL_TALK,
        document_id="channel_talk:user_chat:channel-123:chat-456",
        file_key="file-1",
    )

    response = await service.get_original_file_url(request=request)

    assert response.connector == SourceType.CHANNEL_TALK
    assert response.entity_type == "user_chat"
    assert response.file_key == "file-1"
    assert response.url == "https://signed.example/file"
    assert response.expires_in_seconds == 900
    assert len(resolver.calls) == 1
    _, ref, passed_db = resolver.calls[0]
    assert isinstance(ref, OriginalDocumentRef)
    assert ref.identifiers["channel_id"] == "channel-123"
    assert ref.identifiers["user_chat_id"] == "chat-456"
    assert passed_db is None


@pytest.mark.asyncio
async def test_service_raises_when_no_resolver_is_registered() -> None:
    service = OriginalSearchService(registry=OriginalResolverRegistry())
    request = OriginalContentRequest(
        connector=SourceType.CHANNEL_TALK,
        document_id="channel_talk:user_chat:channel-123:chat-456",
    )

    with pytest.raises(OriginalResolverNotFoundError):
        await service.get_original(request=request, db=object())
