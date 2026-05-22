from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class OriginalContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_type: Any
    payload: dict[str, Any] = Field(default_factory=dict)


class OriginalItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    contents: list[OriginalContent]
    created_at: datetime | None = None
    updated_at: datetime | None = None
