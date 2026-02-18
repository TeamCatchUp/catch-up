import logging
from functools import lru_cache
from urllib.parse import urlencode

import httpx

from catchup.connectors.atlassian.exceptions import (
    AtlassianAuthError,
    AtlassianResourceError,
    AtlassianTokenExpiredError,
)
from catchup.connectors.atlassian.schemas import (
    AtlassianAccessibleResource,
    AtlassianOAuthTokenResponse,
    AtlassianUserInfo,
)
from catchup.configs.config import settings

logger = logging.getLogger(__name__)




class AtlassianOAuthClient:

    def __init__(self):
        self.auth_url = settings.ATLASSIAN_AUTH_URL
        self.token_url = settings.ATLASSIAN_TOKEN_URL
        self.api_url = settings.ATLASSIAN_API_URL

    def get_authorization_url(self, state: str | None = None) -> str:
        """Atlassian OAuth 인가 URL 생성."""
        params = {
            "audience": "api.atlassian.com",
            "client_id": settings.ATLASSIAN_CLIENT_ID,
            "scope": settings.ATLASSIAN_SCOPES,
            "redirect_uri": settings.ATLASSIAN_REDIRECT_URI,
            "response_type": "code",
            "prompt": "consent",
        }
        if state:
            params["state"] = state
        return f"{self.auth_url}?{urlencode(params)}"

    async def exchange_code_for_tokens(
        self, code: str
    ) -> AtlassianOAuthTokenResponse:
        """Authorization Code → Token 교환."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                json={
                    "grant_type": "authorization_code",
                    "client_id": settings.ATLASSIAN_CLIENT_ID,
                    "client_secret": settings.ATLASSIAN_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": settings.ATLASSIAN_REDIRECT_URI,
                },
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200:
                logger.error(
                    "[ATLASSIAN][AUTH] Token exchange failed: %s", response.text
                )
                raise AtlassianAuthError(
                    f"Token exchange failed: {response.status_code}"
                )

            data = response.json()
            refresh_token = data.get("refresh_token")
            access_token = data.get("access_token")
            expires_in = data.get("expires_in")

            if not refresh_token or not access_token or not expires_in:
                logger.error(
                    "[ATLASSIAN][AUTH] Token response missing required fields: %s",
                    data,
                )
                raise AtlassianAuthError(
                    "Token exchange response missing required fields"
                )

            return AtlassianOAuthTokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type=data.get("token_type", "Bearer"),
                expires_in=expires_in,
                scope=data.get("scope", ""),
            )

    async def refresh_access_token(
        self, refresh_token: str
    ) -> AtlassianOAuthTokenResponse:
        """Refresh Token → 새 Access Token 발급."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                json={
                    "grant_type": "refresh_token",
                    "client_id": settings.ATLASSIAN_CLIENT_ID,
                    "client_secret": settings.ATLASSIAN_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                },
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200:
                logger.error(
                    "[ATLASSIAN][AUTH] Token refresh failed: %s", response.text
                )
                raise AtlassianTokenExpiredError()

            data = response.json()
            access_token = data.get("access_token")
            expires_in = data.get("expires_in")

            if not access_token or not expires_in:
                logger.error(
                    "[ATLASSIAN][AUTH] Token refresh response missing required fields: %s",
                    data,
                )
                raise AtlassianAuthError(
                    "Token refresh response missing required fields"
                )

            return AtlassianOAuthTokenResponse(
                access_token=access_token,
                refresh_token=data.get("refresh_token", refresh_token),
                token_type=data.get("token_type", "Bearer"),
                expires_in=expires_in,
                scope=data.get("scope", ""),
            )

    async def get_accessible_resources(
        self, access_token: str
    ) -> list[AtlassianAccessibleResource]:
        """Accessible Resources 조회."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/oauth/token/accessible-resources",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code != 200:
                logger.error(
                    "[ATLASSIAN][AUTH] Failed to fetch accessible resources: %s",
                    response.text,
                )
                raise AtlassianResourceError(
                    f"Failed to fetch accessible resources: {response.status_code}"
                )

            return [
                AtlassianAccessibleResource(
                    id=item["id"],
                    name=item["name"],
                    url=item["url"],
                    scopes=item.get("scopes", []),
                    avatar_url=item.get("avatarUrl"),
                )
                for item in response.json()
            ]

    async def get_user_info(self, access_token: str) -> AtlassianUserInfo:
        """Atlassian /me API 호출."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code != 200:
                logger.error(
                    "[ATLASSIAN][AUTH] Failed to fetch user info: %s", response.text
                )
                raise AtlassianResourceError(
                    f"Failed to fetch user info: {response.status_code}"
                )

            data = response.json()
            return AtlassianUserInfo(
                account_id=data["account_id"],
                email=data.get("email"),
                name=data.get("name"),
                picture=data.get("picture"),
            )
        

# ──────────────────────────────────────────
# 호환성 shim (Phase 3 마이그레이션 전까지 유지)
# ──────────────────────────────────────────

class AtlassianOAuthService(AtlassianOAuthClient):
    """
    기존 호환성 유지용 별칭.

    Phase 3에서 모든 사용처를 AtlassianOAuthClient로 마이그레이션한 후 제거.
    get_valid_access_token()은 token_manager.py로 이동됨.
    """

    async def get_valid_access_token(self, db, token):
        """
        호환성 shim — 새 코드에서는 token_manager.resolve_access_token() 사용.
        """
        from catchup.connectors.atlassian.token_manager import AtlassianTokenManager
        from catchup.db.atlassian import oauth_repository as repo

        manager = AtlassianTokenManager(oauth_client=self, oauth_repository=repo)
        return await manager.resolve_access_token(db, token)


@lru_cache(maxsize=1)
def get_atlassian_oauth_service() -> AtlassianOAuthService:
    """기존 호환성 유지용 싱글톤. Phase 3 이후 제거."""
    return AtlassianOAuthService()