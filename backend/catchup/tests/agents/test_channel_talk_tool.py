from __future__ import annotations

from types import SimpleNamespace

import pytest

from catchup.agents.enums import FailurePolicy
from catchup.agents.schemas import ToolCredentialRef
from catchup.agents.schemas import ToolSpec
from catchup.agents.tools.external.channel_talk import ChannelTalkTool
from catchup.agents.triggers.events import AgentWebhookEvent


class FakeChannelTalkClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def send_internal_user_chat_message(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(message_id="message-1")


def _channel_talk_event(channel_id: str = "channel-123") -> AgentWebhookEvent:
    return AgentWebhookEvent(
        event_id="event-1",
        source="channel_talk",
        event_type="user_chat.new_message",
        payload={
            "entity": {
                "channelId": channel_id,
                "chatType": "userChat",
                "chatId": "chat-1",
            },
        },
    )


def _channel_talk_tool_spec(credential_id: int = 42) -> ToolSpec:
    return ToolSpec(
        name="channel_talk.send_internal_user_chat_message",
        failure_policy=FailurePolicy.CONTINUE,
        max_retry=2,
        credential_ref=ToolCredentialRef(
            vendor="channel_talk",
            credential_id=credential_id,
        ),
    )


@pytest.mark.asyncio
async def test_channel_talk_tool_sends_internal_message_to_triggered_user_chat(
    monkeypatch,
) -> None:
    client = FakeChannelTalkClient()
    tool = ChannelTalkTool(client=client)
    event = _channel_talk_event()

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
async def test_channel_talk_tool_binds_credential_by_spec_id(monkeypatch) -> None:
    client = FakeChannelTalkClient()
    tool = ChannelTalkTool(client=client)
    event = _channel_talk_event()

    monkeypatch.setattr(
        "catchup.agents.tools.external.channel_talk.load_channel_talk_connection_by_id",
        lambda credential_id: SimpleNamespace(
            id=credential_id,
            channel_id="channel-123",
            access_key="access-key-by-id",
            access_secret="access-secret-by-id",
        ),
    )
    monkeypatch.setattr(
        "catchup.agents.tools.external.channel_talk.load_channel_talk_connection",
        lambda channel_id: pytest.fail("expected bound credential to be reused"),
    )

    tool.bind_execution_context(
        tool_specs=[_channel_talk_tool_spec(credential_id=42)],
        global_context=object(),
        trigger_event=event,
    )
    await tool.send_internal_user_chat_message(message="Agent result")

    assert client.calls[0]["access_key"] == "access-key-by-id"
    assert client.calls[0]["access_secret"] == "access-secret-by-id"


def test_channel_talk_tool_rejects_credential_for_different_channel(monkeypatch) -> None:
    tool = ChannelTalkTool(client=FakeChannelTalkClient())
    event = _channel_talk_event(channel_id="channel-123")

    monkeypatch.setattr(
        "catchup.agents.tools.external.channel_talk.load_channel_talk_connection_by_id",
        lambda credential_id: SimpleNamespace(
            id=credential_id,
            channel_id="other-channel",
            access_key="access-key",
            access_secret="access-secret",
        ),
    )

    with pytest.raises(RuntimeError, match="does not match"):
        tool.bind_execution_context(
            tool_specs=[_channel_talk_tool_spec(credential_id=42)],
            global_context=object(),
            trigger_event=event,
        )


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
