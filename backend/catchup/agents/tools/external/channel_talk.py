"""Channel Talk execution tools."""
from __future__ import annotations

from contextvars import ContextVar

from pydantic import BaseModel
from pydantic import Field

from catchup.agents.tools.base import ActionType
from catchup.agents.tools.base import BaseTool
from catchup.agents.tools.base import action
from catchup.agents.triggers.channel_talk_context import (
    extract_channel_talk_user_chat_ids,
)
from catchup.agents.triggers.events import AgentWebhookEvent
from catchup.connectors.channel_talk.core.client import ChannelTalkCoreApiClient
from catchup.connectors.channel_talk.full_sync_helper import (
    load_channel_talk_connection,
)

_event_var: ContextVar[AgentWebhookEvent | None] = ContextVar(
    "channel_talk_tool_event",
    default=None,
)


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
    def bind(cls, event: AgentWebhookEvent) -> None:
        _event_var.set(event)

    def bind_execution_context(
        self,
        *,
        global_context,
        trigger_event: AgentWebhookEvent,
    ) -> None:
        self.bind(trigger_event)

    @action(
        input_model=SendInternalUserChatMessageInput,
        output_model=SendInternalUserChatMessageOutput,
        description=(
            "Send a private internal note to the Channel Talk UserChat that triggered "
            "this agent run. This tool never sends customer-visible messages."
        ),
        type=ActionType.WRITE,
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

        connection = load_channel_talk_connection(channel_id=channel_id)
        if connection is None:
            raise RuntimeError("channel_talk credentials not found")
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
