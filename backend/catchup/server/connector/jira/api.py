import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from catchup.auth.jira.app import get_jira_oauth_service, JiraOAuthService
from catchup.auth.jira.schemas import (
    JiraInstallationStatus,
    JiraOAuthCallbackResponse,
)
from catchup.configs.config import auth_settings
from catchup.db.dependencies import get_db
from catchup.db import jira_oauth as jira_crud

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth/jira", tags=["jira"])


@router.get("/install")
async def install_jira():
    """
    Jira OAuth 설치 시작
    - 관리자가 Jira Workspace에 앱을 설치하는 진입점
    """
    jira_service = get_jira_oauth_service()
    state = secrets.token_urlsafe(32)
    # TODO: state를 Redis에 저장하여 callback에서 검증

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
    # TODO: state 검증

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
    except Exception as e:
        logger.warning(f"Jira 상태 조회 실패: {e}")
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
