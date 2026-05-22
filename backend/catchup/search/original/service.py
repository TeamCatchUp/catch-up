from __future__ import annotations

from sqlalchemy.orm import Session

from catchup.search.original.ids import parse_original_document_id
from catchup.search.original.registry import OriginalResolverRegistry
from catchup.server.search.schemas import OriginalContentRequest
from catchup.server.search.schemas import OriginalContentResponse


class OriginalSearchService:
    def __init__(self, *, registry: OriginalResolverRegistry) -> None:
        self._registry = registry

    async def get_original(
        self,
        *,
        request: OriginalContentRequest,
        db: Session,
    ) -> OriginalContentResponse:
        ref = parse_original_document_id(
            connector=request.connector,
            document_id=request.document_id,
        )
        resolver = self._registry.get(
            connector=ref.connector,
            entity_type=ref.entity_type,
        )
        return await resolver.resolve(
            request=request,
            ref=ref,
            db=db,
        )
