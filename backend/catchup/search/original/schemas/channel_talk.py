from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from catchup.db.models import SourceType
from catchup.search.original.schemas.base import OriginalContent
from catchup.server.search.schemas import OriginalContentResponse


class ChannelTalkOriginalAuthorType(StrEnum):
    CUSTOMER = "customer"
    MANAGER = "manager"


class ChannelTalkUserChatOriginalContentType(StrEnum):
    TEXT = "text"
    BLOCK = "block"
    BUTTON = "button"
    FORM = "form"
    FILE = "file"


class ChannelTalkUserChatOriginalItemType(StrEnum):
    MESSAGE = "message"


class ChannelTalkUserChatOriginalVisibility(StrEnum):
    INTERNAL = "internal"
    PUBLIC = "public"


class ChannelTalkOriginalAuthor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    name: str | None = None
    type: ChannelTalkOriginalAuthorType | None = None
    email: str | None = None
    avatar_url: str | None = None


class ChannelTalkUserChatOriginalContent(OriginalContent):
    content_type: ChannelTalkUserChatOriginalContentType


class ChannelTalkUserChatOriginalItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: ChannelTalkUserChatOriginalItemType
    visibility: ChannelTalkUserChatOriginalVisibility
    author: ChannelTalkOriginalAuthor | None = None
    contents: list[ChannelTalkUserChatOriginalContent]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ChannelTalkUserChatOriginalContentResponse(OriginalContentResponse):
    connector: Literal[SourceType.CHANNEL_TALK]
    entity_type: Literal["user_chat"]
    items: list[ChannelTalkUserChatOriginalItem] = Field(default_factory=list)
