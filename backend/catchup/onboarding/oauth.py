import re
from fastapi.concurrency import run_in_threadpool
import httpx
import logging
import json
import jwt

from catchup.configs.config import auth_settings
from catchup.db.engine import SessionLocal
from catchup.db.user_source_mapping import upsert_oauth_users
from catchup.mapping.schemas import OAuthUserSchema

logger = logging.getLogger(__name__)


# TODO: OAuthClient도 component로 빠져야 하는 게 아닐지
class OAuthClient:
    BASE_URL = f"{auth_settings.KC_INTERNAL_URL}/admin/realms/{auth_settings.KC_REALM}/users"
    
    async def get_parsed_users(self) -> list[OAuthUserSchema]:
        raw_data = await self._fetch_all_oauth_users()
        return self._parse_users(raw_data)
    
    async def _fetch_all_oauth_users(self) -> list:
        token = await self._get_admin_token()
        
        try:
            decoded = jwt.decode(token, options={"verify_signature": False})
            logger.debug(f"Token Realm Access Roles: {decoded.get('realm_access', {}).get('roles')}")
            logger.debug(f"Token Resource Access: {json.dumps(decoded.get('resource_access', {}), indent=2)}")
        except Exception as e:
            logger.warning(f"토큰 디코딩 실패: {e}")

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            request_url = f"{self.BASE_URL}?max=1000"
            logger.info(f"Keycloak 유저 목록 요청 시작: {request_url}")
            
            response = await client.get(request_url, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"유저 조회 실패 (Status: {response.status_code}) | Body: {response.text}")
            
            response.raise_for_status()
            users_data = response.json()
            logger.info(f"유저 목록 수신 완료 (총 {len(users_data)}명)")
            return users_data

    async def _get_admin_token(self) -> str:
        url = f"{auth_settings.KC_INTERNAL_URL}/realms/master/protocol/openid-connect/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": auth_settings.KC_CLIENT_ID,
            "client_secret": auth_settings.KC_CLIENT_SECRET,
        }
        
        logger.info(f"Admin 토큰 요청 시작 (Client ID: {auth_settings.KC_CLIENT_ID})")
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data)
            
            if response.status_code != 200:
                logger.error(f"토큰 발급 실패 (Status: {response.status_code}) | Body: {response.text}")
            
            response.raise_for_status()
            token = response.json().get("access_token")
            logger.debug(f"토큰 발급 완료: {token}")
            return token

    def _parse_users(self, raw_data: list) -> list[OAuthUserSchema]:
        oauth_users = []
        for user in raw_data:
            first_name = user.get("firstName", "")
            last_name = user.get("lastName", "")
            full_name = self._combine_name(first_name, last_name)
            
            oauth_users.append(OAuthUserSchema(
                sub=user["id"],
                email=user.get("email"),
                name=full_name or user.get("username"),
                status="ACTIVE" if user.get("enabled") else "DEACTIVATED"
            ))
        return oauth_users

    def _combine_name(self, first_name: str, last_name: str) -> str:
        f = first_name.strip()
        l = last_name.strip()
        if not f and not l: return ""
        # 한국어 이름 처리
        if re.search(r"[ㄱ-ㅎㅏ-ㅣ가-힣]", f + l):
            return f"{l}{f}".strip()
        return f"{f} {l}".strip()


async def sync_initial_oauth_users():
    try:
        oauth_client = OAuthClient()
        parsed_users = await oauth_client.get_parsed_users()
        
        if not parsed_users:
            logger.warning(f"No users found from OAuth")
            return
        
        def _upsert_oauth_users_sync():
            with SessionLocal() as db:
                try:
                    upsert_oauth_users(db, parsed_users)
                    db.commit()
                    logger.info(f"Successfully synced {len(parsed_users)} users from OAuth")
                except Exception as e:
                    db.rollback()
                    logger.error(f"DB Upsert failed: {e}")
                    raise
                
        await run_in_threadpool(_upsert_oauth_users_sync)  # TODO: fastapi 의존성이 여기에 위치하는 게 맞을지
        
    except Exception as e:
        logger.error(f"Failed to sync OAuth users: {e}", exc_info=True)