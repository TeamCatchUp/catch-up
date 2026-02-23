# import re
# import httpx
# import logging

# from catchup.configs.config import auth_settings
# from catchup.mapping.schemas import OktaUser as OktaUserSchema

# logger = logging.getLogger(__name__)

# class OktaClient:
#     BASE_URL = f"https://{auth_settings.OKTA_DOMAIN}/api/v1/users"
#     HEADERS = {
#         "Authorization": f"SSWS {auth_settings.OKTA_API_KEY}",
#         "Accept": "application/json",
#         "Content-Type": "application/json"
#     }
    
#     async def get_parsed_users(self) -> list[OktaUserSchema]:
#         raw_data = await self._fetch_all_okta_users()
#         return self._parse_users(raw_data)
    
#     async def _fetch_all_okta_users(self) -> list:
#         async with httpx.AsyncClient() as client:
#             response = await client.get(self.BASE_URL, headers=self.HEADERS)
#             response.raise_for_status()
#             return response.json()

#     def _parse_users(self, raw_data: list) -> list[OktaUserSchema]:
#         okta_users = []
#         for user in raw_data:
#             profile = user.get("profile", {})
#             full_name = self._combine_name(
#                 profile.get("firstName", ""), 
#                 profile.get("lastName", "")
#             )
            
#             okta_users.append(OktaUserSchema(
#                 okta_uid=user["id"],
#                 email=profile.get("email"),
#                 name=full_name,
#                 status=user.get("status", "UNKNOWN")
#             ))
#         return okta_users

#     def _combine_name(self, first_name: str, last_name: str) -> str:
#         f = first_name.strip()
#         l = last_name.strip()
#         if re.search(r"[ㄱ-ㅎㅏ-ㅣ가-힣]", f + l):
#             return f"{l}{f}".strip()
#         return f"{f} {l}".strip()


import re
import httpx
import logging

from catchup.configs.config import auth_settings
from catchup.mapping.schemas import OktaUser as OktaUserSchema

logger = logging.getLogger(__name__)

class OktaClient:
    # Keycloak Admin API 경로 (기존 변수명 유지)
    BASE_URL = f"{auth_settings.KC_INTERNAL_URL}/admin/realms/{auth_settings.KC_REALM}/users"
    
    async def get_parsed_users(self) -> list[OktaUserSchema]:
        # Keycloak Admin API는 호출 전 전용 토큰이 필요함
        raw_data = await self._fetch_all_okta_users()
        return self._parse_users(raw_data)
    
    async def _fetch_all_okta_users(self) -> list:
        # 1. Admin API 호출을 위한 Access Token 먼저 획득
        token = await self._get_admin_token()
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            # Keycloak 기본값은 100명이므로 max 파라미터 추가
            response = await client.get(f"{self.BASE_URL}?max=1000", headers=headers)
            response.raise_for_status()
            return response.json()

    async def _get_admin_token(self) -> str:
        """Keycloak Admin API 인증을 위한 토큰 발급"""
        # Admin 전용 토큰 엔드포인트
        url = f"{auth_settings.KC_INTERNAL_URL}/realms/master/protocol/openid-connect/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": auth_settings.KC_ADMIN_CLIENT_ID, # Admin 권한 Client ID
            "client_secret": auth_settings.KC_ADMIN_CLIENT_SECRET,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data)
            response.raise_for_status()
            return response.json().get("access_token")

    def _parse_users(self, raw_data: list) -> list[OktaUserSchema]:
        okta_users = []
        for user in raw_data:
            # Keycloak은 firstName, lastName이 루트에 바로 있음
            first_name = user.get("firstName", "")
            last_name = user.get("lastName", "")
            
            full_name = self._combine_name(first_name, last_name)
            
            # 리턴 타입 및 필드명 유지
            okta_users.append(OktaUserSchema(
                okta_uid=user["id"], # Keycloak UUID
                email=user.get("email"),
                name=full_name or user.get("username"),
                status="ACTIVE" if user.get("enabled") else "DEACTIVATED"
            ))
        return okta_users

    def _combine_name(self, first_name: str, last_name: str) -> str:
        f = first_name.strip()
        l = last_name.strip()
        if not f and not l:
            return ""
        if re.search(r"[ㄱ-ㅎㅏ-ㅣ가-힣]", f + l):
            return f"{l}{f}".strip()
        return f"{f} {l}".strip()