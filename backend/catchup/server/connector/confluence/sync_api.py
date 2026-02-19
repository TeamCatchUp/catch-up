"""
Confluence Sync API

Confluence 데이터 동기화 API 엔드포인트.
전체 동기화, 상태 조회 기능 제공.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from catchup.connectors.confluence.factory import create_confluence_ingestion_service
from catchup.db.confluence import sync_repository as confluence_sync
from catchup.db.dependencies import get_db

logger = logging.getLogger(__name__)


# ================================================================
# Request/Response Schemas
# ================================================================

class ConfluenceSyncRequest(BaseModel):
    """동기화 요청"""
    space_keys: list[str] | None = Field(
        None,
        description="동기화할 Space Key 목록 (None이면 전체)",
        examples=[["ENG", "DEV"]],
    )


class SyncResultDetail(BaseModel):
    """엔티티별 동기화 결과"""
    synced: int = 0
    errors: int = 0


class ConfluenceSyncResponse(BaseModel):
    """동기화 응답"""
    status: str
    message: str
    cloud_id: str | None = None
    results: dict[str, SyncResultDetail] | None = Field(
        None,
        description="엔티티별 동기화 결과 (pages, blogposts)",
    )


class ConfluenceSyncStatusResponse(BaseModel):
    """동기화 상태 응답"""
    cloud_id: str
    space_key: str
    entity_type: str
    last_sync_status: str | None
    last_successful_sync_at: str | None
    synced_entities: int
    total_entities: int
    last_sync_error: str | None


# ================================================================
# Router
# ================================================================

router = APIRouter(prefix="/api/v1/confluence/sync", tags=["confluence-sync"])


# ================================================================
# Endpoints
# ================================================================

@router.post("/full", response_model=ConfluenceSyncResponse)
async def trigger_full_sync(
    request: ConfluenceSyncRequest,
    cloud_id: str = Query(..., description="Atlassian Cloud ID"),
    db: Session = Depends(get_db),
):
    """
    전체 동기화 트리거

    지정된 Space(또는 전체)의 모든 Confluence Page/BlogPost를 PGVector에 동기화.
    대량의 데이터가 있을 경우 시간이 오래 걸릴 수 있습니다.
    """
    try:
        service = await create_confluence_ingestion_service(db, cloud_id)
        result = await service.full_sync(
            db=db,
            space_keys=request.space_keys,
        )

        summary_parts = []
        if result["pages"]["synced"] > 0 or result["pages"]["errors"] > 0:
            summary_parts.append(f"Pages={result['pages']['synced']}")
        if result["blogposts"]["synced"] > 0 or result["blogposts"]["errors"] > 0:
            summary_parts.append(f"BlogPosts={result['blogposts']['synced']}")

        message = (
            f"전체 동기화 완료: {', '.join(summary_parts)}"
            if summary_parts
            else "동기화할 데이터가 없습니다"
        )

        return ConfluenceSyncResponse(
            status="success",
            message=message,
            cloud_id=cloud_id,
            results={
                "pages": SyncResultDetail(**result["pages"]),
                "blogposts": SyncResultDetail(**result["blogposts"]),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CONFLUENCE][SYNC] Full sync error: cloud_id={cloud_id}, error={e}")
        raise HTTPException(
            status_code=500,
            detail=f"동기화 중 오류가 발생했습니다: {str(e)}",
        )



@router.get("/status", response_model=list[ConfluenceSyncStatusResponse])
async def get_sync_status(
    cloud_id: str = Query(..., description="Atlassian Cloud ID"),
    db: Session = Depends(get_db),
):
    """
    동기화 상태 조회

    해당 Confluence 인스턴스의 Space별/Entity별 동기화 상태를 반환.
    """
    sync_states = confluence_sync.get_all_sync_states(db, cloud_id)

    if not sync_states:
        return []

    return [
        ConfluenceSyncStatusResponse(
            cloud_id=state.cloud_id,
            space_key=state.space_key,
            entity_type=state.entity_type,
            last_sync_status=state.last_sync_status,
            last_successful_sync_at=(
                state.last_successful_sync_at.isoformat()
                if state.last_successful_sync_at
                else None
            ),
            synced_entities=state.synced_entities or 0,
            total_entities=state.total_entities or 0,
            last_sync_error=state.last_sync_error,
        )
        for state in sync_states
    ]
