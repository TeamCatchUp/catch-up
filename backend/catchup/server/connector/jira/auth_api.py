"""
Jira Auth API

Jira OAuth 인증 및 연결 관리 API 엔드포인트.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from httpx import HTTPStatusError, RequestError
from sqlalchemy.orm import Session

from catchup.connectors.jira.auth import get_jira_oauth_service, JiraOAuthService
from catchup.connectors.jira.dynamic_webhook_service import get_jira_dynamic_webhook_service
from catchup.connectors.jira.factory import create_jira_ingestion_service
from catchup.connectors.jira.schemas import JiraInstallationStatus
from catchup.configs.config import auth_settings
from catchup.db.dependencies import get_db
from catchup.db.engine import SessionLocal
from catchup.db.jira import oauth_repository as jira_crud
from catchup.utils.redis import store_oauth_state, validate_oauth_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth/jira", tags=["jira"])


# ================================================================
# Endpoints
# ================================================================

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
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Jira OAuth 콜백 처리
    - Authorization code → 토큰 교환
    - 접근 가능한 Jira 리소스 조회
    - 각 리소스별 토큰 저장
    """
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

    tokens = await jira_service.exchange_code_for_tokens(code)
    user_info = await jira_service.get_user_info(tokens.access_token)
    resources = await jira_service.get_accessible_resources(tokens.access_token)

    if not resources:
        return RedirectResponse(
            url=f"{auth_settings.FRONTEND_REDIRECT_URI}?jira_installed=false&reason=no_resources"
        )

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
        background_tasks.add_task(_sync_jira_metadata, resource.id)
        background_tasks.add_task(_ensure_jira_dynamic_webhook, resource.id)

    logger.info(f"Jira 설치 완료: {len(resources)}개 사이트 연결")

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


async def _sync_jira_metadata(cloud_id: str) -> None:
    """OAuth 설치 직후 메타데이터 동기화 (BackgroundTask)"""
    logger.info(f"[JIRA][AUTH] Starting background metadata sync: cloud_id={cloud_id}")

    db = SessionLocal()
    try:
        service = await create_jira_ingestion_service(db, cloud_id)
        results = await service.sync_metadata(db)
        logger.info(
            f"[JIRA][AUTH] Background metadata sync completed: "
            f"cloud_id={cloud_id}, results={results}"
        )
    except Exception as e:
        logger.error(
            f"[JIRA][AUTH] Background metadata sync failed: cloud_id={cloud_id}, error={e}"
        )
    finally:
        db.close()


async def _ensure_jira_dynamic_webhook(cloud_id: str) -> None:
    """
    OAuth 설치 직후 Dynamic Webhook 등록 보장 (BackgroundTask)
    """
    logger.info(f"[JIRA][AUTH] Ensuring dynamic webhook: cloud_id={cloud_id}")

    db = SessionLocal()
    try:
        dynamic_webhook_service = get_jira_dynamic_webhook_service()
        result = await dynamic_webhook_service.ensure_registered(db=db, cloud_id=cloud_id)
        logger.info(
            f"[JIRA][AUTH] Dynamic webhook ensured: cloud_id={cloud_id}, result={result}"
        )
    except Exception as e:
        logger.error(
            f"[JIRA][AUTH] Dynamic webhook ensure failed: cloud_id={cloud_id}, error={e}",
            exc_info=True,
        )
    finally:
        db.close()
