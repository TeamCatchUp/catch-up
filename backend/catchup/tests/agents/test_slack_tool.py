from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace

import pytest

from catchup.agents.enums import FailurePolicy
from catchup.agents.schemas import ToolReferenceSpec
from catchup.agents.schemas import ToolSpec
from catchup.agents.tools.context import bind_trigger_context
from catchup.agents.tools.external.slack import SlackTool
from catchup.agents.tools.references import bind_tool_references
from catchup.agents.triggers.events import AgentWebhookEvent


class FakeSlackClient:
    instances: list["FakeSlackClient"] = []
    history_responses: list[dict] = []
    post_calls: list[dict] = []

    def __init__(self, access_token: str, team_id: str) -> None:
        self.access_token = access_token
        self.team_id = team_id
        self.history_calls: list[dict] = []
        self.instances.append(self)

    async def get_conversation_history(self, **kwargs):
        self.history_calls.append(kwargs)
        return self.history_responses.pop(0)

    async def post_message(self, **kwargs):
        self.post_calls.append(kwargs)
        return {"ok": True, "ts": "reply-ts"}


def _event() -> AgentWebhookEvent:
    return AgentWebhookEvent(
        event_id="event-1",
        source="channel_talk",
        event_type="user_chat.created",
        occurred_at=datetime(2020, 1, 1, 10, 0, tzinfo=timezone.utc),
        payload={"entity": {"channelId": "channel-talk-1", "chatId": "chat-123"}},
    )


def _slack_spec() -> ToolSpec:
    return ToolSpec(
        name="slack.find_channel_talk_user_chat_message",
        failure_policy=FailurePolicy.CONTINUE,
        max_retry=1,
    )


def _bind_tool(monkeypatch) -> SlackTool:
    FakeSlackClient.instances = []
    FakeSlackClient.history_responses = []
    FakeSlackClient.post_calls = []

    monkeypatch.setattr(
        "catchup.agents.tools.external.slack.get_slack_token_by_id",
        lambda db, credential_id: SimpleNamespace(
            id=credential_id,
            team_id="T123",
            bot_user_id="U-BOT",
            bot_access_token="xoxb-token",
        ),
    )
    monkeypatch.setattr(
        "catchup.agents.tools.external.slack.SlackApiClientWrapper",
        FakeSlackClient,
    )
    reference = ToolReferenceSpec(
        argument="channel_name",
        kind="slack_channel",
        values={
            "채널톡 연동 채널": {
                "channel_id": "C123",
                "credential_id": 7,
            }
        },
    )
    bind_tool_references(
        {
            "slack.find_channel_talk_user_chat_message": [reference],
            "slack.send_thread_message": [reference],
        }
    )

    bind_trigger_context(_event())
    tool = SlackTool()
    tool.bind_execution_context(
        tool_specs=[_slack_spec()],
        global_context=object(),
        trigger_event=_event(),
    )
    return tool


@pytest.mark.asyncio
async def test_find_channel_talk_user_chat_message_matches_slack_share_slug_url(
    monkeypatch,
) -> None:
    tool = _bind_tool(monkeypatch)
    FakeSlackClient.history_responses = [
        {
            "messages": [
                {
                    "ts": "1780389003.000001",
                    "bot_id": "B123",
                    "attachments": [
                        {
                            "title_link": (
                                "https://desk.channel.io/zxq46/user-chats/"
                                "%EC%97%98%EB%A6%AC+708-6a1f0d0dae3106ffdb6a"
                            ),
                        }
                    ],
                },
            ],
            "has_more": False,
        }
    ]

    result = await tool.find_channel_talk_user_chat_message(
        channel_name="채널톡 연동 채널",
        user_chat_id="6a1f0d0dae3106ffdb6a",
    )

    assert result.message_ts == "1780389003.000001"


@pytest.mark.asyncio
async def test_find_channel_talk_user_chat_message_matches_desk_canonical_url(
    monkeypatch,
) -> None:
    tool = _bind_tool(monkeypatch)
    FakeSlackClient.history_responses = [
        {
            "messages": [
                {
                    "ts": "1780389004.000001",
                    "bot_id": "B123",
                    "text": (
                        "https://desk.channel.io/#/channels/229395/"
                        "user_chats/6a1f0d0dae3106ffdb6a"
                    ),
                },
            ],
            "has_more": False,
        }
    ]

    result = await tool.find_channel_talk_user_chat_message(
        channel_name="채널톡 연동 채널",
        user_chat_id="6a1f0d0dae3106ffdb6a",
    )

    assert result.message_ts == "1780389004.000001"


@pytest.mark.asyncio
async def test_find_channel_talk_user_chat_message_returns_newest_bot_message(
    monkeypatch,
) -> None:
    tool = _bind_tool(monkeypatch)
    FakeSlackClient.history_responses = [
        {
            "messages": [
                {
                    "ts": "1780389000.000001",
                    "bot_id": "B123",
                    "text": "https://desk.channel.io/ws/user-chats/other-chat",
                },
                {
                    "ts": "1780389001.000001",
                    "user": "U-HUMAN",
                    "text": "https://desk.channel.io/ws/user-chats/chat-123",
                },
                {
                    "ts": "1780389002.000001",
                    "bot_id": "B123",
                    "blocks": [
                        {
                            "text": {
                                "text": "<https://desk.channel.io/ws/user-chats/chat-123|open>",
                            }
                        }
                    ],
                },
                {
                    "ts": "1780389003.000001",
                    "subtype": "bot_message",
                    "attachments": [
                        {
                            "text": "https://desk.channel.io/ws/user-chats/chat-123",
                        }
                    ],
                },
            ],
            "has_more": False,
        }
    ]

    result = await tool.find_channel_talk_user_chat_message(
        channel_name="채널톡 연동 채널",
        user_chat_id="chat-123",
    )

    assert result.channel_name == "채널톡 연동 채널"
    assert result.message_ts == "1780389003.000001"
    assert FakeSlackClient.instances[0].history_calls[0]["channel"] == "C123"
    assert FakeSlackClient.instances[0].history_calls[0]["oldest"] == "1577871000.000000"
    assert FakeSlackClient.instances[0].history_calls[0]["latest"] == "1577874600.000000"


@pytest.mark.asyncio
async def test_send_thread_message_uses_message_ts_as_thread_ts(monkeypatch) -> None:
    tool = _bind_tool(monkeypatch)

    result = await tool.send_thread_message(
        channel_name="채널톡 연동 채널",
        message_ts="1780389003.000001",
        message="Agent reply",
    )

    assert result.channel_name == "채널톡 연동 채널"
    assert result.message_ts == "1780389003.000001"
    assert FakeSlackClient.post_calls == [
        {
            "channel": "C123",
            "text": "Agent reply",
            "thread_ts": "1780389003.000001",
        }
    ]


@pytest.mark.asyncio
async def test_send_thread_message_rejects_other_channel(monkeypatch) -> None:
    tool = _bind_tool(monkeypatch)

    with pytest.raises(RuntimeError, match="not allowed"):
        await tool.send_thread_message(
            channel_name="미허용 채널",
            message_ts="1780389003.000001",
            message="Agent reply",
        )
