from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Response, status
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
from catchup.server.auth.schemas import CurrentUserInfo, TokenRefreshResponse

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
