from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import field_validator


def _require_text(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


class DocumentBaseMetadata(BaseModel):
    """
    Shared logical base for all pg_embedding cmetadata documents.

    Connector-specific contracts can constrain `source` and any other
    invariants at their own validation boundary.
    """

    model_config = ConfigDict(extra="forbid")

    source: str
    record_id: str
    url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    synced_at: datetime
    contextual_content: str

    @field_validator("source", "record_id", "contextual_content")
    @classmethod
    def _validate_required_text(cls, value: str, info) -> str:
        return _require_text(value, info.field_name)
