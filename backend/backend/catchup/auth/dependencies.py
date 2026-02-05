from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from catchup.auth.jwt import verify_token
from catchup.db.dependencies import get_db
from catchup.db.models import User
from catchup.db.users import get_user_by_email


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth_header = request.headers.get("Authorization")

    access_token = _parse_auth_header(auth_header)

    payload = verify_token(access_token, "access")

    email: str = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰에 사용자 정보가 없습니다.",
        )

    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="존재하지 않는 사용자입니다.",
        )

    return user


def _parse_auth_header(auth_header: str) -> str:
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 정보가 없습니다.",
        )

    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 정보가 올바르지 않은 형식입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth_header.split(" ")[1]
