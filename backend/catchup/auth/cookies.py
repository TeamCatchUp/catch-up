from fastapi import Response

from catchup.configs.config import auth_settings

ACCESS_TOKEN_KEY = "access_token"
REFRESH_TOKEN_KEY = "refresh_token"
OAUTH_STATE_TOKEN_KEY = "oauth_state"


def set_auth_cookies(
    response: Response, access_token: str, refresh_token: str | None = None
):
    response.set_cookie(
        key=ACCESS_TOKEN_KEY,
        value=access_token,
        httponly=auth_settings.HTTP_ONLY,
        secure=auth_settings.SECURE,
        samesite=auth_settings.SAMESITE,
        max_age=60 * auth_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    )

    if refresh_token:
        response.set_cookie(
            key=REFRESH_TOKEN_KEY,
            value=refresh_token,
            httponly=auth_settings.HTTP_ONLY,
            secure=auth_settings.SECURE,
            samesite=auth_settings.SAMESITE,
            max_age=60 * 60 * 24 * auth_settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS,
        )


def delete_auth_cookies(response: Response):
    response.delete_cookie(ACCESS_TOKEN_KEY)
    response.delete_cookie(REFRESH_TOKEN_KEY)  # 방어 로직


# OAuth state를 브라우저 쿠키에 저장
def set_oauth_state_cookie(
    response: Response,
    state: str
):
    response.set_cookie(
        key=OAUTH_STATE_TOKEN_KEY,
        value=state,
        httponly=auth_settings.HTTP_ONLY,
        secure=auth_settings.SECURE,
        samesite=auth_settings.SAMESITE,
        max_age=600,
    )


# OAuth state를 브라우저 쿠키에서 삭제
def delete_oauth_state_cookie(response: Response):
    response.delete_cookie(OAUTH_STATE_TOKEN_KEY)
    