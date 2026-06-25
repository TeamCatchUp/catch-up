"""Channel Talk execution tools."""
from __future__ import annotations

import asyncio

from pydantic import BaseModel
from pydantic import Field

from catchup.agents.schemas import ToolSpec
from catchup.agents.tools.base import ActionType
from catchup.agents.tools.base import BaseTool
from catchup.agents.tools.base import action
from catchup.agents.tools.context import get_trigger_context
from catchup.agents.tools.references import resolve_tool_reference
from catchup.agents.triggers.channel_talk_context import (
    extract_channel_talk_user_chat_ids,
)
from catchup.agents.triggers.events import AgentWebhookEvent
from catchup.connectors.channel_talk.core.client import ChannelTalkCoreApiClient
from catchup.connectors.channel_talk.credential_loader import (
    load_channel_talk_connection_by_id,
)


class SendInternalUserChatMessageInput(BaseModel):
    channel_name: str = Field(
        min_length=1,
        description="Configured Channel Talk channel reference key selected in AgentSpec references.",
    )
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

    def bind_execution_context(
        self,
        *,
        tool_specs: list[ToolSpec],
        global_context,
        trigger_event: AgentWebhookEvent,
    ) -> None:
        return None

    # TODO : 현재는 Trigger Context에서 user_chat_id를 꺼내는데, TriggerContext에서 꺼낼 수 있는 중간 툴 혹은 user_chat_id를 검색하는 툴을 만들어 Input Model으로 받도록 수정
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
        channel_name: str,
        message: str,
    ) -> SendInternalUserChatMessageOutput:
        event = get_trigger_context().event
        if event.source != "channel_talk":
            raise RuntimeError("Channel Talk tool can only run for channel_talk events")

        triggered_channel_id, user_chat_id = extract_channel_talk_user_chat_ids(
            event.payload
        )
        if not triggered_channel_id:
            raise RuntimeError(
                "Channel Talk channel_id was not found in the trigger event."
            )
        if not user_chat_id:
            raise RuntimeError(
                "Channel Talk user_chat_id was not found in the trigger event."
            )

        reference = resolve_tool_reference(
            tool_name="channel_talk.send_internal_user_chat_message",
            argument="channel_name",
            input_value=channel_name,
            kind="channel_talk_channel",
        )
        channel_id = str(reference.get("channel_id") or "").strip()
        credential_id = reference.get("credential_id")
        if not channel_id:
            raise RuntimeError("channel_talk reference missing channel_id")
        if credential_id is None:
            raise RuntimeError("channel_talk reference missing credential_id")
        if channel_id != triggered_channel_id:
            raise RuntimeError(
                "Channel Talk reference channel does not match the triggered channel."
            )

        connection = await asyncio.to_thread(
            load_channel_talk_connection_by_id,
            int(credential_id),
        )
        if connection is None:
            raise RuntimeError(
                "channel_talk credentials not found for the triggered channel."
            )
        if connection.channel_id != channel_id:
            raise RuntimeError(
                "Loaded Channel Talk credentials do not match the triggered channel."
            )
        if not connection.access_key or not connection.access_secret:
            raise RuntimeError(
                "channel_talk credentials are incomplete for the triggered channel."
            )

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
