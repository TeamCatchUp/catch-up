import re
import httpx
import logging
import json
import jwt


logger = logging.getLogger(__name__)


class KeycloakAdminClient:
    
    def __init__(
        self,
        client: httpx.AsyncClient,
        server_url: str,  # Internal URL
        realm: str,
        client_id: str,
        client_secret: str
    ):
        self.client = client
        self.client_id = client_id
        self.client_secret = client_secret
        
        base_url = server_url.rstrip("/")
        self.users_url = f"{base_url}/admin/realms/{realm}/users"
        self.token_url = f"{base_url}/realms/{realm}/protocol/openid-connect/token"
    
    async def get_parsed_users(self) -> list[dict]:
        raw_data = await self._fetch_all_keycloak_users()
        return self._parse_users(raw_data)
    
    async def _fetch_all_keycloak_users(self) -> list:
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
        
        request_url = f"{self.users_url}?max=1000"
        logger.info(f"Keycloak 유저 목록 요청 시작: {request_url}")
        
        response = await self.client.get(request_url, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"유저 조회 실패 (Status: {response.status_code}) | Body: {response.text}")
        
        response.raise_for_status()
        users_data = response.json()
        logger.info(f"유저 목록 수신 완료 (총 {len(users_data)}명)")
        return users_data

    async def _get_admin_token(self) -> str:
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        
        response = await self.client.post(
            url=self.token_url,
            data=data
        )
        
        if response.status_code != 200:
            logger.error(f"토큰 발급 실패 (Status: {response.status_code}) | Body: {response.text}")
        
        response.raise_for_status()
        token = response.json().get("access_token")
        logger.debug(f"토큰 발급 완료: {token[:10]}...(truncated)")
        return token

    def _parse_users(
        self,
        raw_data: list
    ) -> list[dict]:
        oauth_users = []
        for user in raw_data:
            first_name = user.get("firstName", "")
            last_name = user.get("lastName", "")
            full_name = self._combine_name(first_name, last_name)
            
            oauth_users.append({
                "sub": user["id"],
                "email": user.get("email"),
                "name": full_name or user.get("username"),
                "status": "ACTIVE" if user.get("enabled") else "DEACTIVATED"
            })

        return oauth_users

    def _combine_name(
        self,
        first_name: str,
        last_name: str
    ) -> str:
        f = first_name.strip()
        l = last_name.strip()
        if not f and not l: return ""
        
        # 한국어 이름 처리
        if re.search(r"[ㄱ-ㅎㅏ-ㅣ가-힣]", f + l):
            return f"{l}{f}".strip()
        return f"{f} {l}".strip()