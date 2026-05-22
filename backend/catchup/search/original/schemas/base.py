from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

"""
JSON Payload Example
{
  "items": [
    {
      "id": "message-id",
      "type": "message",
      "visibility": "public",
      "author": {},
      "contents": [
        { "content_type": "text", "payload": {} },
        { "content_type": "file", "payload": {} }
      ],
      "created_at": "..."
    }
  ]
}
"""

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
