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


class GithubPrUserMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login: str
    name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    type: str | None = None
    url: str | None = None
    catchup_user_id: str | None = None

    @field_validator("login")
    @classmethod
    def _validate_login(cls, value: str) -> str:
        return require_text(value, "login")


class GithubPrLabelMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    color: str | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return require_text(value, "name")


class GithubPrMilestoneMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int
    title: str
    state: str
    due_on: datetime | None = None

    @field_validator("title", "state")
    @classmethod
    def _validate_required_text(cls, value: str, info) -> str:
        return require_text(value, info.field_name)


class GithubPrMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str
    merged_at: datetime | None = None
    closed_at: datetime | None = None
    base_ref: str
    head_ref: str
    is_draft: bool | None = None
    review_decision: str | None = None
    changed_files: int
    additions: int | None = None
    deletions: int | None = None
    author: GithubPrUserMetadata | None = None
    assignees: list[GithubPrUserMetadata] = Field(default_factory=list)
    requested_reviewers: list[GithubPrUserMetadata] = Field(default_factory=list)
    review_authors: list[GithubPrUserMetadata] = Field(default_factory=list)
    merged_by: GithubPrUserMetadata | None = None
    labels: list[GithubPrLabelMetadata] = Field(default_factory=list)
    milestone: GithubPrMilestoneMetadata | None = None

    @field_validator("state", "base_ref", "head_ref")
    @classmethod
    def _validate_required_text(cls, value: str, info) -> str:
        return require_text(value, info.field_name)


class GithubPrDataPart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type", "text")
    @classmethod
    def _validate_required_text(cls, value: str, info) -> str:
        return require_text(value, info.field_name)


class GithubPrData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parts: list[GithubPrDataPart] = Field(default_factory=list)


class GithubPrVectorRecord(BaseModel):
    """v2 vector-store row contract for a GitHub pull request."""

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
    data: GithubPrData = Field(default_factory=GithubPrData)
    url: str
    created_at: datetime
    updated_at: datetime
    synced_at: datetime
    github_pr: GithubPrMetadata

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
            "github_pr": self.github_pr.model_dump(
                mode="json",
                exclude_none=False,
            )
        }

    def to_db_values(self) -> dict[str, Any]:
        values = self.model_dump(
            mode="json",
            exclude={"github_pr"},
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
        metadata["github_pr"] = values["langchain_metadata"]["github_pr"]
        return Document(
            id=self.langchain_id,
            page_content=self.content,
            metadata=metadata,
        )
