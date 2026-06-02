"""Channel Talk execution tools."""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
from typing import Any

from pydantic import BaseModel
from pydantic import Field

from catchup.agents.schemas import ToolSpec
from catchup.agents.tools.base import ActionType
from catchup.agents.tools.base import BaseTool
from catchup.agents.tools.base import action
from catchup.agents.triggers.channel_talk_context import (
    extract_channel_talk_user_chat_ids,
)
from catchup.agents.triggers.events import AgentWebhookEvent
from catchup.connectors.channel_talk.core.client import ChannelTalkCoreApiClient
from catchup.connectors.channel_talk.credential_loader import load_channel_talk_connection_by_id
from catchup.connectors.channel_talk.full_sync_helper import load_channel_talk_connection
from catchup.connectors.channel_talk.schemas.channel_connection import ChannelTalkCredentialsRecord

_event_var: ContextVar[AgentWebhookEvent | None] = ContextVar(
    "channel_talk_tool_event",
    default=None,
)
_connection_var: ContextVar[ChannelTalkCredentialsRecord | None] = ContextVar(
    "channel_talk_tool_connection",
    default=None,
)


def _get_field(value: Any, field_name: str) -> Any:
    if isinstance(value, dict):
        return value.get(field_name)
    return getattr(value, field_name, None)


def _get_credential_id(tool_specs: list[ToolSpec]) -> int | None:
    credential_ids: set[int] = set()
    for tool_spec in tool_specs:
        ref = _get_field(tool_spec, "credential_ref")
        if ref is None:
            continue

        vendor = _get_field(ref, "vendor")
        if vendor and vendor != "channel_talk":
            raise RuntimeError(f"Unsupported Channel Talk credential vendor: {vendor}")

        credential_id = _get_field(ref, "credential_id")
        if credential_id is None:
            raise RuntimeError("channel_talk credential_ref.credential_id is required")
        credential_ids.add(int(credential_id))

    if len(credential_ids) > 1:
        raise RuntimeError("Channel Talk actions must use a single credential_ref")
    return next(iter(credential_ids), None)


class SendInternalUserChatMessageInput(BaseModel):
    message: str = Field(
        min_length=1,
        description="Internal note text to send to the triggered Channel Talk UserChat.",
    )


class SendInternalUserChatMessageOutput(BaseModel):
    message_id: str
    channel_id: str
    user_chat_id: str
    private: bool = True


class ChannelTalkTool(BaseTool):
    def __init__(
        self,
        *,
        client: ChannelTalkCoreApiClient | None = None,
    ) -> None:
        super().__init__(
            name="channel_talk",
            display_name="Channel Talk",
            description="Channel Talk actions scoped to the current trigger event.",
        )
        self._client = client or ChannelTalkCoreApiClient()

    @classmethod
    def bind(
        cls,
        event: AgentWebhookEvent,
        connection: ChannelTalkCredentialsRecord | None = None,
    ) -> None:
        _event_var.set(event)
        _connection_var.set(connection)

    def bind_execution_context(
        self,
        *,
        tool_specs: list[ToolSpec],
        global_context,
        trigger_event: AgentWebhookEvent,
    ) -> None:
        if trigger_event.source != "channel_talk":
            raise RuntimeError("Channel Talk tool can only run for channel_talk events")

        channel_id, _ = extract_channel_talk_user_chat_ids(trigger_event.payload)
        if not channel_id:
            raise RuntimeError("Channel Talk channel target not found in trigger event")

        credential_id = _get_credential_id(tool_specs)
        if credential_id is None:
            connection = load_channel_talk_connection(channel_id=channel_id)
        else:
            connection = load_channel_talk_connection_by_id(credential_id)

        if connection is None:
            raise RuntimeError("channel_talk credentials not found")
        if connection.channel_id != channel_id:
            raise RuntimeError(
                "channel_talk credential_ref does not match the trigger event channel"
            )
        if not connection.access_key or not connection.access_secret:
            raise RuntimeError("channel_talk credentials are incomplete")

        self.bind(trigger_event, connection)

    @action(
        input_model=SendInternalUserChatMessageInput,
        output_model=SendInternalUserChatMessageOutput,
        description=(
            "Send a private internal note to the Channel Talk UserChat that triggered "
            "this agent run. This tool never sends customer-visible messages."
        ),
        type=ActionType.WRITE,
        default_failure_policy="continue",
        default_max_retry=2,
    )
    async def send_internal_user_chat_message(
        self,
        message: str,
    ) -> SendInternalUserChatMessageOutput:
        event = _event_var.get()
        if event is None:
            raise RuntimeError(
                "AgentWebhookEvent not bound. Call ChannelTalkTool.bind() before running."
            )
        if event.source != "channel_talk":
            raise RuntimeError("Channel Talk tool can only run for channel_talk events")

        channel_id, user_chat_id = extract_channel_talk_user_chat_ids(event.payload)
        if not channel_id or not user_chat_id:
            raise RuntimeError("Channel Talk UserChat target not found in trigger event")

        connection = _connection_var.get()
        if connection is None:
            connection = await asyncio.to_thread(
                load_channel_talk_connection,
                channel_id=channel_id,
            )
        if connection is None:
            raise RuntimeError("channel_talk credentials not found")
        if connection.channel_id != channel_id:
            raise RuntimeError(
                "channel_talk credential_ref does not match the trigger event channel"
            )
        if not connection.access_key or not connection.access_secret:
            raise RuntimeError("channel_talk credentials are incomplete")

        sent_message = await self._client.send_internal_user_chat_message(
            access_key=connection.access_key,
            access_secret=connection.access_secret,
            channel_id=channel_id,
            user_chat_id=user_chat_id,
            message=message,
        )

        return SendInternalUserChatMessageOutput(
            message_id=sent_message.message_id,
            channel_id=channel_id,
            user_chat_id=user_chat_id,
            private=True,
        )
