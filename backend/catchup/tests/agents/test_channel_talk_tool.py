from __future__ import annotations

from types import SimpleNamespace

import pytest

from catchup.agents.tools.external.channel_talk import ChannelTalkTool
from catchup.agents.triggers.events import AgentWebhookEvent


class FakeChannelTalkClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send_internal_user_chat_message(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(message_id="message-1")


@pytest.mark.asyncio
async def test_channel_talk_tool_sends_internal_message_to_triggered_user_chat(
    monkeypatch,
) -> None:
    client = FakeChannelTalkClient()
    tool = ChannelTalkTool(client=client)
    event = AgentWebhookEvent(
        event_id="event-1",
        source="channel_talk",
        event_type="user_chat.new_message",
        payload={
            "entity": {
                "channelId": "channel-123",
                "chatType": "userChat",
                "chatId": "chat-1",
            },
        },
    )

    monkeypatch.setattr(
        "catchup.agents.tools.external.channel_talk.load_channel_talk_connection",
        lambda channel_id: SimpleNamespace(
            channel_id=channel_id,
            access_key="access-key",
            access_secret="access-secret",
        ),
    )

    ChannelTalkTool.bind(event)
    result = await tool.send_internal_user_chat_message(message="Agent result")

    assert result.message_id == "message-1"
    assert result.channel_id == "channel-123"
    assert result.user_chat_id == "chat-1"
    assert result.private is True
    assert client.calls == [
        {
            "access_key": "access-key",
            "access_secret": "access-secret",
            "channel_id": "channel-123",
            "user_chat_id": "chat-1",
            "message": "Agent result",
        }
    ]


@pytest.mark.asyncio
async def test_channel_talk_tool_rejects_non_channel_talk_event() -> None:
    tool = ChannelTalkTool(client=FakeChannelTalkClient())
    ChannelTalkTool.bind(
        AgentWebhookEvent(
            event_id="event-1",
            source="slack",
            event_type="message.created",
            payload={},
        )
    )

    with pytest.raises(RuntimeError, match="only run for channel_talk"):
        await tool.send_internal_user_chat_message(message="Agent result")
