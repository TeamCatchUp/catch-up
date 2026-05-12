from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query

from catchup.auth.dependencies import get_current_user
from catchup.components.vector_db.pgvector.pgvector import PGVectorService
from catchup.db.models import SourceType
from catchup.db.models import User
from catchup.search.service import ManualSearchService
from catchup.server.search.dependencies import get_manual_search_service
from catchup.server.search.dependencies import get_search_service
from catchup.server.search.schemas import ManualSearchResponse

router = APIRouter(prefix="/api/v1/search", tags=["Search Service"])


@router.get(
    path="/hybrid",
    response_model=ManualSearchResponse,
    description="하이브리드(Vector + Weighted Keyword) 수동 검색 API",
)
async def hybrid_search(
    keyword: Annotated[str, Query(description="검색어")],
    limit: Annotated[int, Query(ge=1, le=100, description="최대 결과 수")] = 20,
    offset: Annotated[int, Query(ge=0, description="오프셋")] = 0,
    tool_filters: Annotated[
        list[SourceType] | None, Query(description="협업 툴 검색 필터")
    ] = None,
    vector_db_service: PGVectorService = Depends(get_search_service),
    current_user: User = Depends(get_current_user),
    search_service: ManualSearchService = Depends(get_manual_search_service),
) -> ManualSearchResponse:
    results = await search_service.search(
        user=current_user,
        keyword=keyword,
        limit=limit,
        offset=offset,
        tool_filters=tool_filters,
        vector_db_service=vector_db_service,
    )
    return ManualSearchResponse(results=results, total=len(results))
