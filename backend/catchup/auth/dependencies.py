import logging
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyCookie
from httpx import AsyncClient
from sqlalchemy.orm import Session

from catchup.auth.jwt import verify_token
from catchup.auth.service import OAuthService
from catchup.components.auth.provider import OAuthIdentityProvider
from catchup.components.auth.constants import OAuthIdentityProviderType
from catchup.components.auth.factory import get_oauth_identity_provider
from catchup.db.dependencies import get_db
from catchup.db.models import User, UserRole, UserStatus
from catchup.db.users import get_user_by_sub
from catchup.server.state import state
from catchup.utils.client import get_global_async_client


cookie_scheme = APIKeyCookie(name="access_token", auto_error=False)

logger = logging.getLogger(__name__)


def get_oauth_provider(
    # Client 요청으로 들어온 OAuth IDP 종류
    provider_type: OAuthIdentityProviderType = OAuthIdentityProviderType.KEYCLOAK,
    client: AsyncClient = Depends(get_global_async_client)
) -> OAuthIdentityProvider:
    """
    로그인 진입점에서 사용.
    요청받은 IDP 타입으로 OAuth 인증 클라이언트를 생성한다.
    """
    
    state = f"{provider_type.value}:{secrets.token_urlsafe(32)}"
    
    return get_oauth_identity_provider(
        provider_type=provider_type,
        client=client,
        state=state
    )


def _get_oauth_provider_from_state(
    state: str,
    client: AsyncClient = Depends(get_global_async_client)
) -> OAuthIdentityProvider:
    """
    oauth service 객체를 주입하기 위해 필요한 내부 의존성
    """
    
    try:
        provider_name = state.split(":")[0]
        provider_type = OAuthIdentityProviderType(provider_name)
    except (IndexError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="유효하지 않은 state 값입니다."
        )
    return get_oauth_identity_provider(
        provider_type=provider_type,
        client=client,
        state=state
    )


def get_oauth_service_from_state(
    db: Session = Depends(get_db),
    provider: OAuthIdentityProvider = Depends(_get_oauth_provider_from_state)
) -> OAuthService:
    return OAuthService(
        db=db,
        provider=provider,
        provider_type=provider.provider_type
    )


# 현재 로그인한 사용자 정보
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
        sub: str = payload.get("sub")
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="토큰에 사용자 정보가 없습니다.",
            )
        
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 만료되었거나 유효하지 않습니다.",
        )

    user = get_user_by_sub(db, sub)
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
        email: str = payload.get("email")
        sub: str = payload.get("sub")

        if not email or not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="토큰에 필수 정보가 없습니다."
            )
            
        return {"sub": sub, "email": email, "name": payload.get("name")}
        
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 만료되었거나 유효하지 않습니다."
        )
    

def require_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """관리자 권한 검사. 인증된 사용자 중 ADMIN role만 허용."""
    logger.debug(f"Checking user role: {current_user.role}")
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
        sub: str = payload.get("sub")
        email: str = payload.get("email")
        name: str = payload.get("name")
        
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="토큰에 사용자 정보가 없습니다.",
            )
            
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 만료되었거나 유효하지 않습니다.",
        )
    
    # 온보딩을 완료한 사용자인지 확인
    user = get_user_by_sub(db, sub)
    
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
        
        # Oauth 로그인 O, 회원가입 X (일반 유저)
        return {
            "email": email,
            "name": name or "Unknown",
            "role": suggested_role,
            "status": UserStatus.NEW 
        }