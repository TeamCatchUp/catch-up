from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationInfo
from pydantic import field_validator

from catchup.connector_core.domain.structure import ConnectorKey
from catchup.connector_core.ports.metadata_sync import MetadataSyncRequest
from catchup.connector_core.ports.metadata_sync import MetadataSyncResult
from catchup.connectors.channel_talk.schemas._parsing import _first_localized_text
from catchup.connectors.channel_talk.schemas._parsing import _mapping_copy
from catchup.connectors.channel_talk.schemas._parsing import _parse_page
from catchup.connectors.channel_talk.schemas._parsing import _PayloadReader
from catchup.connectors.channel_talk.schemas._parsing import _required_reader_text
from catchup.connectors.channel_talk.schemas._parsing import _unwrap_payload
from catchup.connectors.channel_talk.schemas._parsing import _validation_field_name
from catchup.utils.validation import require_text


class ChannelTalkDocumentSpace(BaseModel):
    model_config = ConfigDict(extra="ignore")

    space_id: str
    space_name: str
    channel_id: str

    @field_validator("space_id", "space_name", "channel_id")
    @classmethod
    def validate_space_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, _validation_field_name(info))

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkDocumentSpace":
        source = _unwrap_payload(payload, "space")
        reader = _PayloadReader(source)
        space_id = _required_reader_text(
            reader,
            "space payload missing space id",
            "id",
        )
        channel_id = _required_reader_text(
            reader,
            "space payload missing channel id",
            "channelId",
        )
        return cls(
            space_id=space_id,
            space_name=reader.text("name", skip_mappings=True) or _first_localized_text(_mapping_copy(source.get("name"))) or space_id,
            channel_id=channel_id,
        )










class ChannelTalkDocumentAuthorMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    channel_id: str | None = None
    space_id: str | None = None
    author_id: str
    name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    profile: dict[str, Any] | None = Field(default=None, exclude=True)

    @field_validator("author_id")
    @classmethod
    def validate_author_id(cls, value: str) -> str:
        return require_text(value, "author_id")

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkDocumentAuthorMetadata":
        if not isinstance(payload, Mapping):
            raise ValueError("author payload must be an object")
        reader = _PayloadReader(payload)
        author_id = _required_reader_text(
            reader,
            "author payload missing author id",
            "id",
        )
        profile = _mapping_copy(payload.get("profile"))
        return cls(
            author_id=author_id,
            name=reader.text(
                "name",
                "displayName",
                "display_name",
                skip_mappings=True,
            )
            or _first_localized_text(profile, "name", "displayName", "display_name"),
            email=reader.text("email"),
            avatar_url=reader.text("avatarUrl"),
            profile=profile,
        )


class ChannelTalkDocumentAuthorPage(BaseModel):
    authors: list[ChannelTalkDocumentAuthorMetadata]
    next_page_token: str | None = None

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkDocumentAuthorPage":
        items, next_page_token = _parse_page(
            payload,
            item_keys=("authors",),
            parse_item=ChannelTalkDocumentAuthorMetadata.from_api_payload,
        )
        return cls(authors=items, next_page_token=next_page_token)


class ChannelTalkDocumentNavNodeMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    channel_id: str | None = None
    space_id: str | None = None
    nav_node_id: str
    parent_node_id: str | None = None
    node_type: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    name: str | None = None
    rank: int | None = None
    language: str | None = None

    @field_validator("nav_node_id")
    @classmethod
    def validate_nav_node_id(cls, value: str) -> str:
        return require_text(value, "nav_node_id")

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkDocumentNavNodeMetadata":
        if not isinstance(payload, Mapping):
            raise ValueError("nav node payload must be an object")
        reader = _PayloadReader(payload)
        nav_node_id = _required_reader_text(
            reader,
            "nav node payload missing nav node id",
            "id",
        )
        return cls(
            nav_node_id=nav_node_id,
            parent_node_id=reader.text("parentNodeId"),
            node_type=reader.text("nodeType"),
            entity_type=reader.text("entityType"),
            entity_id=reader.text("entityId"),
            name=reader.text("name", "title"),
            rank=reader.integer("rank"),
            language=reader.text("language"),
        )


class ChannelTalkDocumentNavNodePage(BaseModel):
    nav_nodes: list[ChannelTalkDocumentNavNodeMetadata]
    next_page_token: str | None = None

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkDocumentNavNodePage":
        items, next_page_token = _parse_page(
            payload,
            item_keys=("navNodes",),
            parse_item=ChannelTalkDocumentNavNodeMetadata.from_api_payload,
        )
        return cls(nav_nodes=items, next_page_token=next_page_token)

class ChannelTalkDocumentMetadataSyncRequest(BaseModel):
    channel_id: str
    space_id: str | None = None

    @field_validator("channel_id")
    @classmethod
    def validate_channel_id(cls, value: str) -> str:
        return require_text(value, "channel_id")

    @field_validator("space_id")
    @classmethod
    def validate_space_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return require_text(value, "space_id")

    def to_core_request(self) -> MetadataSyncRequest:
        return MetadataSyncRequest(
            connector=ConnectorKey.CHANNEL_TALK,
            tenant_id=self.channel_id,
            target_id=self.space_id,
        )


class ChannelTalkDocumentMetadataSyncResult(BaseModel):
    connector: ConnectorKey
    channel_id: str
    space_id: str | None = None
    space_synced: bool = False
    authors_synced: int = 0
    nav_nodes_synced: int = 0

    @classmethod
    def from_core_result(cls, result: MetadataSyncResult) -> "ChannelTalkDocumentMetadataSyncResult":
        space_step = result.step_result("document_space")
        authors_step = result.step_result("document_authors")
        nav_step = result.step_result("document_nav_nodes")
        return cls(
            connector=result.connector,
            channel_id=result.tenant_id,
            space_id=result.target_id,
            space_synced=(space_step.synced_count > 0) if space_step else False,
            authors_synced=authors_step.synced_count if authors_step else 0,
            nav_nodes_synced=nav_step.synced_count if nav_step else 0,
        )
