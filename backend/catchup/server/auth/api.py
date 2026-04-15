import structlog
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from fastapi import Response
from fastapi import status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.audit.actions import AuthAction
from catchup.audit.base import AuditStatus
from catchup.audit.contexts import AuditContext
from catchup.audit.emitters import emit_audit_event
from catchup.audit.enums import AuditLevel
from catchup.audit.metadata import AuthAuditMetadata
from catchup.audit.utils import audit_log
from catchup.auth.cookies import delete_auth_cookies
from catchup.auth.cookies import delete_oauth_state_cookie
from catchup.auth.cookies import set_auth_cookies
from catchup.auth.cookies import set_oauth_state_cookie
from catchup.auth.dependencies import get_current_user
from catchup.auth.dependencies import get_current_user_info
from catchup.auth.dependencies import get_oauth_provider
from catchup.auth.dependencies import get_oauth_service_from_state
from catchup.auth.jwt import create_access_token
from catchup.auth.jwt import create_refresh_token
from catchup.auth.jwt import verify_token
from catchup.auth.service import OAuthService
from catchup.components.auth.constants import OAuthIdentityProviderType
from catchup.components.auth.provider import OAuthIdentityProvider
from catchup.configs.config import auth_settings
from catchup.db.dependencies import get_db
from catchup.db.models import ConfluenceUser
from catchup.db.models import GitHubUser
from catchup.db.models import JiraUser
from catchup.db.models import PreMappingBuffer
from catchup.db.models import SlackUser
from catchup.db.models import SourceType
from catchup.db.models import User
from catchup.db.users import get_user_by_sub
from catchup.db.users import update_user_refresh_token
from catchup.server.auth.schemas import CurrentUserInfo
from catchup.server.auth.schemas import CurrentUserProfile
from catchup.server.auth.schemas import IntegrationProfileItem
from catchup.server.auth.schemas import IntegrationProfileResponse
from catchup.utils.redis import store_oauth_state
from catchup.utils.redis import validate_oauth_state

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

# ===========
# Oauth 로그인
# ===========
@router.get(
    path="/oauth/login",
    description="OAuth2 로그인 (현재는 Keycloak만 지원)"
)
@audit_log(AuthAction.LOGIN_ATTEMPT)
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

    return response


@router.get(
    path="/oauth/callback",
    description="OAuth2 리다이렉트 URI"
)
@audit_log(AuthAction.LOGIN)
async def oauth_callback(
    request: Request,
    code: str,
    state: str,
    auth_service: OAuthService = Depends(get_oauth_service_from_state)
):
    audit_ctx = AuditContext.get()
    cookie_state = request.cookies.get("oauth_state")
    
    if not cookie_state:
        logger.warning("login_failed", context="state_not_exists")
        audit_ctx.metadata = AuthAuditMetadata(context="state_missing")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 인증 접근입니다."
        )
    
    elif cookie_state != state:
        logger.warning("login_failed", context="invalid_state")
        audit_ctx.metadata = AuthAuditMetadata(context="state_mismatch")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 인증 접근입니다."
        )
    
    # OAuth state 유효성 검사
    valid = await validate_oauth_state(
        state=state,
        provider=auth_service.provider_type.value
    )
        
    if not valid:
        audit_ctx.metadata = AuthAuditMetadata(context="expired_state")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않거나 만료된 인증입니다."
        )
    
    access_token, refresh_token, actor_snapshot = await auth_service.handle_callback(code)
    audit_ctx.extra_payload["actor"] = actor_snapshot
    
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
            action=AuthAction.REFRESH_TOKEN,
            status=AuditStatus.FAILURE,
            level=AuditLevel.WARNING,
            metadata=AuthAuditMetadata(context="refresh_token_invalid"),
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
            action=AuthAction.REFRESH_TOKEN,
            status=AuditStatus.FAILURE,
            level=AuditLevel.WARNING,
            metadata=AuthAuditMetadata(context="refresh_token_invalid"),
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
        action=AuthAction.REFRESH_TOKEN,
        status=AuditStatus.SUCCESS,
        level=AuditLevel.INFO,
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
@audit_log(AuthAction.LOGOUT)
async def logout(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    def _update_user_refresh_token_sync():
        success = update_user_refresh_token(
            db=db,
            user_id=current_user.id,
            refresh_token=None
        )
        db.commit()
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="로그아웃 처리 중 오류가 발생했습니다."
            )

    await run_in_threadpool(_update_user_refresh_token_sync)
    
    delete_auth_cookies(response)
    
    return {
        "status": "success",
        "detail": "Logged out successfully"
    }


@router.get(
    path="/me",
    description="인증된 사용자의 정보를 반환한다. (미가입 상태 포함)",
    response_model=CurrentUserInfo,
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
