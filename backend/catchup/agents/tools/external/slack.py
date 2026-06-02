"""Slack execution tools for Channel Talk-linked messages."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from urllib.parse import unquote
from urllib.parse import unquote_plus

from pydantic import BaseModel
from pydantic import Field

from catchup.agents.enums import ActionType
from catchup.agents.schemas import ToolSpec
from catchup.agents.tools.base import BaseTool
from catchup.agents.tools.base import action
from catchup.agents.tools.context import get_trigger_context
from catchup.agents.triggers.events import AgentWebhookEvent
from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.db.engine import SessionLocal
from catchup.db.slack.oauth_repository import get_slack_token_by_id

_USER_CHAT_URL_RE = re.compile(
    r"https?://[^\s<|>]+/user-chats/(?P<user_chat_id>[^\s<|>/?#]+)"
)
_SEARCH_WINDOW = timedelta(minutes=30)


@dataclass(slots=True, frozen=True)
class _ResolvedSlackChannel:
    channel_name: str
    channel_id: str
    team_id: str
    bot_access_token: str
    bot_user_id: str


class FindChannelTalkUserChatMessageInput(BaseModel):
    channel_name: str = Field(
        min_length=1,
        description="Configured Slack channel reference key selected in AgentSpec references.",
    )
    user_chat_id: str = Field(
        min_length=1,
        description="Channel Talk UserChat ID to match in Slack Channel Talk URLs.",
    )


class SlackThreadMessageIdentifier(BaseModel):
    channel_name: str = Field(description="Slack channel reference key used for the root message.")
    message_ts: str = Field(
        description="Slack root message timestamp. Pass as thread_ts for thread replies.",
    )


class SendThreadMessageInput(BaseModel):
    channel_name: str = Field(description="Configured Slack channel reference key.")
    message_ts: str = Field(
        description="Slack root message timestamp from find_channel_talk_user_chat_message.",
    )
    message: str = Field(
        min_length=1,
        description="Thread reply text to send.",
    )


def _get_trigger_occurred_at(event: AgentWebhookEvent) -> datetime:
    if event.source != "channel_talk":
        raise RuntimeError("Slack Channel Talk tools can only run for channel_talk events")

    occurred_at = event.occurred_at or event.received_at
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    else:
        occurred_at = occurred_at.astimezone(timezone.utc)
    return occurred_at


def _load_slack_channel(
    *,
    channel_name: str,
    channel_id: str,
    credential_id: int,
) -> _ResolvedSlackChannel:
    with SessionLocal() as db:
        token = get_slack_token_by_id(db, credential_id)
        if token is None:
            raise RuntimeError("slack credentials not found")
        if not token.bot_access_token or not token.team_id or not token.bot_user_id:
            raise RuntimeError("slack credentials are incomplete")
        return _ResolvedSlackChannel(
            channel_name=channel_name,
            team_id=token.team_id,
            bot_access_token=token.bot_access_token,
            bot_user_id=token.bot_user_id,
            channel_id=channel_id,
        )


def _extract_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for child in value.values():
            strings.extend(_extract_strings(child))
        return strings
    if isinstance(value, list):
        strings = []
        for child in value:
            strings.extend(_extract_strings(child))
        return strings
    return []


def _message_contains_user_chat_id(message: dict[str, Any], user_chat_id: str) -> bool:
    for text in _extract_strings(message):
        for match in _USER_CHAT_URL_RE.finditer(text):
            segment = match.group("user_chat_id")
            candidates = {segment, unquote(segment), unquote_plus(segment)}
            if user_chat_id in candidates:
                return True
    return False


def _is_bot_message(message: dict[str, Any]) -> bool:
    if message.get("bot_id"):
        return True
    return message.get("subtype") == "bot_message"


def _slack_ts(value: datetime) -> str:
    return f"{value.timestamp():.6f}"


class SlackTool(BaseTool):
    def __init__(self) -> None:
        super().__init__(
            name="slack",
            display_name="Slack",
            description="Slack actions scoped to a selected credential and channel.",
        )

    def bind_execution_context(
        self,
        *,
        tool_specs: list[ToolSpec],
        global_context,
        trigger_event: AgentWebhookEvent,
    ) -> None:
        return None

    def _resolve_channel(
        self,
        *,
        tool_name: str,
        channel_name: str,
    ) -> _ResolvedSlackChannel:
        from catchup.agents.tools.references import resolve_tool_reference

        value = resolve_tool_reference(
            tool_name=tool_name,
            argument="channel_name",
            input_value=channel_name,
            kind="slack_channel",
        )
        channel_id = str(value.get("channel_id") or "").strip()
        credential_id = value.get("credential_id")
        if not channel_id:
            raise RuntimeError("slack reference missing channel_id")
        if credential_id is None:
            raise RuntimeError("slack reference missing credential_id")
        return _load_slack_channel(
            channel_name=channel_name,
            channel_id=channel_id,
            credential_id=int(credential_id),
        )

    def _client(self, channel: _ResolvedSlackChannel) -> SlackApiClientWrapper:
        return SlackApiClientWrapper(channel.bot_access_token, channel.team_id)

    @action(
        input_model=FindChannelTalkUserChatMessageInput,
        output_model=SlackThreadMessageIdentifier,
        description=(
            "Find the newest bot-authored Slack message in the configured channel whose "
            "Channel Talk /user-chats/{id} URL matches the given user_chat_id. "
            "Searches from trigger occurred_at - 30 minutes to min(occurred_at + 30 minutes, now)."
        ),
        type=ActionType.READ,
        default_failure_policy="continue",
        default_max_retry=1,
    )
    async def find_channel_talk_user_chat_message(
        self,
        channel_name: str,
        user_chat_id: str,
    ) -> SlackThreadMessageIdentifier:
        occurred_at = _get_trigger_occurred_at(get_trigger_context().event)
        channel = self._resolve_channel(
            tool_name="slack.find_channel_talk_user_chat_message",
            channel_name=channel_name,
        )

        now = datetime.now(timezone.utc)
        oldest_at = occurred_at - _SEARCH_WINDOW
        latest_at = min(occurred_at + _SEARCH_WINDOW, now)

        client = self._client(channel)
        cursor: str | None = None
        newest_match: dict[str, Any] | None = None

        while True:
            response = await client.get_conversation_history(
                channel=channel.channel_id,
                oldest=_slack_ts(oldest_at),
                latest=_slack_ts(latest_at),
                cursor=cursor,
                limit=15,
                inclusive=True,
            )

            for message in response.get("messages", []):
                if not isinstance(message, dict):
                    continue
                if not _is_bot_message(message):
                    continue
                if not _message_contains_user_chat_id(message, user_chat_id):
                    continue
                if newest_match is None or str(message.get("ts", "")) > str(newest_match.get("ts", "")):
                    newest_match = message

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not response.get("has_more") or not cursor:
                break

        if newest_match is None:
            raise RuntimeError("Slack Channel Talk linked bot message not found")

        message_ts = str(newest_match.get("ts") or "").strip()
        if not message_ts:
            raise RuntimeError("Slack matched message is missing ts")

        return SlackThreadMessageIdentifier(
            channel_name=channel.channel_name,
            message_ts=message_ts,
        )

    @action(
        input_model=SendThreadMessageInput,
        output_model=SlackThreadMessageIdentifier,
        description=(
            "Send a Slack thread reply to the root message identified by channel_id and message_ts. "
            "The message_ts is passed to Slack chat.postMessage as thread_ts."
        ),
        type=ActionType.WRITE,
        default_failure_policy="continue",
        default_max_retry=2,
    )
    async def send_thread_message(
        self,
        channel_name: str,
        message_ts: str,
        message: str,
    ) -> SlackThreadMessageIdentifier:
        channel = self._resolve_channel(
            tool_name="slack.send_thread_message",
            channel_name=channel_name,
        )

        await self._client(channel).post_message(
            channel=channel.channel_id,
            text=message,
            thread_ts=message_ts,
        )

        return SlackThreadMessageIdentifier(
            channel_name=channel.channel_name,
            message_ts=message_ts,
        )
