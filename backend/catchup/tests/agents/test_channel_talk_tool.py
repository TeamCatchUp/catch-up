from __future__ import annotations

from types import SimpleNamespace

import pytest

from catchup.agents.enums import FailurePolicy
from catchup.agents.schemas import ToolReferenceSpec
from catchup.agents.schemas import ToolSpec
from catchup.agents.tools.context import bind_trigger_context
from catchup.agents.tools.external.channel_talk import ChannelTalkTool
from catchup.agents.tools.references import bind_tool_references
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


def _channel_talk_tool_spec() -> ToolSpec:
    return ToolSpec(
        name="channel_talk.send_internal_user_chat_message",
        failure_policy=FailurePolicy.CONTINUE,
        max_retry=2,
    )


def _bind_references(
    *,
    channel_id: str = "channel-123",
    credential_id: int = 42,
) -> None:
    bind_tool_references(
        {
            "channel_talk.send_internal_user_chat_message": [
                ToolReferenceSpec(
                    argument="channel_name",
                    kind="channel_talk_channel",
                    values={
                        "채널톡 연동 채널": {
                            "channel_id": channel_id,
                            "credential_id": credential_id,
                        }
                    },
                )
            ]
        }
    )


@pytest.mark.asyncio
async def test_channel_talk_tool_sends_internal_message_to_triggered_user_chat(
    monkeypatch,
) -> None:
    client = FakeChannelTalkClient()
    tool = ChannelTalkTool(client=client)
    event = _channel_talk_event()
    _bind_references()

    monkeypatch.setattr(
        "catchup.agents.tools.external.channel_talk.load_channel_talk_connection_by_id",
        lambda credential_id: SimpleNamespace(
            id=credential_id,
            channel_id="channel-123",
            access_key="access-key",
            access_secret="access-secret",
        ),
    )

    bind_trigger_context(event)
    result = await tool.send_internal_user_chat_message(
        channel_name="채널톡 연동 채널",
        message="Agent result",
    )

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
async def test_channel_talk_tool_loads_trigger_channel_credentials_lazily(
    monkeypatch,
) -> None:
    client = FakeChannelTalkClient()
    tool = ChannelTalkTool(client=client)
    event = _channel_talk_event()
    _bind_references(credential_id=42)

    load_calls = []
    monkeypatch.setattr(
        "catchup.agents.tools.external.channel_talk.load_channel_talk_connection_by_id",
        lambda credential_id: load_calls.append(credential_id) or SimpleNamespace(
            id=credential_id,
            channel_id="channel-123",
            access_key="access-key-bound",
            access_secret="access-secret-bound",
        ),
    )

    tool.bind_execution_context(
        tool_specs=[_channel_talk_tool_spec()],
        global_context=object(),
        trigger_event=event,
    )
    bind_trigger_context(event)

    assert load_calls == []

    await tool.send_internal_user_chat_message(
        channel_name="채널톡 연동 채널",
        message="Agent result",
    )

    assert load_calls == [42]
    assert client.calls[0]["access_key"] == "access-key-bound"
    assert client.calls[0]["access_secret"] == "access-secret-bound"


@pytest.mark.asyncio
async def test_channel_talk_tool_rejects_non_channel_talk_event_at_action_time() -> None:
    tool = ChannelTalkTool(client=FakeChannelTalkClient())
    event = AgentWebhookEvent(
        event_id="event-1",
        source="slack",
        event_type="message.created",
        payload={},
    )

    tool.bind_execution_context(
        tool_specs=[_channel_talk_tool_spec()],
        global_context=object(),
        trigger_event=event,
    )
    bind_trigger_context(event)

    with pytest.raises(RuntimeError, match="only run for channel_talk"):
        await tool.send_internal_user_chat_message(
            channel_name="채널톡 연동 채널",
            message="Agent result",
        )


@pytest.mark.asyncio
async def test_channel_talk_tool_reports_missing_channel_id(monkeypatch) -> None:
    tool = ChannelTalkTool(client=FakeChannelTalkClient())
    _bind_references()
    bind_trigger_context(
        AgentWebhookEvent(
            event_id="event-1",
            source="channel_talk",
            event_type="user_chat.new_message",
            payload={"entity": {"chatType": "userChat", "chatId": "chat-1"}},
        )
    )

    load_calls = []
    monkeypatch.setattr(
        "catchup.agents.tools.external.channel_talk.load_channel_talk_connection_by_id",
        lambda credential_id: load_calls.append(credential_id),
    )

    with pytest.raises(RuntimeError, match="channel_id was not found"):
        await tool.send_internal_user_chat_message(
            channel_name="채널톡 연동 채널",
            message="Agent result",
        )

    assert load_calls == []


@pytest.mark.asyncio
async def test_channel_talk_tool_reports_missing_user_chat_id(monkeypatch) -> None:
    tool = ChannelTalkTool(client=FakeChannelTalkClient())
    _bind_references()
    bind_trigger_context(
        AgentWebhookEvent(
            event_id="event-1",
            source="channel_talk",
            event_type="user_chat.new_message",
            payload={"entity": {"channelId": "channel-123", "chatType": "userChat"}},
        )
    )

    load_calls = []
    monkeypatch.setattr(
        "catchup.agents.tools.external.channel_talk.load_channel_talk_connection_by_id",
        lambda credential_id: load_calls.append(credential_id),
    )

    with pytest.raises(RuntimeError, match="user_chat_id was not found"):
        await tool.send_internal_user_chat_message(
            channel_name="채널톡 연동 채널",
            message="Agent result",
        )

    assert load_calls == []


@pytest.mark.asyncio
async def test_channel_talk_tool_rejects_reference_for_other_channel(
    monkeypatch,
) -> None:
    tool = ChannelTalkTool(client=FakeChannelTalkClient())
    _bind_references(channel_id="other-channel")

    load_calls = []
    monkeypatch.setattr(
        "catchup.agents.tools.external.channel_talk.load_channel_talk_connection_by_id",
        lambda credential_id: load_calls.append(credential_id),
    )

    bind_trigger_context(_channel_talk_event(channel_id="channel-123"))

    with pytest.raises(RuntimeError, match="does not match the triggered channel"):
        await tool.send_internal_user_chat_message(
            channel_name="채널톡 연동 채널",
            message="Agent result",
        )

    assert load_calls == []
