from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from catchup.audit.actions import ManualSearchAction
from catchup.audit.metadata import ManualSearchAuditMetadata
from catchup.audit.utils import audit_log
from catchup.auth.dependencies import get_current_user
from catchup.components.vector_db.pgvector.pgvector import PGVectorService
from catchup.db.dependencies import get_db
from catchup.db.manual_search_history import get_search_queries_by_user
from catchup.db.manual_search_history import save_search_query
from catchup.db.models import SourceType
from catchup.db.models import User
from catchup.search.service import ManualSearchService
from catchup.server.schemas import BasePagination
from catchup.server.schemas import calculate_skip
from catchup.server.search.dependencies import get_manual_search_service
from catchup.server.search.dependencies import get_search_service
from catchup.server.search.schemas import ManualSearchHistoryResponse
from catchup.server.search.schemas import ManualSearchResponse

router = APIRouter(prefix="/api/v1/search", tags=["Search Service"])


@router.get(
    path="/hybrid",
    response_model=ManualSearchResponse,
    description="하이브리드(Vector + Weighted Keyword) 수동 검색 API",
)
@audit_log(
    action=ManualSearchAction.SEND_QUERY,
    metadata_factory=ManualSearchAuditMetadata.from_audit,
)
async def hybrid_search(
    keyword: Annotated[str, Query(description="검색어")],
    tool_filters: Annotated[
        list[SourceType] | None, Query(description="협업 툴 검색 필터")
    ] = None,
    vector_db_service: PGVectorService = Depends(get_search_service),
    current_user: User = Depends(get_current_user),
    search_service: ManualSearchService = Depends(get_manual_search_service),
    db: Session = Depends(get_db),
) -> ManualSearchResponse:
    results, total, source_distribution = await search_service.search(
        user=current_user,
        keyword=keyword,
        tool_filters=tool_filters,
        vector_db_service=vector_db_service,
    )

    await run_in_threadpool(save_search_query, db, current_user.id, keyword)
    db.commit()

    return ManualSearchResponse(
        results=results,
        total=total,
        source_distribution=source_distribution,
    )


@router.get(
    path="/queries",
    response_model=BasePagination[ManualSearchHistoryResponse],
    description="사용자의 수동 검색 기록 조회 (기간별 필터링 지원)",
)
def get_search_query_history(
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    size: int = Query(20, ge=1, le=100, description="페이지 크기 (1 ~ 100)"),
    period: str = Query("all", description="조회 기간: today, 7d, all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    skip = calculate_skip(page, size)

    items, total = get_search_queries_by_user(
        db=db,
        user_id=current_user.id,
        period=period,
        skip=skip,
        limit=size,
    )

    return {
        "total": total,
        "page": page,
        "size": size,
        "items": items,
    }
