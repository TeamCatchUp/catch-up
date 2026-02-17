"""
Atlassian OAuth Service

Atlassian OAuth 2.0 3LO 인증을 담당하는 공통 서비스
Jira/Confluence 모두 동일한 OAuth 앱 및 Access Token 흐름을 사용
"""

import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from catchup.connectors.atlassian.schemas import (
    AtlassianAccessibleResource,
    AtlassianOAuthTokenResponse,
    AtlassianUserInfo,
)
from catchup.configs.config import settings
from catchup.db.models import AtlassianOAuthToken

logger = logging.getLogger(__name__)


class AtlassianOAuthService:
    """Atlassian OAuth 2.0 3LO 공통 서비스."""

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
        """Authorization Code로 토큰 교환."""
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
                    f"[ATLASSIAN][AUTH] Token exchange failed: {response.text}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to exchange code for tokens: {response.text}",
                )

            data = response.json()
            refresh_token = data.get("refresh_token")
            access_token = data.get("access_token")
            expires_in = data.get("expires_in")

            # Atlassian 정책/앱 설정에 따라 refresh_token이 비어올 수 있어
            # KeyError 대신 인증 실패 응답으로 명확히 종료한다.
            if not refresh_token or not access_token or not expires_in:
                logger.error(
                    "[ATLASSIAN][AUTH] Token response missing required fields: %s",
                    data,
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange code for tokens: missing required fields",
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
        """Refresh Token으로 Access Token 갱신."""
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
                logger.error(f"[ATLASSIAN][AUTH] Token refresh failed: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=(
                        "Atlassian 인증이 만료되었습니다. 다시 연결해주세요. "
                        "(/api/v1/auth/atlassian/install)"
                    ),
                )

            data = response.json()
            access_token = data.get("access_token")
            expires_in = data.get("expires_in")

            if not access_token or not expires_in:
                logger.error(
                    "[ATLASSIAN][AUTH] Token refresh response missing required fields: %s",
                    data,
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=(
                        "Atlassian token refresh 응답이 유효하지 않습니다. "
                        "다시 연결해주세요. (/api/v1/auth/atlassian/install)"
                    ),
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
        """accessible-resources 조회 (Jira + Confluence 동시 포함 스코프 확인 가능)."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/oauth/token/accessible-resources",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code != 200:
                logger.error(
                    f"[ATLASSIAN][AUTH] Failed to fetch accessible resources: {response.text}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to fetch accessible resources: {response.text}",
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
                logger.error(f"[ATLASSIAN][AUTH] Failed to fetch user info: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to fetch user info: {response.text}",
                )

            data = response.json()
            return AtlassianUserInfo(
                account_id=data["account_id"],
                email=data.get("email"),
                name=data.get("name"),
                picture=data.get("picture"),
            )

    async def get_valid_access_token(
        self, db: Session, token: AtlassianOAuthToken
    ) -> str:
        """토큰 유효성 검사 후 필요시 갱신."""
        buffer_time = timedelta(minutes=5)
        if token.expires_at <= datetime.now(timezone.utc) + buffer_time:
            logger.info(
                f"[ATLASSIAN][AUTH] Refreshing Access Token: cloud_id={token.cloud_id}"
            )

            try:
                new_tokens = await self.refresh_access_token(token.refresh_token)

                token.access_token = new_tokens.access_token
                token.refresh_token = new_tokens.refresh_token
                token.expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=new_tokens.expires_in
                )
                db.commit()
                db.refresh(token)

            except HTTPException as e:
                if e.status_code == 401:
                    logger.warning(
                        f"[ATLASSIAN][AUTH] refresh_token expired: cloud_id={token.cloud_id}. "
                        "User needs to re-authenticate."
                    )
                raise

        return token.access_token


@lru_cache(maxsize=1)
def get_atlassian_oauth_service() -> AtlassianOAuthService:
    """Atlassian OAuth Service 싱글톤 팩토리."""
    return AtlassianOAuthService()
