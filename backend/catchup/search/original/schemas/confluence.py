from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from catchup.db.models import SourceType
from catchup.search.original.schemas.base import OriginalContent
from catchup.server.search.schemas import OriginalContentResponse


class ConfluenceOriginalContentType(StrEnum):
    STORAGE = "storage"


class ConfluenceOriginalItemType(StrEnum):
    DOCUMENT = "document"
    COMMENT = "comment"


class ConfluenceOriginalCommentType(StrEnum):
    FOOTER = "footer"
    INLINE = "inline"


class ConfluenceOriginalAuthor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    name: str | None = None
    email: str | None = None
    avatar_url: str | None = None


class ConfluenceOriginalContent(OriginalContent):
    content_type: ConfluenceOriginalContentType


class ConfluenceOriginalAttachment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_key: str
    id: str
    name: str
    media_type: str | None = None
    size: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ConfluenceOriginalItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: ConfluenceOriginalItemType
    contents: list[ConfluenceOriginalContent]
    author: ConfluenceOriginalAuthor | None = None
    comment_type: ConfluenceOriginalCommentType | None = None
    parent_id: str | None = None
    resolution_status: str | None = None
    inline_original_selection: str | None = None
    inline_marker_ref: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ConfluenceOriginalContentResponse(OriginalContentResponse):
    connector: Literal[SourceType.CONFLUENCE]
    entity_type: Literal["page", "blogpost"]
    items: list[ConfluenceOriginalItem] = Field(default_factory=list)
