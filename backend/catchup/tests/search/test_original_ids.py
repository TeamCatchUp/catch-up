import pytest
from pydantic import ValidationError

from catchup.db.models import SourceType
from catchup.search.original.ids import OriginalDocumentIdError
from catchup.search.original.ids import parse_original_document_id
from catchup.server.search.schemas import OriginalContentRequest


def test_parse_channel_talk_user_chat_document_id() -> None:
    ref = parse_original_document_id(
        connector=SourceType.CHANNEL_TALK,
        document_id="channel_talk:user_chat:channel-123:chat-456",
    )

    assert ref.connector == SourceType.CHANNEL_TALK
    assert ref.entity_type == "user_chat"
    assert ref.document_id == "channel_talk:user_chat:channel-123:chat-456"
    assert ref.identifiers == {
        "channel_id": "channel-123",
        "user_chat_id": "chat-456",
    }


def test_parse_rejects_connector_mismatch() -> None:
    with pytest.raises(OriginalDocumentIdError, match="connector does not match"):
        parse_original_document_id(
            connector=SourceType.CHANNEL_TALK,
            document_id="slack:message:T1:C1:123.456",
        )


def test_parse_rejects_unsupported_channel_talk_entity_type() -> None:
    with pytest.raises(OriginalDocumentIdError, match="unsupported channel_talk entity_type"):
        parse_original_document_id(
            connector=SourceType.CHANNEL_TALK,
            document_id="channel_talk:document_article:channel-123:article-456",
        )


@pytest.mark.parametrize(
    "document_id",
    [
        "",
        "channel_talk",
        "channel_talk:user_chat:channel-123",
        "channel_talk:user_chat::chat-456",
        "channel_talk:user_chat:channel-123:",
    ],
)
def test_parse_rejects_malformed_channel_talk_user_chat_document_id(
    document_id: str,
) -> None:
    with pytest.raises(OriginalDocumentIdError):
        parse_original_document_id(
            connector=SourceType.CHANNEL_TALK,
            document_id=document_id,
        )


def test_original_search_request_accepts_connector_enum_value() -> None:
    request = OriginalContentRequest(
        connector="channel_talk",
        document_id="channel_talk:user_chat:channel-123:chat-456",
        next_cursor="cursor-1",
    )

    assert request.connector == SourceType.CHANNEL_TALK
    assert request.document_id == "channel_talk:user_chat:channel-123:chat-456"
    assert request.next_cursor == "cursor-1"


def test_original_search_request_rejects_unknown_connector() -> None:
    with pytest.raises(ValidationError):
        OriginalContentRequest(
            connector="unknown",
            document_id="unknown:thing:id",
        )
