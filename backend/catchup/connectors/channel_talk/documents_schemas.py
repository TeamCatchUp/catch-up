from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from datetime import timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import ValidationInfo
from pydantic import field_validator

from catchup.connector_core.domain.structure import ConnectorKey
from catchup.connector_core.ports.metadata_sync import MetadataSyncRequest
from catchup.connector_core.ports.metadata_sync import MetadataSyncResult
from catchup.utils.validation import require_text


class ChannelTalkDocumentAssociationStatus(StrEnum):
    API_VERIFIED = "api_verified"
    LOCAL_TRUSTED = "local_trusted"
    UNVERIFIED = "unverified"
    FAILED = "failed"


class ChannelTalkDocumentConnectRequest(BaseModel):
    access_key: str
    access_secret: str

    @field_validator("access_key", "access_secret")
    @classmethod
    def validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, _validation_field_name(info))


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
            "spaceId",
            "space_id",
        )
        channel_id = _required_reader_text(
            reader,
            "space payload missing channel id",
            "channelId",
            "channel_id",
            "channelTalkChannelId",
            "channelTalkChannelID",
            "channel",
        )
        return cls(
            space_id=space_id,
            space_name=reader.text("name", "spaceName", "space_name", "title") or space_id,
            channel_id=channel_id,
        )


class ChannelTalkDocumentCredentialsRecord(BaseModel):
    channel_id: str
    space_id: str
    space_name: str
    access_key: str | None = None
    access_secret: str | None = None
    credential_last_verified_at: datetime | None = None
    association_status: ChannelTalkDocumentAssociationStatus

    @field_validator("channel_id", "space_id", "space_name")
    @classmethod
    def validate_record_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, _validation_field_name(info))


class ChannelTalkDocumentCredentialsUpsert(BaseModel):
    channel_id: str
    access_key: str
    access_secret: str
    space: ChannelTalkDocumentSpace
    credential_last_verified_at: datetime
    association_status: ChannelTalkDocumentAssociationStatus

    @field_validator("channel_id", "access_key", "access_secret")
    @classmethod
    def validate_upsert_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, _validation_field_name(info))

    def to_record(self) -> ChannelTalkDocumentCredentialsRecord:
        return ChannelTalkDocumentCredentialsRecord(
            channel_id=self.channel_id,
            space_id=self.space.space_id,
            space_name=self.space.space_name,
            access_key=self.access_key,
            access_secret=self.access_secret,
            credential_last_verified_at=self.credential_last_verified_at,
            association_status=self.association_status,
        )


class ChannelTalkDocumentCredentialsStatus(BaseModel):
    installed: bool
    channel_id: str | None = None
    space_id: str | None = None
    space_name: str | None = None
    credential_last_verified_at: datetime | None = None
    association_status: ChannelTalkDocumentAssociationStatus | None = None

    @classmethod
    def disconnected(cls) -> "ChannelTalkDocumentCredentialsStatus":
        return cls(installed=False)

    @classmethod
    def from_record(
        cls,
        record: ChannelTalkDocumentCredentialsRecord | None,
    ) -> "ChannelTalkDocumentCredentialsStatus":
        if record is None:
            return cls.disconnected()
        return cls(
            installed=True,
            channel_id=record.channel_id,
            space_id=record.space_id,
            space_name=record.space_name,
            credential_last_verified_at=record.credential_last_verified_at,
            association_status=record.association_status,
        )


class ChannelTalkDocumentUninstallResult(BaseModel):
    success: bool = True
    removed: bool = False
    installed: bool = False


class ChannelTalkDocumentAuthorMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    channel_id: str | None = None
    space_id: str | None = None
    author_id: str
    name: str | None = None
    email: str | None = None
    avatar_url: str | None = None

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
            "authorId",
            "author_id",
        )
        return cls(
            author_id=author_id,
            name=reader.text("name", "displayName", "display_name"),
            email=reader.text("email"),
            avatar_url=reader.text("avatarUrl", "avatarURL", "avatar_url"),
        )


class ChannelTalkDocumentAuthorPage(BaseModel):
    authors: list[ChannelTalkDocumentAuthorMetadata]
    next_page_token: str | None = None

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkDocumentAuthorPage":
        items, next_page_token = _parse_page(
            payload,
            item_keys=("authors", "results", "items"),
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
            "navNodeId",
            "nav_node_id",
        )
        return cls(
            nav_node_id=nav_node_id,
            parent_node_id=reader.text("parentId", "parentNodeId", "parent_node_id"),
            node_type=reader.text("type", "nodeType", "node_type"),
            entity_type=reader.text("entityType", "entity_type"),
            entity_id=reader.text("entityId", "entity_id"),
            name=reader.text("name", "title"),
            rank=reader.integer("rank", "order", "sortOrder", "sort_order"),
            language=reader.text("language", "locale"),
        )


class ChannelTalkDocumentNavNodePage(BaseModel):
    nav_nodes: list[ChannelTalkDocumentNavNodeMetadata]
    next_page_token: str | None = None

    @classmethod
    def from_api_payload(cls, payload: Any) -> "ChannelTalkDocumentNavNodePage":
        items, next_page_token = _parse_page(
            payload,
            item_keys=("navNodes", "nav_nodes", "nodes", "results", "items"),
            parse_item=ChannelTalkDocumentNavNodeMetadata.from_api_payload,
        )
        return cls(nav_nodes=items, next_page_token=next_page_token)


class ChannelTalkDocumentMetadataSyncRequest(BaseModel):
    channel_id: str

    @field_validator("channel_id")
    @classmethod
    def validate_channel_id(cls, value: str) -> str:
        return require_text(value, "channel_id")

    def to_core_request(self) -> MetadataSyncRequest:
        return MetadataSyncRequest(
            connector=ConnectorKey.CHANNEL_TALK,
            tenant_id=self.channel_id,
        )


class ChannelTalkDocumentMetadataSyncResult(BaseModel):
    connector: ConnectorKey
    channel_id: str
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
            space_synced=(space_step.synced_count > 0) if space_step else False,
            authors_synced=authors_step.synced_count if authors_step else 0,
            nav_nodes_synced=nav_step.synced_count if nav_step else 0,
        )


def _unwrap_payload(payload: Any, key: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be an object")
    nested = payload.get(key)
    if isinstance(nested, Mapping):
        return nested
    return payload


def _parse_page(
    payload: Any,
    *,
    item_keys: tuple[str, ...],
    parse_item,
) -> tuple[list[Any], str | None]:
    if isinstance(payload, list):
        return [parse_item(item) for item in payload], None
    if not isinstance(payload, Mapping):
        raise ValueError("page payload must be an object or list")
    reader = _PayloadReader(payload)
    items: list[Any] = []
    for key in item_keys:
        raw_items = payload.get(key)
        if isinstance(raw_items, list):
            items = [parse_item(item) for item in raw_items]
            break
    return items, reader.text("next", "nextPageToken", "next_page_token", "since")


def _required_reader_text(
    reader: "_PayloadReader",
    error_message: str,
    *keys: str,
) -> str:
    value = reader.text(*keys)
    if value is None:
        raise ValueError(error_message)
    return value


def _validation_field_name(info: ValidationInfo) -> str:
    return info.field_name or "field"


class _PayloadReader:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = payload

    def text(self, *keys: str) -> str | None:
        for key in keys:
            value = self.payload.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    def integer(self, *keys: str) -> int | None:
        for key in keys:
            value = self.payload.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            try:
                return int(float(text))
            except (TypeError, ValueError):
                continue
        return None

    @classmethod
    def parse_datetime(cls, value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is not None:
                return value
            return value.replace(tzinfo=timezone.utc)
        text = str(value).strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            return parsed
        return parsed.replace(tzinfo=timezone.utc)
