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


class JiraIssueUserMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_user_id: str | None = None
    internal_user_id: str | None = None


class JiraIssueSprintMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    state: str | None = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return require_text(value, "name")


class JiraIssueMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_id: str
    type: str | None = None
    status: str | None = None
    status_category: str | None = None
    priority: str | None = None
    resolution: str | None = None
    assignee: JiraIssueUserMetadata | None = None
    reporter: JiraIssueUserMetadata | None = None
    creator: JiraIssueUserMetadata | None = None
    resolved_at: datetime | None = None
    due_date: str | None = None
    parent_key: str | None = None
    parent_name: str | None = None
    subtask_keys: list[str] = Field(default_factory=list)
    sprint: JiraIssueSprintMetadata | None = None
    story_points: float | None = None
    components: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    fix_versions: list[str] = Field(default_factory=list)
    affects_versions: list[str] = Field(default_factory=list)
    time_spent_seconds: int | None = None

    @field_validator("issue_id")
    @classmethod
    def _validate_required_text(cls, value: str, info) -> str:
        return require_text(value, info.field_name)


class JiraIssueDataPart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type", "text")
    @classmethod
    def _validate_required_text(cls, value: str, info) -> str:
        return require_text(value, info.field_name)


class JiraIssueData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parts: list[JiraIssueDataPart] = Field(default_factory=list)


class JiraIssueVectorRecord(BaseModel):
    """v2 vector-store row contract for a Jira issue."""

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
    data: JiraIssueData = Field(default_factory=JiraIssueData)
    url: str
    created_at: datetime
    updated_at: datetime
    synced_at: datetime
    jira_issue: JiraIssueMetadata

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
            "jira_issue": self.jira_issue.model_dump(
                mode="json",
                exclude_none=False,
            )
        }

    def to_db_values(self) -> dict[str, Any]:
        values = self.model_dump(
            mode="json",
            exclude={"jira_issue"},
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
        metadata["jira_issue"] = values["langchain_metadata"]["jira_issue"]
        return Document(
            id=self.langchain_id,
            page_content=self.content,
            metadata=metadata,
        )
