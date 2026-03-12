from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
import structlog

from catchup.audit.service import emit_audit_event
from catchup.audit.enums import AuditLevel
from catchup.events.enums import AuthEventAction
from catchup.auth.service import OAuthService
from catchup.auth.cookies import delete_auth_cookies, delete_oauth_state_cookie, set_auth_cookies, set_oauth_state_cookie
from catchup.auth.dependencies import (
    get_current_user,
    get_current_user_info,
    get_oauth_provider,
    get_oauth_service_from_state
)
from catchup.auth.jwt import create_access_token, create_refresh_token, verify_token
from catchup.components.auth.provider import OAuthIdentityProvider
from catchup.components.auth.constants import OAuthIdentityProviderType
from catchup.configs.config import auth_settings
from catchup.db.dependencies import get_db
from catchup.db.models import (
    ConfluenceUser,
    GitHubUser,
    JiraUser,
    PreMappingBuffer,
    SlackUser,
    SourceType,
    User,
)
from catchup.db.users import get_user_by_sub, update_user_refresh_token
from sqlalchemy import select
from catchup.events.enums import EventType
from catchup.server.auth.schemas import (
    CurrentUserInfo,
    CurrentUserProfile,
    IntegrationProfileItem,
    IntegrationProfileResponse
)
from catchup.utils.redis import store_oauth_state, validate_oauth_state

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

# ===========
# Oauth 로그인
# ===========
@router.get(
    path="/oauth/login",
    description="OAuth2 로그인 (현재는 Keycloak만 지원)"
)
async def oauth2_login(
    request: Request,
    # TODO: Path()로 변경. 수정 범위를 최소화하기 위한 PoC 한정 임시방편
    provider_type: OAuthIdentityProviderType = Query(default=OAuthIdentityProviderType.KEYCLOAK),
    provider: OAuthIdentityProvider = Depends(get_oauth_provider)
):
    # OAuth state를 Redis에 저장
    await store_oauth_state(
        state=provider.state,
        provider=provider_type.value
    )
    
    authentication_url = provider.get_authentication_url()
    response = RedirectResponse(authentication_url)
    
    # OAuth state를 브라우저 쿠키에도 저장
    set_oauth_state_cookie(
        response=response,
        state=provider.state
    )
    
    emit_audit_event(
        event_type=EventType.AUTH,
        event_action=AuthEventAction.LOGIN_ATTEMPT,
        level=AuditLevel.INFO,
        immediate=True
    )

    return response


@router.get(
    path="/oauth/callback",
    description="OAuth2 리다이렉트 URI"
)
async def oauth_callback(
    request: Request,
    code: str,
    state: str,
    auth_service: OAuthService = Depends(get_oauth_service_from_state)
):
    cookie_state = request.cookies.get("oauth_state")
    valid_state = True
    if not cookie_state:
        logger.warning("login_failed", context="state_not_exists")
        emit_audit_event(
            event_type=EventType.AUTH,
            event_action=AuthEventAction.LOGIN_FAILURE,
            level=AuditLevel.WARNING,
            metadata={"reason": "state_missing"},
            immediate=True
        )
        valid_state = False
    
    elif cookie_state != state:
        logger.warning("login_failed", context="invalid_state")
        emit_audit_event(
            event_type=EventType.AUTH,
            event_action=AuthEventAction.LOGIN_FAILURE,
            level=AuditLevel.WARNING,
            metadata={"reason": "state_mismatch"},
            immediate=True
        )
        valid_state = False
        
    if not valid_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 인증 접근입니다."
        )

    # OAuth state 유효성 검사
    is_valid = await validate_oauth_state(
        state=state,
        provider=auth_service.provider_type.value
    )
    
    if not is_valid:
        emit_audit_event(
            event_type=EventType.AUTH,
            event_action=AuthEventAction.LOGIN_FAILURE,
            level=AuditLevel.WARNING,
            metadata={"reason": "expired_state"},
            immediate=True
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않거나 만료된 인증입니다."
        )
    
    access_token, refresh_token = await auth_service.handle_callback(code)
    
    response = RedirectResponse(url=auth_settings.FRONTEND_REDIRECT_URI)
    
    delete_oauth_state_cookie(response)
    set_auth_cookies(
        response=response,
        access_token=access_token,
        refresh_token=refresh_token
    )
    
    return response


@router.post(
    path="/refresh",
    description="Refresh 토큰 발급",
)
def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh Token이 없습니다."
        )

    # refresh token 유효성 검사
    try:
        payload = verify_token(
            token=refresh_token,
            type="refresh"
        )
    except HTTPException as e:
        emit_audit_event(
            event_type=EventType.AUTH,
            event_action=AuthEventAction.LOGIN_FAILURE,
            level=AuditLevel.WARNING,
            metadata={"reason": "invalid_or_expired_token", "detail": e.detail},
            immediate=True
        )
        
        # 유효하지 않은 토큰인 경우 사용자 쿠키 삭제
        err_response = JSONResponse(
            status_code=e.status_code, 
            content={"detail": e.detail}
        )
        delete_auth_cookies(err_response)
        return err_response
    
    
    # sub 기반 User 조회
    sub = payload.get("sub")
    user = get_user_by_sub(
        db=db,
        sub=sub
    )
    
    snapshot = None
    if user:
        snapshot = user.to_snapshot()
        snapshot["sub"] = user.oauth_user.sub

    # 존재하지 않는 사용자이거나 refresh token이 일치하지 않는 경우
    if not user or user.refresh_token != refresh_token:
        emit_audit_event(
            event_type=EventType.AUTH,
            event_action=AuthEventAction.LOGIN_FAILURE,
            level=AuditLevel.WARNING,
            metadata={"reason": "invalid_refresh_token"},
            immediate=True,
            actor=snapshot,
        )
        err_response = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Refresh Token이 유효하지 않습니다."}
        )
        delete_auth_cookies(err_response)
        return err_response
    
    # token 재발급
    token_data = {
        "sub": user.oauth_user.sub,
        "email": user.email,
        "name": user.name,
        "role": user.role
    }
    new_access_token = create_access_token(data=token_data)
    new_refresh_token = create_refresh_token(data=token_data)  # Rotation
    
    # refresh token 갱신
    update_user_refresh_token(
        db=db,
        user_id=user.id,
        refresh_token=new_refresh_token
    )

    set_auth_cookies(
        response=response,
        access_token=new_access_token,
        refresh_token=new_refresh_token
    )

    emit_audit_event(
        event_type=EventType.AUTH,
        event_action=AuthEventAction.TOKEN_REFRESH,
        level=AuditLevel.INFO,
        immediate=True,
        actor=snapshot,
    )

    return {
        "status": "success",
        "detail": "Access Token을 성공적으로 갱신했습니다."
    }


@router.post(
    path="/logout",
    description="access & refresh 토큰을 쿠키에서 제거한다."
)
async def logout(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    def _update_user_refresh_token_sync():
        update_user_refresh_token(
            db=db,
            user_id=current_user.id,
            refresh_token=None
        )
        db.commit()
    
    await run_in_threadpool(_update_user_refresh_token_sync)

    delete_auth_cookies(response)
    
    emit_audit_event(
        event_type=EventType.AUTH,
        event_action=AuthEventAction.LOGOUT,
        level=AuditLevel.INFO,
        immediate=True
    )

    return {"status": "success", "detail": "Logged out successfully"}


@router.get(
    path="/me",
    description="인증된 사용자의 정보를 반환한다. (미가입 상태 포함)" 
)
def read_users_me(
    user_info: dict = Depends(get_current_user_info)
):
    return CurrentUserInfo(**user_info)


@router.get(
    path="/me/profile",
    description = "마이페이지 - 계정 상세 정보",
    response_model=CurrentUserProfile,
)
async def mypage_profile(current_user: User = Depends(get_current_user)):
    return CurrentUserProfile(
        name=current_user.name,
        email=current_user.email,
        picture=current_user.picture or "",
        department=current_user.department,
        job_level=current_user.job_level,
        role=current_user.role,
    )


@router.get(
    path="/me/integrations",
    description="마이페이지 - 외부 툴 프로필 (GitHub/Jira/Confluence/Slack)",
    response_model=IntegrationProfileResponse,
)
async def mypage_integrations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    premapped_rows = db.scalars(
        select(PreMappingBuffer).where(PreMappingBuffer.email == current_user.email)
    ).all()

    response = IntegrationProfileResponse()

    def _to_item(avatar_url: str | None, name: str | None, email: str | None):
        return IntegrationProfileItem(
            avatar_url=avatar_url,
            name=name,
            email=email,
        )

    for row in premapped_rows:
        if row.source_type == SourceType.GITHUB:
            github = db.scalar(
                select(GitHubUser).where(GitHubUser.login == row.external_user_identifier)
            )
            response.github = _to_item(
                avatar_url=github.avatar_url if github else None,
                name=row.external_user_identifier,  # GitHub는 로그인 ID 우선
                email=github.email if github else None,
            )

        elif row.source_type == SourceType.JIRA:
            jira_user = db.scalar(
                select(JiraUser).where(JiraUser.account_id == row.external_user_identifier)
            )
            response.jira = _to_item(
                avatar_url=jira_user.avatar_url if jira_user else None,
                name=jira_user.display_name if jira_user else row.name,
                email=jira_user.email_address if jira_user else None,
            )

        elif row.source_type == SourceType.CONFLUENCE:
            confluence_user = db.scalar(
                select(ConfluenceUser).where(
                    ConfluenceUser.account_id == row.external_user_identifier
                )
            )
            response.confluence = _to_item(
                avatar_url=confluence_user.avatar_url if confluence_user else None,
                name=confluence_user.display_name
                if confluence_user and confluence_user.display_name
                else row.name,
                email=confluence_user.email if confluence_user else None,
            )

        elif row.source_type == SourceType.SLACK:
            slack_user = db.scalar(
                select(SlackUser).where(SlackUser.user_id == row.external_user_identifier)
            )
            response.slack = _to_item(
                avatar_url=slack_user.avatar_url if slack_user else None,
                name=slack_user.display_name if slack_user else row.name,
                email=slack_user.email if slack_user else None,
            )

    logger.info(
        "user_integrations_status",
        user_id=current_user.oauth_user.sub,
        github=bool(response.github),
        jira=bool(response.jira),
        confluence=bool(response.confluence),
        slack=bool(response.slack)
    )

    return response
