import logging
from fastapi import HTTPException, status
import httpx
from sqlalchemy.orm import Session

from catchup.auth.schemas import KeycloakUserInfoResponse
from catchup.configs.config import auth_settings
from catchup.db.models import OauthUser, UserStatus
from catchup.db.users import get_oauth_user_with_sub

logger = logging.getLogger(__name__)

class KeycloakOAuthService:
    REALM = auth_settings.KC_REALM
    BASE_PATH = f"/realms/{REALM}/protocol/openid-connect"
    
    INTERNAL_BASE = f"{auth_settings.KC_INTERNAL_URL}{BASE_PATH}"
    ISSUER = f"{auth_settings.KC_INTERNAL_URL}/realms/{REALM}"
    TOKEN_URL = f"{INTERNAL_BASE}/token"
    USER_INFO_URL = f"{INTERNAL_BASE}/userinfo"
    
    async def get_user(
        self,
        code: str
    ) -> KeycloakUserInfoResponse:
        async with httpx.AsyncClient() as client:
            access_token = await self._get_access_token(client, code)
            return await self._fetch_user_info(client, access_token)
        
    async def _get_access_token(
        self,
        client: httpx.AsyncClient,
        code: str,
    ) -> str:
        response = await client.post(
            self.TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": auth_settings.KC_CLIENT_ID,
                "client_secret": auth_settings.KC_CLIENT_SECRET,
                "code": code,
                "redirect_uri": auth_settings.KC_REDIRECT_URI,
                "scope": "openid email profile offline_access",
            }
        )
        if response.status_code != 200:
            logger.error(f"Oauth token error: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효하지 않은 Code입니다."
            )
        
        return response.json().get("access_token")
        
    
    async def _fetch_user_info(
        self,
        client: httpx.AsyncClient,
        access_token: str
    ) -> KeycloakUserInfoResponse:
        response = await client.get(
            self.USER_INFO_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )

        if response.status_code != 200:
            logger.error(f"UserInfo Error Header: {response.headers.get('WWW-Authenticate')}")
            logger.error(f"UserInfo Error Body: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Oauth 사용자 정보를 가져오지 못했습니다."
            )
        
        data = response.json()
        
        return KeycloakUserInfoResponse(**data)
    
    def get_or_register_user(
        self,
        db: Session,
        oauth_user: KeycloakUserInfoResponse
    ) -> OauthUser:
        oauth_user_record = get_oauth_user_with_sub(db, oauth_user.sub)
        
        if not oauth_user_record:
            new_oauth_user = OauthUser(
                sub=oauth_user.sub,
                email=oauth_user.email,
                name=oauth_user.name,
                status=UserStatus.ACTIVE
            )
            db.add(new_oauth_user)
            db.flush()
            
            oauth_user_record = new_oauth_user
        
        return oauth_user_record