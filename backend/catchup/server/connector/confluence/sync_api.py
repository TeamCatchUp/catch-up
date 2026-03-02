"""
Confluence Sync API

Confluence 데이터 동기화 API 엔드포인트.
전체 동기화, 상태 조회 기능 제공.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from catchup.auth.dependencies import require_admin_user
from catchup.connectors.confluence.factory import create_confluence_ingestion_service
from catchup.connectors.confluence.schemas import ConfluenceSpaceResponse
from catchup.db.confluence import domain_repository as confluence_entities
from catchup.db.confluence import sync_repository as confluence_sync
from catchup.db.dependencies import get_db
from catchup.db.models import User

logger = logging.getLogger(__name__)


# ================================================================
# Request/Response Schemas
# ================================================================

class ConfluenceSyncRequest(BaseModel):
    """동기화 요청"""
    cloud_id: str = Field(..., description="Atlassian Cloud ID")
    space_keys: list[str] | None = Field(
        None,
        description="동기화할 Space Key 목록 (None이면 전체)",
        examples=[["ENG", "DEV"]],
    )
    sync_days: int | None = Field(
        None,
        description="수집 범위 (일), 미지정 시 기본값 사용",
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


class AccessibleSpaceItem(BaseModel):
    """접근 가능한 Space 요약"""
    space_key: str
    space_name: str


class AccessibleSpacesResponse(BaseModel):
    """접근 가능한 Space 목록 응답"""
    cloud_id: str
    total_spaces: int
    spaces: list[AccessibleSpaceItem]


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
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
):
    """
    전체 동기화 트리거

    지정된 Space(또는 전체)의 모든 Confluence Page/BlogPost를 PGVector에 동기화.
    대량의 데이터가 있을 경우 시간이 오래 걸릴 수 있습니다.
    """
    cloud_id = request.cloud_id
    try:
        service = await create_confluence_ingestion_service(db, cloud_id)
        result = await service.full_sync(
            db=db,
            space_keys=request.space_keys,
            sync_days=request.sync_days,
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
    
@router.post("/incremental", response_model = ConfluenceSyncResponse)
async def trigger_incremental_sync(
    cloud_id: str = Query(..., description="Atlassian Cloud ID"),
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
):
    """
    Sync Status가 있는 Space Id를 대상으로 마지막 동기화 시점 이후 수정/생성된 Page, Blogpost 동기화
    """
    try:
        service = await create_confluence_ingestion_service(db, cloud_id)
        result = await service.incremental_sync(db=db)

        summary_parts = []
        if result["pages"]["synced"] > 0 or result["pages"]["errors"] > 0:
            summary_parts.append(
                f"Pages={result['pages']['synced']}(skipped={result['pages']['skipped']})"
            )
        if result["blogposts"]["synced"] > 0 or result["blogposts"]["errors"] > 0:
            summary_parts.append(
                f"BlogPosts={result['blogposts']['synced']}(skipped={result['blogposts']['skipped']})"
            )
        
        message = (
            f"증분 동기화 완료: {', '.join(summary_parts)}"
            if summary_parts
            else "변경된 데이터가 없습니다"
        )

        return ConfluenceSyncResponse(
            status="success",
            message=message,
            cloud_id=cloud_id,
            results={
                "pages": SyncResultDetail(
                    synced=result["pages"]["synced"],
                    errors=result["pages"]["errors"],
                ),
                "blogposts": SyncResultDetail(
                    synced=result["blogposts"]["synced"],
                    errors=result["blogposts"]["errors"],
                ),
            },
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[CONFLUENCE][INCREMENTAL SYNC] Failed: cloud_id = {cloud_id}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"증분 동기화 중 오류가 발생했습니다: {str(e)}",
        )

@router.get("/accessible/spaces", response_model=AccessibleSpacesResponse)
async def list_accessible_spaces(
    cloud_id: str = Query(..., description="Atlassian Cloud ID"),
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
):
    """
    Cloud 기준 접근 가능한 Space를 실시간 조회 후 DB 스냅샷 동기화
    """
    try:
        service = await create_confluence_ingestion_service(db, cloud_id)
        raw_spaces = await service.client.get_spaces(space_type=None, status="current")

        deduped_by_space_id: dict[str, dict] = {}
        for raw_space in raw_spaces:
            try:
                space = ConfluenceSpaceResponse.model_validate(raw_space)
            except Exception:
                logger.debug(
                    "[CONFLUENCE][FULL SYNC][ACCESSIBLE] Skip invalid space payload: cloud_id=%s",
                    cloud_id,
                )
                continue

            description_text = ""
            if space.description:
                description_text = space.description.get_plain_text()

            deduped_by_space_id[space.id] = {
                "cloud_id": cloud_id,
                "space_id": space.id,
                "space_key": space.key,
                "space_name": space.name,
                "space_type": space.type,
                "status": space.status,
                "homepage_id": space.homepage_id,
                "description": description_text[:2000] if description_text else None,
            }

        spaces_payload = list(deduped_by_space_id.values())
        sync_result = confluence_entities.sync_spaces_snapshot(
            db=db,
            cloud_id=cloud_id,
            spaces=spaces_payload,
        )

        spaces = [
            AccessibleSpaceItem(space_key=item["space_key"], space_name=item["space_name"])
            for item in spaces_payload
        ]
        spaces.sort(key=lambda item: item.space_key)

        logger.info(
            "[CONFLUENCE][FULL SYNC][ACCESSIBLE] Accessible spaces synced: cloud_id=%s, fetched=%s, upserted=%s, deleted=%s",
            cloud_id,
            len(spaces),
            sync_result["upserted"],
            sync_result["deleted"],
        )

        return AccessibleSpacesResponse(
            cloud_id=cloud_id,
            total_spaces=len(spaces),
            spaces=spaces,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[CONFLUENCE][FULL SYNC][ACCESSIBLE] list_accessible_spaces failed: cloud_id=%s, error=%s",
            cloud_id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="접근 가능한 Space 조회 중 오류가 발생했습니다.",
        )


@router.get("/status", response_model=list[ConfluenceSyncStatusResponse])
async def get_sync_status(
    cloud_id: str = Query(..., description="Atlassian Cloud ID"),
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_admin_user),
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
