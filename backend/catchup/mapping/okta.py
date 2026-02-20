import re
import httpx
import logging

from catchup.configs.config import auth_settings
from catchup.mapping.schemas import OktaUser as OktaUserSchema

logger = logging.getLogger(__name__)

class OktaClient:
    BASE_URL = f"https://{auth_settings.OKTA_DOMAIN}/api/v1/users"
    HEADERS = {
        "Authorization": f"SSWS {auth_settings.OKTA_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    async def get_parsed_users(self) -> list[OktaUserSchema]:
        raw_data = await self._fetch_all_okta_users()
        return self._parse_users(raw_data)
    
    async def _fetch_all_okta_users(self) -> list:
        async with httpx.AsyncClient() as client:
            response = await client.get(self.BASE_URL, headers=self.HEADERS)
            response.raise_for_status()
            return response.json()

    def _parse_users(self, raw_data: list) -> list[OktaUserSchema]:
        okta_users = []
        for user in raw_data:
            profile = user.get("profile", {})
            full_name = self._combine_name(
                profile.get("firstName", ""), 
                profile.get("lastName", "")
            )
            
            okta_users.append(OktaUserSchema(
                okta_uid=user["id"],
                email=profile.get("email"),
                name=full_name,
                status=user.get("status", "UNKNOWN")
            ))
        return okta_users

    def _combine_name(self, first_name: str, last_name: str) -> str:
        f = first_name.strip()
        l = last_name.strip()
        if re.search(r"[ㄱ-ㅎㅏ-ㅣ가-힣]", f + l):
            return f"{l}{f}".strip()
        return f"{f} {l}".strip()
