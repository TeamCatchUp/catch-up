"""
Jira Sync API

Jira 데이터 동기화 API 엔드포인트.
전체/증분 동기화, 상태 조회 기능 제공.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.connectors.jira.auth import get_jira_oauth_service, JiraOAuthService
from catchup.connectors.jira.service import JiraIngestionService
from catchup.db.dependencies import get_db
from catchup.db.jira import oauth_repository as jira_crud
from catchup.db.models import JiraSyncState

logger = logging.getLogger(__name__)


# ================================================================
# Request/Response Schemas
# ================================================================

class SyncRequest(BaseModel):
    """동기화 요청"""
    project_keys: list[str] | None = Field(
        None,
        description="동기화할 프로젝트 키 목록 (None이면 전체)",
        examples=[["CATCH", "PROJ"]],
    )
    sync_issues: bool = Field(True, description="이슈/에픽 동기화 여부")
    sync_projects: bool = Field(True, description="프로젝트 동기화 여부")
    sync_sprints: bool = Field(True, description="스프린트 동기화 여부 (Agile API 필요)")


class SyncResultDetail(BaseModel):
    """엔티티별 동기화 결과"""
    synced: int = 0
    errors: int = 0


class SyncResponse(BaseModel):
    """동기화 응답"""
    status: str
    message: str
    cloud_id: str | None = None
    results: dict[str, SyncResultDetail] | None = Field(
        None,
        description="엔티티별 동기화 결과 (issues, epics, projects, sprints)",
    )


class SyncStatusResponse(BaseModel):
    """동기화 상태 응답"""
    cloud_id: str
    entity_type: str
    last_sync_status: str | None
    last_successful_sync_at: str | None
    synced_entities: int
    last_sync_error: str | None


# ================================================================
# Router
# ================================================================

router = APIRouter(prefix="/api/v1/jira/sync", tags=["jira-sync"])


# ================================================================
# Helper Functions
# ================================================================

async def _run_full_sync(
    cloud_id: str,
    access_token: str,
    site_url: str,
    db: Session,
    project_keys: list[str] | None = None,
    sync_issues: bool = True,
    sync_projects: bool = True,
    sync_sprints: bool = True,
) -> dict[str, Any]:
    """전체 동기화 실행"""
    try:
        service = JiraIngestionService(cloud_id, access_token, site_url)
        await service.initialize()
        return await service.full_sync(
            db,
            project_keys=project_keys,
            sync_issues=sync_issues,
            sync_projects=sync_projects,
            sync_sprints=sync_sprints,
        )
    except Exception as e:
        logger.error(f"Full sync failed for cloud_id={cloud_id}: {e}")
        raise


async def _run_incremental_sync(
    cloud_id: str,
    access_token: str,
    site_url: str,
    db: Session,
) -> dict[str, Any]:
    """증분 동기화 실행"""
    try:
        service = JiraIngestionService(cloud_id, access_token, site_url)
        await service.initialize()
        return await service.incremental_sync(db)
    except Exception as e:
        logger.error(f"Incremental sync failed for cloud_id={cloud_id}: {e}")
        raise


# ================================================================
# Endpoints
# ================================================================

@router.post("/full", response_model=SyncResponse)
async def trigger_full_sync(
    request: SyncRequest,
    cloud_id: str = Query(..., description="Jira Cloud ID"),
    db: Session = Depends(get_db),
    jira_service: JiraOAuthService = Depends(get_jira_oauth_service),
):
    """
    전체 동기화 트리거

    지정된 프로젝트(또는 전체)의 모든 Jira 데이터를 PGVector에 동기화.
    대량의 데이터가 있을 경우 시간이 오래 걸릴 수 있습니다.
    """
    token_record = jira_crud.get_jira_token_by_cloud_id(db, cloud_id)
    if not token_record:
        raise HTTPException(
            status_code=404,
            detail=f"Jira 연결을 찾을 수 없습니다: {cloud_id}",
        )

    try:
        access_token = await jira_service.get_valid_access_token(db, token_record)
        site_url = token_record.site_url or ""

        result = await _run_full_sync(
            cloud_id=cloud_id,
            access_token=access_token,
            site_url=site_url,
            db=db,
            project_keys=request.project_keys,
            sync_issues=request.sync_issues,
            sync_projects=request.sync_projects,
            sync_sprints=request.sync_sprints,
        )

        summary_parts = []
        if result["issues"]["synced"] > 0 or result["issues"]["errors"] > 0:
            summary_parts.append(f"Issues={result['issues']['synced']}")
        if result["epics"]["synced"] > 0 or result["epics"]["errors"] > 0:
            summary_parts.append(f"Epics={result['epics']['synced']}")
        if result["projects"]["synced"] > 0 or result["projects"]["errors"] > 0:
            summary_parts.append(f"Projects={result['projects']['synced']}")
        if result["sprints"]["synced"] > 0 or result["sprints"]["errors"] > 0:
            summary_parts.append(f"Sprints={result['sprints']['synced']}")

        message = f"전체 동기화 완료: {', '.join(summary_parts)}" if summary_parts else "동기화할 데이터가 없습니다"

        return SyncResponse(
            status="success",
            message=message,
            cloud_id=cloud_id,
            results={
                "issues": SyncResultDetail(**result["issues"]),
                "epics": SyncResultDetail(**result["epics"]),
                "projects": SyncResultDetail(**result["projects"]),
                "sprints": SyncResultDetail(**result["sprints"]),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Full sync error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"동기화 중 오류가 발생했습니다: {str(e)}",
        )


@router.post("/incremental", response_model=SyncResponse)
async def trigger_incremental_sync(
    cloud_id: str = Query(..., description="Jira Cloud ID"),
    db: Session = Depends(get_db),
    jira_service: JiraOAuthService = Depends(get_jira_oauth_service),
):
    """
    증분 동기화 트리거

    마지막 동기화 이후 업데이트된 데이터만 동기화.
    이전 동기화 기록이 없으면 전체 동기화로 전환됩니다.
    """
    token_record = jira_crud.get_jira_token_by_cloud_id(db, cloud_id)
    if not token_record:
        raise HTTPException(
            status_code=404,
            detail=f"Jira 연결을 찾을 수 없습니다: {cloud_id}",
        )

    try:
        access_token = await jira_service.get_valid_access_token(db, token_record)
        site_url = token_record.site_url or ""

        result = await _run_incremental_sync(
            cloud_id=cloud_id,
            access_token=access_token,
            site_url=site_url,
            db=db,
        )

        return SyncResponse(
            status="success",
            message=f"증분 동기화 완료: Issues={result['issues']}, Epics={result['epics']}",
            cloud_id=cloud_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Incremental sync error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"동기화 중 오류가 발생했습니다: {str(e)}",
        )


@router.get("/status", response_model=list[SyncStatusResponse])
async def get_sync_status(
    cloud_id: str = Query(..., description="Jira Cloud ID"),
    db: Session = Depends(get_db),
):
    """
    동기화 상태 조회

    해당 Jira 인스턴스의 엔티티별 동기화 상태를 반환.
    """
    stmt = select(JiraSyncState).where(JiraSyncState.cloud_id == cloud_id)
    result = db.execute(stmt)
    sync_states = result.scalars().all()

    if not sync_states:
        return []

    return [
        SyncStatusResponse(
            cloud_id=state.cloud_id,
            entity_type=state.entity_type,
            last_sync_status=state.last_sync_status,
            last_successful_sync_at=(
                state.last_successful_sync_at.isoformat()
                if state.last_successful_sync_at
                else None
            ),
            synced_entities=state.synced_entities or 0,
            last_sync_error=state.last_sync_error,
        )
        for state in sync_states
    ]
