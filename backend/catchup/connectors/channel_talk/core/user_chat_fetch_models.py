from __future__ import annotations

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import ValidationInfo
from pydantic import field_validator
from pydantic import model_validator

from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatDetail
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatListItem,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatState
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessage,
)
from catchup.utils.validation import require_text


class ChannelTalkUserChatFullSyncConnection(BaseModel):
    """Validated Channel Talk credentials for the UserChat fetch boundary."""

    model_config = ConfigDict(extra="forbid")

    channel_id: str
    channel_name: str
    access_key: str
    access_secret: str

    @field_validator("channel_id", "channel_name", "access_key", "access_secret")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @classmethod
    def from_credentials_record(
        cls,
        record: ChannelTalkCredentialsRecord,
    ) -> "ChannelTalkUserChatFullSyncConnection":
        return cls(
            channel_id=record.channel_id,
            channel_name=record.channel_name,
            access_key=require_text(record.access_key, "access_key"),
            access_secret=require_text(record.access_secret, "access_secret"),
        )


class ChannelTalkFetchedUserChat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: ChannelTalkUserChatState
    channel_name: str
    list_item: ChannelTalkUserChatListItem
    detail: ChannelTalkUserChatDetail
    messages: tuple[ChannelTalkUserChatMessage, ...] = ()

    @field_validator("messages")
    @classmethod
    def _validate_messages(
        cls,
        value: tuple[ChannelTalkUserChatMessage, ...],
    ) -> tuple[ChannelTalkUserChatMessage, ...]:
        return tuple(value)


class ChannelTalkFetchedUserChatsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundles: tuple[ChannelTalkFetchedUserChat, ...] = ()
    next_checkpoint_state: ChannelTalkUserChatState | None = None
    next_checkpoint_cursor: str | None = None

    @model_validator(mode="after")
    def _validate_checkpoint_shape(self) -> "ChannelTalkFetchedUserChatsResult":
        if (
            self.next_checkpoint_cursor is not None
            and self.next_checkpoint_state is None
        ):
            raise ValueError(
                "next_checkpoint_state is required with next_checkpoint_cursor"
            )
        return self
