from datetime import datetime
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from catchup.audit.actions import ManualSearchAction
from catchup.audit.metadata import ManualSearchAuditMetadata
from catchup.audit.utils import audit_log
from catchup.auth.dependencies import get_current_user
from catchup.components.vector_db.pgvector.pgvector import PGVectorService
from catchup.db.dependencies import get_db
from catchup.db.manual_search_history import save_search_query
from catchup.db.models import SourceType
from catchup.db.models import User
from catchup.search.original.ids import OriginalDocumentIdError
from catchup.search.original.registry import OriginalResolverNotFoundError
from catchup.search.original.resolvers.channel_talk import ChannelTalkOriginalError
from catchup.search.original.schemas import OriginalSearchRequest
from catchup.search.original.schemas import OriginalSearchResponse
from catchup.search.original.service import OriginalSearchService
from catchup.search.service import ManualSearchService
from catchup.server.search.dependencies import get_manual_search_service
from catchup.server.search.dependencies import get_original_search_service
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
    start_date: Annotated[
        datetime | None,
        Query(
            description="검색 시작 날짜 (ISO 8601, UTC). KST 기준이면 T15:00:00Z로 변환 후 전송. 없으면 전체 기간 시작."
        ),
    ] = None,
    end_date: Annotated[
        datetime | None,
        Query(
            description="검색 종료 날짜 (ISO 8601, UTC). KST 기준이면 T15:00:00Z로 변환 후 전송. 없으면 현재 시간 기준."
        ),
    ] = None,
    vector_db_service: PGVectorService = Depends(get_search_service),
    current_user: User = Depends(get_current_user),
    search_service: ManualSearchService = Depends(get_manual_search_service),
    db: Session = Depends(get_db),
) -> ManualSearchResponse:
    sr = await search_service.search(
        user=current_user,
        keyword=keyword,
        tool_filters=tool_filters,
        vector_db_service=vector_db_service,
        start_date=start_date,
        end_date=end_date,
    )

    await run_in_threadpool(save_search_query, db, current_user.id, keyword)
    db.commit()

    return ManualSearchResponse(
        results=sr.results,
        total=sr.total,
        source_distribution=sr.source_distribution,
    )


@router.post(
    path="/original",
    response_model=OriginalSearchResponse,
    description="검색 결과 document_id 기반 원문 조회 API",
)
async def get_original_search_result(
    request: OriginalSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    original_search_service: OriginalSearchService = Depends(
        get_original_search_service
    ),
) -> OriginalSearchResponse:
    _ = current_user
    try:
        return await original_search_service.get_original(
            request=request,
            db=db,
        )
    except (OriginalDocumentIdError, OriginalResolverNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ChannelTalkOriginalError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    path="/queries",
    response_model=list[ManualSearchHistoryResponse],
    description="사용자의 최근 검색어 조회 (기간별 필터링 지원, 최대 20개)",
)
async def get_search_query_history(
    period: str = Query("all", description="조회 기간: today, 7d, all"),
    current_user: User = Depends(get_current_user),
    search_service: ManualSearchService = Depends(get_manual_search_service),
) -> list[ManualSearchHistoryResponse]:
    entries = await search_service.get_search_history(
        user=current_user,
        period=period,
    )
    return [
        ManualSearchHistoryResponse(id=i + 1, query=query, created_at=searched_at)
        for i, (query, searched_at) in enumerate(entries)
    ]
