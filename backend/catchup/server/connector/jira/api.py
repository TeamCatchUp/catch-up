import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from httpx import HTTPStatusError, RequestError
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.auth.jira.app import get_jira_oauth_service, JiraOAuthService
from catchup.auth.jira.schemas import (
    JiraInstallationStatus,
    JiraOAuthCallbackResponse,
)
from catchup.components.connectors.jira.service import JiraIngestionService
from catchup.configs.config import auth_settings
from catchup.db.dependencies import get_db
from catchup.db import jira_oauth as jira_crud
from catchup.db.models import JiraEntityType, JiraSyncState, JiraSyncStatus
from catchup.utils.redis import store_oauth_state, validate_oauth_state

logger = logging.getLogger(__name__)


# ================================================================
# Sync API Schemas
# ================================================================

class SyncRequest(BaseModel):
    """동기화 요청"""
    project_keys: list[str] | None = Field(
        None,
        description="동기화할 프로젝트 키 목록 (None이면 전체)",
        examples=[["CATCH", "PROJ"]],
    )


class SyncResponse(BaseModel):
    """동기화 응답"""
    status: str
    message: str
    cloud_id: str | None = None


class SyncStatusResponse(BaseModel):
    """동기화 상태 응답"""
    cloud_id: str
    entity_type: str
    last_sync_status: str | None
    last_successful_sync_at: str | None
    synced_entities: int
    last_sync_error: str | None


class SearchRequest(BaseModel):
    """검색 요청"""
    query: str = Field(..., description="검색 쿼리 (자연어)")
    k: int = Field(5, ge=1, le=50, description="반환할 결과 수")
    entity_type: str | None = Field(
        None,
        description="엔티티 타입 필터 (issue, epic, project, sprint)",
    )
    project_key: str | None = Field(None, description="프로젝트 필터")


class SearchResultItem(BaseModel):
    """검색 결과 항목"""
    id: str
    content: str
    metadata: dict[str, Any]


class SearchResponse(BaseModel):
    """검색 응답"""
    results: list[SearchResultItem]
    total: int

router = APIRouter(prefix="/api/v1/auth/jira", tags=["jira"])


@router.get("/install")
async def install_jira():
    """
    Jira OAuth 설치 시작
    - 관리자가 Jira Workspace에 앱을 설치하는 진입점
    """
    jira_service = get_jira_oauth_service()
    state = secrets.token_urlsafe(32)

    await store_oauth_state(state, provider="jira")

    authorization_url = jira_service.get_authorization_url(state=state)
    return RedirectResponse(url=authorization_url)


@router.get("/callback")
async def jira_oauth_callback(
    code: str,
    state: str | None = None,
    db: Session = Depends(get_db),
    jira_service: JiraOAuthService = Depends(get_jira_oauth_service),
):
    """
    Jira OAuth 콜백 처리
    - Authorization code → 토큰 교환
    - 접근 가능한 Jira 리소스 조회
    - 각 리소스별 토큰 저장
    """
    # State 파라미터 검증 (CSRF 방지)
    if not state:
        logger.warning("Jira OAuth state 파라미터 누락")
        return RedirectResponse(
            url=f"{auth_settings.FRONTEND_REDIRECT_URI}?jira_installed=false&reason=missing_state"
        )

    is_valid_state = await validate_oauth_state(state, provider="jira")
    if not is_valid_state:
        logger.warning(f"Jira OAuth state 검증 실패: {state}")
        return RedirectResponse(
            url=f"{auth_settings.FRONTEND_REDIRECT_URI}?jira_installed=false&reason=invalid_state"
        )

    # 1. Code → Token 교환
    tokens = await jira_service.exchange_code_for_tokens(code)

    # 2. Atlassian 계정 정보 조회
    user_info = await jira_service.get_user_info(tokens.access_token)

    # 3. 접근 가능한 Jira 리소스 조회
    resources = await jira_service.get_accessible_resources(tokens.access_token)

    if not resources:
        # 프론트엔드로 리다이렉트 (실패)
        return RedirectResponse(
            url=f"{auth_settings.FRONTEND_REDIRECT_URI}?jira_installed=false&reason=no_resources"
        )

    # 4. 각 리소스별 토큰 저장
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens.expires_in)

    for resource in resources:
        jira_crud.create_or_update_jira_token(
            db=db,
            atlassian_account_id=user_info.account_id,
            cloud_id=resource.id,
            site_name=resource.name,
            site_url=resource.url,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_at=expires_at,
            scopes=tokens.scope,
        )

    logger.info(f"Jira 설치 완료: {len(resources)}개 사이트 연결")

    # 5. 프론트엔드로 리다이렉트 (성공)
    return RedirectResponse(
        url=f"{auth_settings.FRONTEND_REDIRECT_URI}?jira_installed=true&count={len(resources)}"
    )


@router.get("/status", response_model=JiraInstallationStatus)
async def jira_installation_status(
    db: Session = Depends(get_db),
    jira_service: JiraOAuthService = Depends(get_jira_oauth_service),
):
    """Jira 설치 상태 조회"""
    tokens = jira_crud.get_all_jira_tokens(db)

    if not tokens:
        return JiraInstallationStatus(installed=False)

    try:
        valid_token = await jira_service.get_valid_access_token(db, tokens[0])
        resources = await jira_service.get_accessible_resources(valid_token)
        return JiraInstallationStatus(installed=True, resources=resources)
    except HTTPException as e:
        logger.warning(f"Jira 상태 조회 실패: {e.detail}")
        return JiraInstallationStatus(installed=True, resources=[])
    except (HTTPStatusError, RequestError) as e:
        logger.warning(f"Jira API 요청 실패: {e}")
        return JiraInstallationStatus(installed=True, resources=[])


@router.delete("/uninstall")
async def jira_uninstall(
    cloud_id: str = Query(..., description="삭제할 Jira Cloud ID"),
    db: Session = Depends(get_db),
):
    """Jira 연결 해제"""
    deleted = jira_crud.delete_jira_token(db, cloud_id)
    if deleted:
        return {"status": "success", "message": "Jira 연결이 해제되었습니다."}
    return {"status": "not_found", "message": "해당 Jira 연결을 찾을 수 없습니다."}


# ================================================================
# Sync Router
# ================================================================

sync_router = APIRouter(prefix="/api/v1/jira/sync", tags=["jira-sync"])


async def _run_full_sync(
    cloud_id: str,
    access_token: str,
    site_url: str,
    db: Session,
    project_keys: list[str] | None = None,
) -> dict[str, Any]:
    """전체 동기화 실행 (백그라운드 태스크용)"""
    try:
        service = JiraIngestionService(cloud_id, access_token, site_url)
        await service.initialize()
        return await service.full_sync(db, project_keys)
    except Exception as e:
        logger.error(f"Full sync failed for cloud_id={cloud_id}: {e}")
        raise


async def _run_incremental_sync(
    cloud_id: str,
    access_token: str,
    site_url: str,
    db: Session,
) -> dict[str, Any]:
    """증분 동기화 실행 (백그라운드 태스크용)"""
    try:
        service = JiraIngestionService(cloud_id, access_token, site_url)
        await service.initialize()
        return await service.incremental_sync(db)
    except Exception as e:
        logger.error(f"Incremental sync failed for cloud_id={cloud_id}: {e}")
        raise


@sync_router.post("/full", response_model=SyncResponse)
async def trigger_full_sync(
    request: SyncRequest,
    cloud_id: str = Query(..., description="Jira Cloud ID"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    jira_service: JiraOAuthService = Depends(get_jira_oauth_service),
):
    """
    전체 동기화 트리거

    지정된 프로젝트(또는 전체)의 모든 Jira 데이터를 PGVector에 동기화.
    대량의 데이터가 있을 경우 시간이 오래 걸릴 수 있습니다.
    """
    # 토큰 조회 및 검증
    token_record = jira_crud.get_jira_token_by_cloud_id(db, cloud_id)
    if not token_record:
        raise HTTPException(
            status_code=404,
            detail=f"Jira 연결을 찾을 수 없습니다: {cloud_id}",
        )

    try:
        # 유효한 access token 획득
        access_token = await jira_service.get_valid_access_token(db, token_record)
        site_url = token_record.site_url or ""

        # 동기 실행 (백그라운드 태스크로 전환 가능)
        result = await _run_full_sync(
            cloud_id=cloud_id,
            access_token=access_token,
            site_url=site_url,
            db=db,
            project_keys=request.project_keys,
        )

        return SyncResponse(
            status="success",
            message=f"전체 동기화 완료: Issues={result['issues']['synced']}, Epics={result['epics']['synced']}",
            cloud_id=cloud_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Full sync error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"동기화 중 오류가 발생했습니다: {str(e)}",
        )


@sync_router.post("/incremental", response_model=SyncResponse)
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


@sync_router.get("/status", response_model=list[SyncStatusResponse])
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


@sync_router.post("/search", response_model=SearchResponse)
async def search_jira_documents(
    request: SearchRequest,
    cloud_id: str = Query(..., description="Jira Cloud ID"),
    db: Session = Depends(get_db),
    jira_service: JiraOAuthService = Depends(get_jira_oauth_service),
):
    """
    Jira 문서 벡터 검색

    PGVector에 저장된 Jira 데이터에서 시맨틱 검색 수행.
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

        service = JiraIngestionService(cloud_id, access_token, site_url)
        await service.initialize()

        documents = await service.search(
            query=request.query,
            k=request.k,
            entity_type=request.entity_type,
            project_key=request.project_key,
        )

        results = [
            SearchResultItem(
                id=doc.id or "",
                content=doc.page_content[:500],  # 500자로 제한
                metadata=doc.metadata,
            )
            for doc in documents
        ]

        return SearchResponse(results=results, total=len(results))

    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"검색 중 오류가 발생했습니다: {str(e)}",
        )
