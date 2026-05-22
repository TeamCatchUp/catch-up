from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session

from catchup.search.original.ids import OriginalDocumentRef
from catchup.server.search.schemas import OriginalContentRequest
from catchup.server.search.schemas import OriginalContentResponse


class OriginalContentResolver(Protocol):
    async def resolve(
        self,
        *,
        request: OriginalContentRequest,
        ref: OriginalDocumentRef,
        db: Session,
    ) -> OriginalContentResponse: ...
