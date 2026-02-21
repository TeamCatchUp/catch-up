import logging
from fastapi import HTTPException, status
import httpx
from sqlalchemy.orm import Session

from catchup.auth.schemas import OktaUserInfoResponse, UserCreate
from catchup.configs.config import auth_settings
from catchup.db.models import OktaUser, User, UserRole, UserStatus
from catchup.db.users import get_okta_user_with_okta_uid, get_user_by_email

logger = logging.getLogger(__name__)

class OktaOAuthService:
    ISSUER = f"https://{auth_settings.OKTA_DOMAIN}"
    TOKEN_URL = f"https://{auth_settings.OKTA_DOMAIN}/oauth2/v1/token"
    USER_INFO_URL = f"https://{auth_settings.OKTA_DOMAIN}/oauth2/v1/userinfo"
    
    async def get_okta_user(
        self,
        code: str
    ) -> OktaUserInfoResponse:
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
                "client_id": auth_settings.OKTA_CLIENT_ID,
                "client_secret": auth_settings.OKTA_CLIENT_SECRET,
                "code": code,
                "redirect_uri": auth_settings.OKTA_REDIRECT_URI,
            }
        )
        
        logger.info(f"response: {response}")
        
        if response.status_code != 200:
            logger.error(f"Okta token error: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효하지 않은 Okta Code입니다."
            )
        
        return response.json().get("access_token")
        
    
    async def _fetch_user_info(
        self,
        client: httpx.AsyncClient,
        access_token: str
    ) -> OktaUserInfoResponse:
        response = await client.get(
            self.USER_INFO_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Okta 사용자 정보를 가져오지 못했습니다."
            )
        
        data = response.json()
        
        return OktaUserInfoResponse(**data)
    
    # TODO: Google OAuth 중복 로직 통합
    def get_or_register_okta_user(
        self,
        db: Session,
        okta_user: OktaUserInfoResponse
    ) -> OktaUser:
        okta_record = get_okta_user_with_okta_uid(db, okta_user.sub)
        
        if not okta_record:
            new_okta_record = OktaUser(
                okta_uid=okta_user.sub,
                email=okta_user.email,
                name=okta_user.name,
                status=UserStatus.ACTIVE
            )
            db.add(new_okta_record)
            db.flush()
            
            okta_record = new_okta_record
        
        return okta_record