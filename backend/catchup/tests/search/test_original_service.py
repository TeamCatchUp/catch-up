from datetime import datetime
from datetime import timezone

import pytest

from catchup.db.models import SourceType
from catchup.search.original.ids import OriginalDocumentRef
from catchup.search.original.registry import OriginalResolverNotFoundError
from catchup.search.original.registry import OriginalResolverRegistry
from catchup.search.original.schemas import OriginalSearchRequest
from catchup.search.original.schemas import OriginalSearchResponse
from catchup.search.original.service import OriginalSearchService


class _RecordingResolver:
    def __init__(self) -> None:
        self.calls = []

    async def resolve(self, *, request, ref, db):
        self.calls.append((request, ref, db))
        return OriginalSearchResponse(
            connector=ref.connector,
            entity_type=ref.entity_type,
            document_id=ref.document_id,
            title="Original",
            items=[],
            metadata={"channel_id": ref.identifiers["channel_id"]},
            next_cursor=None,
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
    request = OriginalSearchRequest(
        connector=SourceType.CHANNEL_TALK,
        document_id="channel_talk:user_chat:channel-123:chat-456",
    )
    db = object()

    response = await service.get_original(request=request, db=db)

    assert response.connector == SourceType.CHANNEL_TALK
    assert response.entity_type == "user_chat"
    assert response.metadata == {"channel_id": "channel-123"}
    assert len(resolver.calls) == 1
    _, ref, passed_db = resolver.calls[0]
    assert isinstance(ref, OriginalDocumentRef)
    assert ref.identifiers["user_chat_id"] == "chat-456"
    assert passed_db is db


@pytest.mark.asyncio
async def test_service_raises_when_no_resolver_is_registered() -> None:
    service = OriginalSearchService(registry=OriginalResolverRegistry())
    request = OriginalSearchRequest(
        connector=SourceType.CHANNEL_TALK,
        document_id="channel_talk:user_chat:channel-123:chat-456",
    )

    with pytest.raises(OriginalResolverNotFoundError):
        await service.get_original(request=request, db=object())
