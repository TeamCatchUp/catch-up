import logging
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from catchup.auth.cookies import delete_auth_cookies, set_auth_cookies
from catchup.auth.dependencies import get_current_user
from catchup.auth.google_oauth import GoogleOAuthService
from catchup.auth.jwt import create_access_token, create_refresh_token, verify_token
from catchup.configs.config import auth_settings
from catchup.db.dependencies import get_db
from catchup.db.models import User
from catchup.db.users import get_user_by_email, update_user_refresh_token
from catchup.db import github_installation as installation_crud
from catchup.server.auth.schemas import CurrentUserInfo, TokenRefreshResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

GOOGLE_LOGIN_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USER_INFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"


@router.get("/login")
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


@router.get("/google/callback")
async def google_callback(
    code: str,
    db: Session = Depends(get_db),
    oauth_service: GoogleOAuthService = Depends(),
):
    google_user = await oauth_service.get_google_user(code)

    user = oauth_service.get_or_register_google_user(db, google_user)

    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})

    update_user_refresh_token(db, user.id, refresh_token)

    response = RedirectResponse(url=auth_settings.FRONTEND_REDIRECT_URI)

    set_auth_cookies(response, access_token, refresh_token)

    return response


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(
    request: Request, response: Response, db: Session = Depends(get_db)
):
    refresh_token = request.headers.get("refresh_token")

    payload = verify_token(refresh_token, "refresh")

    email = payload.get("sub")

    user = get_user_by_email(db, email)

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


@router.post("/logout")
async def logout(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    update_user_refresh_token(db, current_user.id, None)

    delete_auth_cookies(response)

    return {"status": "success", "detail": "Logged out successfully"}


@router.get("/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    return CurrentUserInfo(
        email=current_user.email, name=current_user.name, role=current_user.role
    )


# ============================================================
# GitHub App Installation Callback
# ============================================================

@router.get("/github/install")
async def github_app_install_callback(
    installation_id: Optional[int] = Query(None),
    setup_action: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    GitHub App 설치 완료 후 Callback 엔드포인트

    GitHub App 설정에서 "Setup URL (optional)"로 등록:
    https://your-domain.com/api/v1/auth/github/install

    GitHub이 전달하는 Query Parameters:
    - installation_id: 설치된 Installation ID
    - setup_action: "install" (신규 설치) 또는 "update" (권한 변경)
    """
    logger.info(
        f"GitHub App install callback received: "
        f"installation_id={installation_id}, setup_action={setup_action}"
    )

    # installation_id가 없으면 에러
    if not installation_id:
        logger.warning("GitHub App install callback received without installation_id")
        redirect_url = f"{auth_settings.FRONTEND_REDIRECT_URI}?github_install=error&reason=missing_installation_id"
        return RedirectResponse(url=redirect_url)

    # DB에서 Installation 확인 (Webhook이 먼저 도착했으면 이미 저장되어 있음)
    installation = installation_crud.get_installation_by_installation_id(db, installation_id)

    if installation:
        logger.info(
            f"GitHub App installation found: "
            f"installation_id={installation_id}, account={installation.account_login}"
        )
        redirect_url = (
            f"{auth_settings.FRONTEND_REDIRECT_URI}"
            f"?github_install=success"
            f"&installation_id={installation_id}"
            f"&account={installation.account_login}"
        )
    else:
        # Webhook이 아직 처리되지 않았을 수 있음 (race condition)
        # 일단 성공으로 처리하고, 프론트엔드에서 polling으로 확인하도록
        logger.info(
            f"GitHub App installation not yet in DB: installation_id={installation_id}. "
            f"Webhook may arrive shortly."
        )
        redirect_url = (
            f"{auth_settings.FRONTEND_REDIRECT_URI}"
            f"?github_install=pending"
            f"&installation_id={installation_id}"
        )

    return RedirectResponse(url=redirect_url)
