from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query

from catchup.components.vector_db.pgvector.pgvector import PGVectorService
from catchup.db.models import SourceType
from catchup.rag.schemas.sources import BaseSource
from catchup.server.search.dependencies import get_search_service
from catchup.server.search.schemas import KeywordSearchResponse

router = APIRouter(prefix="/api/v1/search", tags=["Search Service"])


@router.get(
    path="/hybrid",
    response_model=KeywordSearchResponse,
    description="하이브리드(Vector + Weighted Keyword) 수동 검색 API",
)
async def hybrid_search(
    keyword: Annotated[str, Query(description="검색어")],
    limit: Annotated[int, Query(ge=1, le=100, description="최대 결과 수")] = 20,
    offset: Annotated[int, Query(ge=0, description="오프셋")] = 0,
    tool_filters: Annotated[list[SourceType], Query(description="협업 툴 검색 필터")] = [],
    service: PGVectorService = Depends(get_search_service),
) -> KeywordSearchResponse:
    """
    Semantic Search와 Weighted Keyword Search를 결합한 하이브리드 검색.
    """
    docs = await service.hybrid_search(
        query=keyword,
        k=limit,
        tool_filters=tool_filters,
        offset=offset,
        # keyword_tokens는 내부적으로 [query]로 처리됨
    )

    results = []
    for i, doc in enumerate(docs):
        # Weighted RRF 결과는 doc.metadata["score"]에 저장됨
        source = BaseSource.from_document(
            index=i + 1,
            doc=doc,
            relevance_score=doc.metadata.get("score", 0.0),
        )
        results.append(source)

    return KeywordSearchResponse(
        results=results,
        total=len(results),
    )
