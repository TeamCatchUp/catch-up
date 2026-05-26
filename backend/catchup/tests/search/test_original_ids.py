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


def test_parse_slack_message_document_id() -> None:
    ref = parse_original_document_id(
        connector=SourceType.SLACK,
        document_id="slack:message:T1:C1:1716400000.000100",
    )

    assert ref.connector == SourceType.SLACK
    assert ref.entity_type == "message"
    assert ref.document_id == "slack:message:T1:C1:1716400000.000100"
    assert ref.identifiers == {
        "team_id": "T1",
        "channel_id": "C1",
        "ts": "1716400000.000100",
    }


def test_parse_confluence_page_chunk_document_id() -> None:
    ref = parse_original_document_id(
        connector=SourceType.CONFLUENCE,
        document_id="confluence:page:123:chunk:4",
    )

    assert ref.connector == SourceType.CONFLUENCE
    assert ref.entity_type == "page"
    assert ref.document_id == "confluence:page:123:chunk:4"
    assert ref.identifiers == {
        "content_id": "123",
        "chunk_index": "4",
    }


def test_parse_confluence_blogpost_chunk_document_id() -> None:
    ref = parse_original_document_id(
        connector=SourceType.CONFLUENCE,
        document_id="confluence:blogpost:456:chunk:0",
    )

    assert ref.connector == SourceType.CONFLUENCE
    assert ref.entity_type == "blogpost"
    assert ref.identifiers == {
        "content_id": "456",
        "chunk_index": "0",
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


def test_parse_rejects_unsupported_slack_entity_type() -> None:
    with pytest.raises(OriginalDocumentIdError, match="unsupported slack entity_type"):
        parse_original_document_id(
            connector=SourceType.SLACK,
            document_id="slack:file:T1:C1:1716400000.000100",
        )


def test_parse_rejects_unsupported_confluence_entity_type() -> None:
    with pytest.raises(OriginalDocumentIdError, match="unsupported confluence entity_type"):
        parse_original_document_id(
            connector=SourceType.CONFLUENCE,
            document_id="confluence:comment:123:chunk:0",
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


@pytest.mark.parametrize(
    "document_id",
    [
        "",
        "slack",
        "slack:message:T1:C1",
        "slack:message::C1:1716400000.000100",
        "slack:message:T1::1716400000.000100",
        "slack:message:T1:C1:",
        "slack:message:T1:C1:1716400000.000100:extra",
    ],
)
def test_parse_rejects_malformed_slack_message_document_id(
    document_id: str,
) -> None:
    with pytest.raises(OriginalDocumentIdError):
        parse_original_document_id(
            connector=SourceType.SLACK,
            document_id=document_id,
        )


@pytest.mark.parametrize(
    "document_id",
    [
        "",
        "confluence",
        "confluence:page:123",
        "confluence:page:123:section:0",
        "confluence:page::chunk:0",
        "confluence:page:123:chunk:",
        "confluence:page:123:chunk:not-number",
        "confluence:page:123:chunk:0:extra",
    ],
)
def test_parse_rejects_malformed_confluence_document_id(
    document_id: str,
) -> None:
    with pytest.raises(OriginalDocumentIdError):
        parse_original_document_id(
            connector=SourceType.CONFLUENCE,
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


def test_original_search_request_accepts_slack_connector_enum_value() -> None:
    request = OriginalContentRequest(
        connector="slack",
        document_id="slack:message:T1:C1:1716400000.000100",
    )

    assert request.connector == SourceType.SLACK
    assert request.document_id == "slack:message:T1:C1:1716400000.000100"


def test_original_search_request_accepts_confluence_connector_enum_value() -> None:
    request = OriginalContentRequest(
        connector="confluence",
        document_id="confluence:page:123:chunk:0",
    )

    assert request.connector == SourceType.CONFLUENCE
    assert request.document_id == "confluence:page:123:chunk:0"


def test_original_search_request_rejects_unknown_connector() -> None:
    with pytest.raises(ValidationError):
        OriginalContentRequest(
            connector="unknown",
            document_id="unknown:thing:id",
        )
