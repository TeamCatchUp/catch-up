from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session

from catchup.search.original.ids import OriginalDocumentRef
from catchup.search.original.schemas import OriginalSearchRequest
from catchup.search.original.schemas import OriginalSearchResponse


class OriginalContentResolver(Protocol):
    async def resolve(
        self,
        *,
        request: OriginalSearchRequest,
        ref: OriginalDocumentRef,
        db: Session,
    ) -> OriginalSearchResponse: ...

