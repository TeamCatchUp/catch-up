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


class SlackMessageAuthorMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slack_user_id: str | None = None
    slack_bot_id: str | None = None
    name: str | None = None
    catchup_user_id: str | None = None


class SlackMessageReactionMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    count: int = 0

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return require_text(value, "name")


class SlackMessageMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_id: str
    channel_id: str
    channel_name: str
    ts: str
    thread_ts: str | None = None
    is_thread_root: bool = False
    message_type: str | None = None
    subtype: str | None = None
    author: SlackMessageAuthorMetadata | None = None
    reply_count: int = 0
    reactions: list[SlackMessageReactionMetadata] = Field(default_factory=list)
    edited_at: str | None = None
    latest_reply_ts: str | None = None

    @field_validator("team_id", "channel_id", "channel_name", "ts")
    @classmethod
    def _validate_required_text(cls, value: str, info) -> str:
        return require_text(value, info.field_name)


class SlackMessageDataPart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type", "text")
    @classmethod
    def _validate_required_text(cls, value: str, info) -> str:
        return require_text(value, info.field_name)


class SlackMessageData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parts: list[SlackMessageDataPart] = Field(default_factory=list)


class SlackMessageVectorRecord(BaseModel):
    """v2 vector-store row contract for a Slack message."""

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
    data: SlackMessageData = Field(default_factory=SlackMessageData)
    url: str
    created_at: datetime
    updated_at: datetime
    synced_at: datetime
    slack_message: SlackMessageMetadata

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
            "slack_message": self.slack_message.model_dump(
                mode="json",
                exclude_none=False,
            )
        }

    def to_db_values(self) -> dict[str, Any]:
        values = self.model_dump(
            mode="json",
            exclude={"slack_message"},
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
        metadata["slack_message"] = values["langchain_metadata"]["slack_message"]
        return Document(
            id=self.langchain_id,
            page_content=self.content,
            metadata=metadata,
        )
