import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from catchup.auth.jira.schemas import (
    JiraAccessibleResource,
    JiraOAuthTokenResponse,
    JiraUserInfo,
)
from catchup.configs.config import settings
from catchup.db.models import JiraOAuthToken

logger = logging.getLogger(__name__)


class JiraOAuthService:
    def __init__(self):
        self.auth_url = settings.ATLASSIAN_AUTH_URL
        self.token_url = settings.ATLASSIAN_TOKEN_URL
        self.api_url = settings.ATLASSIAN_API_URL

    def get_authorization_url(self, state: str | None = None) -> str:
        params = {
            "audience": "api.atlassian.com",
            "client_id": settings.JIRA_CLIENT_ID,
            "scope": settings.JIRA_SCOPES,
            "redirect_uri": settings.JIRA_REDIRECT_URI,
            "response_type": "code",
            "prompt": "consent",
        }
        if state:
            params["state"] = state
        return f"{self.auth_url}?{urlencode(params)}"

    async def exchange_code_for_tokens(self, code: str) -> JiraOAuthTokenResponse:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                json={
                    "grant_type": "authorization_code",
                    "client_id": settings.JIRA_CLIENT_ID,
                    "client_secret": settings.JIRA_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": settings.JIRA_REDIRECT_URI,
                },
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200:
                logger.error(f"Jira OAuth Token Exchange Failed: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to exchange code for tokens: {response.text}",
                )

            data = response.json()
            return JiraOAuthTokenResponse(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                token_type=data.get("token_type", "Bearer"),
                expires_in=data["expires_in"],
                scope=data.get("scope", ""),
            )

    async def refresh_access_token(self, refresh_token: str) -> JiraOAuthTokenResponse:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                json={
                    "grant_type": "refresh_token",
                    "client_id": settings.JIRA_CLIENT_ID,
                    "client_secret": settings.JIRA_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                },
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200:
                logger.error(f"Jira OAuth Token Refresh Failed: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Failed to refresh access token: {response.text}",
                )

            data = response.json()
            return JiraOAuthTokenResponse(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", refresh_token),
                token_type=data.get("token_type", "Bearer"),
                expires_in=data["expires_in"],
                scope=data.get("scope", ""),
            )

    async def get_accessible_resources(
        self, access_token: str
    ) -> list[JiraAccessibleResource]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/oauth/token/accessible-resources",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code != 200:
                logger.error(f"Failed to fetch Jira accessible resources: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to fetch accessible resources: {response.text}",
                )

            return [
                JiraAccessibleResource(
                    id=item["id"],
                    name=item["name"],
                    url=item["url"],
                    scopes=item.get("scopes", []),
                    avatar_url=item.get("avatarUrl"),
                )
                for item in response.json()
            ]

    async def get_user_info(self, access_token: str) -> JiraUserInfo:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code != 200:
                logger.error(f"Failed to fetch Jira user info: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to fetch user info: {response.text}",
                )

            data = response.json()
            return JiraUserInfo(
                account_id=data["account_id"],
                email=data.get("email"),
                name=data.get("name"),
                picture=data.get("picture"),
            )

    async def get_valid_access_token(
        self, db: Session, jira_token: JiraOAuthToken
    ) -> str:
        buffer_time = timedelta(minutes=5)
        if jira_token.expires_at <= datetime.now(timezone.utc) + buffer_time:
            logger.info(f"Refreshing Jira Access Token: Cloud ID = {jira_token.cloud_id}")

            new_tokens = await self.refresh_access_token(jira_token.refresh_token)

            jira_token.access_token = new_tokens.access_token
            jira_token.refresh_token = new_tokens.refresh_token
            jira_token.expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=new_tokens.expires_in
            )
            db.commit()
            db.refresh(jira_token)

        return jira_token.access_token


@lru_cache(maxsize=1)
def get_jira_oauth_service() -> JiraOAuthService:
    return JiraOAuthService()
