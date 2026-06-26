from __future__ import annotations

from datetime import datetime
from typing import Any

from langchain_core.documents import Document
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator

from catchup.components.vector_db.v2.constants import (
    KNOWLEDGE_STORE_METADATA_COLUMN_NAMES,
)
from catchup.utils.validation import require_text


class ChannelTalkUserChatCustomerMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str | None = None
    member_id: str | None = None
    veil_id: str | None = None
    unified_id: str | None = None
    type: str | None = None
    name: str | None = None
    email: str | None = None
    mobile_number: str | None = None
    avatar_url: str | None = None
    language: str | None = None
    country: str | None = None
    city: str | None = None


class ChannelTalkUserChatAssignmentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manager_ids: list[str] = Field(default_factory=list)
    assignee_id: str | None = None
    first_assignee_id_after_open: str | None = None
    manager_role_ids: list[str] = Field(default_factory=list)


class ChannelTalkUserChatTagMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str | None = None
    name: str | None = None


class ChannelTalkUserChatMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str
    description: str | None = None
    managed: bool | None = None
    priority: str | None = None
    goal_state: str | None = None
    customer: ChannelTalkUserChatCustomerMetadata | None = None
    assignment: ChannelTalkUserChatAssignmentMetadata = Field(
        default_factory=ChannelTalkUserChatAssignmentMetadata
    )
    tags: list[ChannelTalkUserChatTagMetadata] = Field(default_factory=list)

    @field_validator("state")
    @classmethod
    def _validate_state(cls, value: str) -> str:
        return require_text(value, "state")


class ChannelTalkUserChatDataPart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type", "text")
    @classmethod
    def _validate_required_text(cls, value: str, info) -> str:
        return require_text(value, info.field_name)


class ChannelTalkUserChatData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parts: list[ChannelTalkUserChatDataPart] = Field(default_factory=list)


class ChannelTalkUserChatVectorRecord(BaseModel):
    """v2 vector-store row contract for a Channel Talk UserChat."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    langchain_id: str
    content: str
    embedding: list[float]
    source: str
    entity_type: str
    record_id: str
    scope_type: str
    scope_id: str
    target_type: str
    target_id: str
    target_name: str
    internal_author_id: str | None = None
    title: str
    body: str
    data: ChannelTalkUserChatData = Field(default_factory=ChannelTalkUserChatData)
    url: str
    created_at: datetime
    updated_at: datetime
    synced_at: datetime
    channel_talk_user_chat: ChannelTalkUserChatMetadata

    @field_validator(
        "langchain_id",
        "content",
        "source",
        "entity_type",
        "record_id",
        "scope_type",
        "scope_id",
        "target_type",
        "target_id",
        "target_name",
        "title",
        "url",
    )
    @classmethod
    def _validate_required_text(cls, value: str, info) -> str:
        return require_text(value, info.field_name)

    @property
    def langchain_metadata(self) -> dict[str, Any]:
        return {
            "channel_talk_user_chat": self.channel_talk_user_chat.model_dump(
                mode="json",
                exclude_none=False,
            )
        }

    def to_db_values(self) -> dict[str, Any]:
        values = self.model_dump(
            mode="json",
            exclude={"channel_talk_user_chat"},
            exclude_none=False,
        )
        values["langchain_metadata"] = self.langchain_metadata
        return values

    def to_document(self) -> Document:
        values = self.to_db_values()
        metadata = {
            column_name: values[column_name]
            for column_name in KNOWLEDGE_STORE_METADATA_COLUMN_NAMES
        }
        metadata["channel_talk_user_chat"] = values["langchain_metadata"][
            "channel_talk_user_chat"
        ]
        return Document(
            id=self.langchain_id,
            page_content=self.content,
            metadata=metadata,
        )
