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


def get_pending_signup_user(
    access_token: str = Depends(cookie_scheme)
) -> dict:
    """
    회원가입 전용.
    User DB 조회 없이 토큰 payload를 기반으로 회원가입을 처리하기 위함이다.
    """
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 쿠키가 없습니다."
        )
        
    try:
        payload = verify_token(access_token, "access")
        email: str = payload.get("sub")
        okta_uid: str = payload.get("okta_uid")

        if not email or not okta_uid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="토큰에 필수 정보가 없습니다."
            )
            
        return {"email": email, "okta_uid": okta_uid, "name": payload.get("name")}
        
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 만료되었거나 유효하지 않습니다."
        )