from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session

from catchup.search.original.ids import OriginalDocumentRef
from catchup.server.search.schemas import OriginalContentRequest
from catchup.server.search.schemas import OriginalContentResponse
from catchup.server.search.schemas import OriginalFileUrlRequest
from catchup.server.search.schemas import OriginalFileUrlResponse


class OriginalContentResolver(Protocol):
    async def resolve(
        self,
        *,
        request: OriginalContentRequest,
        ref: OriginalDocumentRef,
        db: Session | None = None,
    ) -> OriginalContentResponse: ...

    async def resolve_file_url(
        self,
        *,
        request: OriginalFileUrlRequest,
        ref: OriginalDocumentRef,
        db: Session | None = None,
    ) -> OriginalFileUrlResponse: ...
