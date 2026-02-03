from fastapi import Response

from catchup.configs.config import auth_settings

ACCESS_TOKEN_KEY = "access_token"
REFRESH_TOKEN_KEY = "refresh_token"


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
