from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import ValidationInfo
from pydantic import field_validator
from pydantic import model_validator

from catchup.connector_core.document_format.base import DocumentBaseMetadata
from catchup.utils.validation import require_text


class JiraAttachmentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str | None = None
    url: str | None = None
    mime_type: str | None = None
    type: str | None = None


class JiraIssueMetadata(BaseModel):
    """Typed Jira issue metadata"""
    # TODO : Langchain Postgres v2 마이그레이션 시점에 Flat 형식 제거

    model_config = ConfigDict(extra="forbid")

    entity_type: Literal["issue"] = "issue"
    issue_key: str
    issue_id: str | None = None
    title: str
    project_key: str
    issue_type: str | None = None
    status: str | None = None
    priority: str | None = None
    assignee: str | None = None
    assignee_email: str | None = None
    reporter: str | None = None
    resolved_at: datetime | None = None
    parent_key: str | None = None
    subtask_keys: tuple[str, ...] = ()
    sprint_id: int | str | None = None
    sprint_name: str | None = None
    components: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()
    fix_versions: tuple[str, ...] = ()
    inline_attachments: tuple[JiraAttachmentMetadata, ...] = ()
    attachments: tuple[JiraAttachmentMetadata, ...] = ()

    @field_validator("issue_key", "title", "project_key")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")

    @field_validator("subtask_keys", "components", "labels", "fix_versions")
    @classmethod
    def _validate_text_tuple(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(item for item in value if item)

    def to_flat_metadata(self) -> dict[str, object]:
        metadata: dict[str, object] = {
            "entity_type": self.entity_type,
            "issue_key": self.issue_key,
            "issue_id": self.issue_id,
            "title": self.title,
            "project_key": self.project_key,
            "issue_type": self.issue_type,
            "status": self.status,
            "priority": self.priority,
            "assignee": self.assignee,
            "assignee_email": self.assignee_email,
            "reporter": self.reporter,
            "resolved_at": self.resolved_at.isoformat()
            if self.resolved_at is not None
            else None,
            "parent_key": self.parent_key,
            "subtask_keys": list(self.subtask_keys),
            "sprint_id": self.sprint_id,
            "sprint_name": self.sprint_name,
            "components": list(self.components),
            "labels": list(self.labels),
            "fix_versions": list(self.fix_versions),
            "inline_attachments": [
                item.model_dump(mode="json", exclude_none=True)
                for item in self.inline_attachments
            ],
            "attachments": [
                item.model_dump(mode="json", exclude_none=True)
                for item in self.attachments
            ],
        }
        return metadata


class JiraIssueLogicalMetadata(BaseModel):
    """Jira logical metadata contract with flat storage compatibility."""

    model_config = ConfigDict(extra="forbid")

    base: DocumentBaseMetadata
    issue: JiraIssueMetadata

    @model_validator(mode="after")
    def _validate_identity(self) -> "JiraIssueLogicalMetadata":
        if self.base.source != "jira":
            raise ValueError("base.source must be jira")
        if self.base.record_id != self.issue.issue_key:
            raise ValueError("base.record_id must match issue.issue_key")
        return self

    def to_storage_metadata(self) -> dict[str, object]:
        base_storage = self.base.model_dump(mode="python")
        for key in ("created_at", "updated_at", "synced_at"):
            value = base_storage.get(key)
            if isinstance(value, datetime):
                base_storage[key] = value.isoformat()
        return {
            **base_storage,
            **self.issue.to_flat_metadata(),
        }
