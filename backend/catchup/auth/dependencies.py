from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyCookie
from sqlalchemy.orm import Session

from catchup.auth.jwt import verify_token
from catchup.db.dependencies import get_db
from catchup.db.models import User, UserRole, UserStatus
from catchup.db.users import get_user_by_email
from catchup.server.state import state


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
    User DB 조회 없이 토큰 access token payload를 기반으로 회원가입을 처리하기 위함이다.
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
    

def require_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """관리자 권한 검사. 인증된 사용자 중 ADMIN role만 허용."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="권한이 없습니다. 관리자만 접근할 수 있습니다.",
        )
    return current_user


def get_current_user_info(
    access_token: str = Depends(cookie_scheme),
    db: Session = Depends(get_db)
) -> dict:
    """/auth/me 전용"""
    
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 쿠키가 없습니다.",
        )
        
    try:
        payload = verify_token(access_token, "access")
        email: str = payload.get("sub")
        name: str = payload.get("name")
        
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
    
    if user:
        return {
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "status": user.status
        }
    else:
        suggested_role = UserRole.USER
        
        # 아직 어드민이 생성되지 않은 상태라면 어드민 권한 부여
        if not state.is_admin_initiated:
            suggested_role = UserRole.ADMIN
        
        # Okta 로그인 O, 회원가입 X (일반 유저)
        return {
            "email": email,
            "name": name or "Unknown",
            "role": suggested_role,
            "status": UserStatus.NEW 
        }