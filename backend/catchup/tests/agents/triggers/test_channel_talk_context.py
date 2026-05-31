from types import SimpleNamespace

import pytest

from catchup.agents.triggers.channel_talk_context import CHANNEL_TALK_CHANNEL_ID_KEY
from catchup.agents.triggers.channel_talk_context import (
    CHANNEL_TALK_USER_CHAT_CONTEXT_KEY,
)
from catchup.agents.triggers.channel_talk_context import CHANNEL_TALK_USER_CHAT_ID_KEY
from catchup.agents.triggers.channel_talk_context import (
    build_channel_talk_user_chat_inputs,
)
from catchup.agents.triggers.channel_talk_context import (
    extract_channel_talk_user_chat_ids,
)
from catchup.agents.triggers.channel_talk_context import (
    fetch_channel_talk_user_chat_context,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)


def test_extract_channel_talk_user_chat_ids_from_created_payload() -> None:
    assert extract_channel_talk_user_chat_ids(
        {
            "entity": {
                "channelId": "ch-001",
                "id": "chat-1",
            }
        }
    ) == ("ch-001", "chat-1")


def test_extract_channel_talk_user_chat_ids_from_message_payload() -> None:
    assert extract_channel_talk_user_chat_ids(
        {
            "entity": {
                "channelId": "ch-001",
                "chatType": "userChat",
                "chatId": "chat-1",
                "id": "msg-1",
            }
        }
    ) == ("ch-001", "chat-1")


@pytest.mark.asyncio
async def test_build_channel_talk_user_chat_inputs_uses_contextual_content(monkeypatch) -> None:
    record = ChannelTalkCredentialsRecord(
        channel_id="ch-001",
        channel_name="Support",
        access_key="access",
        access_secret="secret",
        webhook_token="token",
    )

    async def fetch_context(**kwargs):
        assert kwargs["connection_record"] is record
        assert kwargs["user_chat_id"] == "chat-1"
        return "assembled context"

    monkeypatch.setattr(
        "catchup.agents.triggers.channel_talk_context.load_channel_talk_connection",
        lambda channel_id: record if channel_id == "ch-001" else None,
    )
    monkeypatch.setattr(
        "catchup.agents.triggers.channel_talk_context.fetch_channel_talk_user_chat_context",
        fetch_context,
    )

    result = await build_channel_talk_user_chat_inputs(
        {
            "entity": {
                "channelId": "ch-001",
                "chatType": "userChat",
                "chatId": "chat-1",
            },
        }
    )

    assert result == {
        CHANNEL_TALK_CHANNEL_ID_KEY: "ch-001",
        CHANNEL_TALK_USER_CHAT_ID_KEY: "chat-1",
        CHANNEL_TALK_USER_CHAT_CONTEXT_KEY: "assembled context",
    }


@pytest.mark.asyncio
async def test_fetch_channel_talk_user_chat_context_uses_transformer_output() -> None:
    record = ChannelTalkCredentialsRecord(
        channel_id="ch-001",
        channel_name="Support",
        access_key="access",
        access_secret="secret",
        webhook_token="token",
    )
    bundle = SimpleNamespace()

    class FakeFetcher:
        async def fetch_user_chat_bundle_by_id(self, **kwargs):
            assert kwargs["connection"].channel_id == "ch-001"
            assert kwargs["user_chat_id"] == "chat-1"
            return bundle

        async def fetch_managers_by_id(self, **kwargs):
            assert kwargs["connection"].channel_id == "ch-001"
            return {"manager-1": SimpleNamespace()}

    class FakeTransformer:
        def build(self, **kwargs):
            assert kwargs["bundle"] is bundle
            assert "manager-1" in kwargs["managers_by_id"]
            return SimpleNamespace(contextual_content="assembled context")

    result = await fetch_channel_talk_user_chat_context(
        connection_record=record,
        user_chat_id="chat-1",
        fetcher=FakeFetcher(),
        transformer=FakeTransformer(),
    )

    assert result == "assembled context"
