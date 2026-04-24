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
    path="/keyword",
    response_model=KeywordSearchResponse,
    description="키워드 기반 수동 검색 API",
)
async def keyword_search(
    keyword: Annotated[str, Query(description="검색어")],
    limit: Annotated[int, Query(ge=1, le=100, description="최대 결과 수")] = 20,
    offset: Annotated[int, Query(ge=0, description="오프셋")] = 0,
    tool_filters: Annotated[list[SourceType], Query(description="협업 툴 검색 필터")] = [],
    # start_date: Annotated[datetime | None, Query(description="시작 날짜")] = None,
    # end_date: Annotated[datetime | None, Query(description="종료 날짜")] = None,
    service: PGVectorService = Depends(get_search_service),
) -> KeywordSearchResponse:

    docs = service.manual_keyword_search(
        keyword=keyword,
        limit=limit,
        offset=offset,
        integrations=tool_filters,
        # start_date=start_date,
        # end_date=end_date,
    )


    # Document -> SourceResponse 변환
    results = []
    for i, doc in enumerate(docs):
        # BaseSource.from_document는 index, doc, score 등을 인자로 받음
        source = BaseSource.from_document(
            index=i + 1,
            doc=doc,
            relevance_score=doc.metadata.get("relevance_score", 0.0),
        )
        results.append(source)

    return KeywordSearchResponse(
        results=results,
        total=len(
            results
        ),  # 실제 전체 카운트는 별도 쿼리가 필요할 수 있으나 현재는 결과 수 반환
    )
