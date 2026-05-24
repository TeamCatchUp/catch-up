from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from catchup.db.models import SourceType
from catchup.server.search.schemas import OriginalContentResponse

SLACK_CONVERSATIONS_REPLIES_RAW_ITEM_TYPE = "slack_conversations_replies_raw"


class SlackMessageOriginalRawItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["slack_conversations_replies_raw"] = (
        SLACK_CONVERSATIONS_REPLIES_RAW_ITEM_TYPE
    )
    raw_payload: dict[str, Any]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SlackMessageOriginalContentResponse(OriginalContentResponse):
    connector: Literal[SourceType.SLACK]
    entity_type: Literal["message"]
    items: list[SlackMessageOriginalRawItem] = Field(default_factory=list)
