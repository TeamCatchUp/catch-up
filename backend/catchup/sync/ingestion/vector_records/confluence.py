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


class ConfluenceUserMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str | None = None
    display_name: str | None = None


class ConfluenceSpaceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    space_id: str | None = None


class ConfluenceHierarchyMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_page_id: str | None = None
    parent_type: str | None = None
    position: int | None = None


class ConfluenceVersionMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int | None = None
    author_id: str | None = None
    message: str | None = None
    minor_edit: bool | None = None


class ConfluenceChunkMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_index: int
    chunk_count: int
    section_hierarchy: list[str] = Field(default_factory=list)
    has_images: bool = False
    image_urls: list[str] = Field(default_factory=list)


class ConfluenceContentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = None
    space: ConfluenceSpaceMetadata = Field(default_factory=ConfluenceSpaceMetadata)
    hierarchy: ConfluenceHierarchyMetadata | None = None
    author: ConfluenceUserMetadata | None = None
    owner_id: str | None = None
    version: ConfluenceVersionMetadata = Field(
        default_factory=ConfluenceVersionMetadata
    )
    labels: list[str] = Field(default_factory=list)
    chunk: ConfluenceChunkMetadata


class ConfluenceDataPart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type", "text")
    @classmethod
    def _validate_required_text(cls, value: str, info) -> str:
        return require_text(value, info.field_name)


class ConfluenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parts: list[ConfluenceDataPart] = Field(default_factory=list)


class _ConfluenceVectorRecordBase(BaseModel):
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
    data: ConfluenceData = Field(default_factory=ConfluenceData)
    url: str
    created_at: datetime
    updated_at: datetime
    synced_at: datetime

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

    def _document_from_values(self, values: dict[str, Any], domain_key: str) -> Document:
        metadata = {
            column_name: values[column_name]
            for column_name in KNOWLEDGE_STORE_METADATA_COLUMN_NAMES
        }
        metadata[domain_key] = values["langchain_metadata"][domain_key]
        return Document(
            id=self.langchain_id,
            page_content=self.content,
            metadata=metadata,
        )


class ConfluencePageVectorRecord(_ConfluenceVectorRecordBase):
    """v2 vector-store row contract for a Confluence page chunk."""

    confluence_page: ConfluenceContentMetadata

    @property
    def langchain_metadata(self) -> dict[str, Any]:
        return {
            "confluence_page": self.confluence_page.model_dump(
                mode="json",
                exclude_none=False,
            )
        }

    def to_db_values(self) -> dict[str, Any]:
        values = self.model_dump(
            mode="json",
            exclude={"confluence_page"},
            exclude_none=False,
        )
        values["langchain_metadata"] = self.langchain_metadata
        return values

    def to_document(self) -> Document:
        return self._document_from_values(self.to_db_values(), "confluence_page")


class ConfluenceBlogpostVectorRecord(_ConfluenceVectorRecordBase):
    """v2 vector-store row contract for a Confluence blogpost chunk."""

    confluence_blogpost: ConfluenceContentMetadata

    @property
    def langchain_metadata(self) -> dict[str, Any]:
        return {
            "confluence_blogpost": self.confluence_blogpost.model_dump(
                mode="json",
                exclude_none=False,
            )
        }

    def to_db_values(self) -> dict[str, Any]:
        values = self.model_dump(
            mode="json",
            exclude={"confluence_blogpost"},
            exclude_none=False,
        )
        values["langchain_metadata"] = self.langchain_metadata
        return values

    def to_document(self) -> Document:
        return self._document_from_values(self.to_db_values(), "confluence_blogpost")
