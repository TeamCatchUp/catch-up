import time
from functools import lru_cache
from pathlib import Path

import httpx
import jwt

from catchup.configs.config import settings

class GithubAppService:
    '''
    GithubApp 인증 서비스
    - JWT 객체 생성 (Private Key 서명)
    - Installation Access Token 발급
    '''

    GITHUB_API_BASE = "https://api.github.com"

    def __init__(
            self,
            app_id: int,
            private_key: str):
        self.app_id = app_id
        self.private_key = private_key

    def _create_jwt(self) -> str:
        """
        GitHub App 인증용 JWT 생성
        - Time Out : 10분
        - Signing Algorithm : RS256
        """
        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + (10 * 60),  # 10분
            "iss": self.app_id,
        }
        return jwt.encode(payload, self.private_key, algorithm="RS256")
    
    async def get_installation_access_token(self, installation_id: int) -> dict:
        """
        Installation Access Token 발급
        - 유효 시간: 1시간
        - Repository 접근에 사용
        """
        jwt_token = self._create_jwt()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response.raise_for_status()
            return response.json()
        
    async def get_app_info(self) -> dict:
        """GitHub App 정보 조회 (Health Check)"""
        jwt_token = self._create_jwt()
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.GITHUB_API_BASE}/app",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response.raise_for_status()
            return response.json()
        
def _load_private_key() -> str:
        """Private Key 파일 로드"""
        key_path = Path(settings.GITHUB_APP_PRIVATE_KEY_PATH)
        if not key_path.exists():
            raise FileNotFoundError(f"GitHub App Private Key not found: {key_path}")
        return key_path.read_text()
    
@lru_cache
def get_github_app_service() -> GithubAppService:
    """GitHubAppService 싱글톤 팩토리"""
    private_key = _load_private_key()
    return GithubAppService(
        app_id=settings.GITHUB_APP_ID,
        private_key=private_key,
    )