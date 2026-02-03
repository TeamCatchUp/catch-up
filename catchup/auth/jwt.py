from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import HTTPException, status

from catchup.configs.config import auth_settings


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()

    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=auth_settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "type": "access"})

    encoded_jwt = jwt.encode(
        payload=to_encode,
        key=auth_settings.JWT_SECRET_KEY,
        algorithm=auth_settings.JWT_ALGORITHM,
    )

    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        days=auth_settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    to_encode.update({"exp": expire, "type": "refresh"})

    encoded_jwt = jwt.encode(
        payload=to_encode,
        key=auth_settings.JWT_SECRET_KEY,
        algorithm=auth_settings.JWT_ALGORITHM,
    )

    return encoded_jwt


def verify_token(token: str, type: str) -> dict:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="인증 정보가 없습니다."
        )

    try:
        payload = jwt.decode(
            token,
            auth_settings.JWT_SECRET_KEY,
            algorithms=[auth_settings.JWT_ALGORITHM],
        )

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="만료된 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰 타입이 올바르지 않습니다.",
        )

    return payload
