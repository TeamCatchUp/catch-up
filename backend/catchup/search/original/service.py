from __future__ import annotations

from sqlalchemy.orm import Session

from catchup.search.original.ids import parse_original_document_id
from catchup.search.original.registry import OriginalResolverRegistry
from catchup.server.search.schemas import OriginalContentRequest
from catchup.server.search.schemas import OriginalContentResponse
from catchup.server.search.schemas import OriginalFileUrlRequest
from catchup.server.search.schemas import OriginalFileUrlResponse


class OriginalSearchService:
    def __init__(self, *, registry: OriginalResolverRegistry) -> None:
        self._registry = registry

    async def get_original(
        self,
        *,
        request: OriginalContentRequest,
        db: Session | None = None,
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

    async def get_original_file_url(
        self,
        *,
        request: OriginalFileUrlRequest,
        db: Session | None = None,
    ) -> OriginalFileUrlResponse:
        ref = parse_original_document_id(
            connector=request.connector,
            document_id=request.document_id,
        )
        resolver = self._registry.get(
            connector=ref.connector,
            entity_type=ref.entity_type,
        )
        return await resolver.resolve_file_url(
            request=request,
            ref=ref,
            db=db,
        )
