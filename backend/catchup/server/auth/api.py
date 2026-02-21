import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from catchup.auth.cookies import delete_auth_cookies, set_auth_cookies
from catchup.auth.dependencies import get_current_user, get_current_user_info
from catchup.auth.google_oauth import GoogleOAuthService
from catchup.auth.jwt import create_access_token, create_refresh_token, verify_token
from catchup.auth.okta_oauth import OktaOAuthService
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
from catchup.db.users import get_user_by_email, update_user_refresh_token
from sqlalchemy import select
from catchup.server.auth.schemas import (
    CurrentUserInfo,
    CurrentUserProfile,
    IntegrationProfileItem,
    IntegrationProfileResponse,
    TokenRefreshResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

GOOGLE_LOGIN_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USER_INFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"

# ==========
# Okta
# ==========
@router.get(
    path="/okta/login",
    description="Okta OAuth2 로그인"
)
async def okta_oauth2_login():
    base_url = f"https://{auth_settings.OKTA_DOMAIN}/oauth2/v1/authorize"
    
    params = {
        "client_id": auth_settings.OKTA_CLIENT_ID,
        "redirect_uri": auth_settings.OKTA_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile offline_access",
        "state": "random_state_string_check_needed",
    }
    
    url = f"{base_url}?{urlencode(params)}"
    
    return RedirectResponse(url)


@router.get(
    path="/okta/callback",
    description="Okta OAuth2 리다이렉트 URI"
)
async def okta_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
    oauth_service: OktaOAuthService = Depends(),
):
    okta_user = await oauth_service.get_okta_user(code)
    
    def _handle_login_sync():
        okta_record = oauth_service.get_or_register_okta_user(db, okta_user)
        
        token_data = {
            "sub": okta_user.email,
            "okta_uid": okta_user.sub,
            "name": okta_user.name
        }
        access_token = create_access_token(data=token_data)
        
        if okta_record.user_id is not None:
            # 기존 유저: 리프레시 토큰 정상 발급
            refresh_token = create_refresh_token(data=token_data)
            update_user_refresh_token(db, okta_record.user_id, refresh_token)
        else:
            # 아직 온보딩 전인 신규 유저: 임시로 엑세스 토큰만 발급
            refresh_token = None
        db.commit()
        
        return access_token, refresh_token
    
    access_token, refresh_token = await run_in_threadpool(_handle_login_sync)
    
    response = RedirectResponse(url=auth_settings.FRONTEND_REDIRECT_URI)
    set_auth_cookies(response, access_token, refresh_token)
    
    return response

# ==========
# Google
# ==========
@router.get(
    path="/google/login",
    description="Google Oauth2 로그인"
)
async def google_oauth2_login():
    params = {
        "client_id": auth_settings.GOOGLE_CLIENT_ID,
        "redirect_uri": auth_settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "prompt": "select_account",
    }

    url = f"{GOOGLE_LOGIN_BASE_URL}?{urlencode(params)}"

    return RedirectResponse(url)


@router.get(
    path="/google/callback",
    description="Google OAuth2 리다이렉트 URI"
)
async def google_callback(
    code: str,
    db: Session = Depends(get_db),
    oauth_service: GoogleOAuthService = Depends(),
):
    google_user = await oauth_service.get_google_user(code)

    def _handle_login_sync():
        user = oauth_service.get_or_register_google_user(db, google_user)

        access_token = create_access_token(data={"sub": user.email})
        refresh_token = create_refresh_token(data={"sub": user.email})

        update_user_refresh_token(db, user.id, refresh_token)
        db.commit()
        
        return access_token, refresh_token

    access_token, refresh_token = await run_in_threadpool(_handle_login_sync)

    response = RedirectResponse(url=auth_settings.FRONTEND_REDIRECT_URI)

    set_auth_cookies(response, access_token, refresh_token)

    return response


@router.post(
    path="/refresh",
    description="Refresh 토큰 발급",
    response_model=TokenRefreshResponse)
async def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    refresh_token = request.cookies.get("refresh_token")
    
    if not refresh_token:
        refresh_token = request.headers.get("refresh_token")

    payload = verify_token(refresh_token, "refresh")

    email = payload.get("sub")

    user = await run_in_threadpool(
        get_user_by_email,
        db,
        email
    )

    if not user or user.refresh_token != refresh_token:
        delete_auth_cookies(response)

        response.status_code = status.HTTP_401_UNAUTHORIZED

        return TokenRefreshResponse(
            status="error", detail="Refresh Token이 유효하지 않습니다."
        )

    new_access_token = create_access_token(data={"sub": user.email})

    set_auth_cookies(response, new_access_token)

    return TokenRefreshResponse(
        status="success", detail="Access Token을 성공적으로 갱신했습니다."
    )


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
        "[AUTH][ME-INTEGRATIONS] user_id=%s github=%s jira=%s confluence=%s slack=%s",
        current_user.id,
        bool(response.github),
        bool(response.jira),
        bool(response.confluence),
        bool(response.slack),
    )

    return response
