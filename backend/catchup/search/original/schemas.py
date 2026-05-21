from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from catchup.db.models import SourceType


class OriginalSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector: SourceType = Field(..., description="원문 조회 대상 connector")
    document_id: str = Field(..., min_length=1, description="검색 결과 document id")
    next_cursor: str | None = Field(
        default=None,
        description="추가 페이지 조회용 cursor",
    )


class OriginalAuthor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    name: str | None = None
    type: str | None = None
    email: str | None = None
    avatar_url: str | None = None


class OriginalBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["plain_text", "markdown", "html"] = "plain_text"
    text: str = ""


class OriginalItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["message", "comment", "description", "section", "event"]
    author: OriginalAuthor | None = None
    body: OriginalBody
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OriginalSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector: SourceType
    entity_type: str
    document_id: str
    title: str
    url: str | None = None
    items: list[OriginalItem] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    next_cursor: str | None = None
    fetched_at: datetime
