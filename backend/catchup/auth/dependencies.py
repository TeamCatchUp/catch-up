from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyCookie
from sqlalchemy.orm import Session

from catchup.auth.jwt import verify_token
from catchup.db.dependencies import get_db
from catchup.db.models import User
from catchup.db.users import get_user_by_email


cookie_scheme = APIKeyCookie(name="access_token", auto_error=False)

def get_current_user(
    access_token: str = Depends(cookie_scheme),
    db: Session = Depends(get_db)
) -> User:
    
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 쿠키가 없습니다.",
        )
        
    try:
        payload = verify_token(access_token, "access")
        email: str = payload.get("sub")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="토큰에 사용자 정보가 없습니다.",
            )
        
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 만료되었거나 유효하지 않습니다.",
        )

    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="존재하지 않는 사용자입니다.",
        )

    return user
