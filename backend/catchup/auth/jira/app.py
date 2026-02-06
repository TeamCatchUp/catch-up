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
        """
        Refresh Token으로 새 Access Token 발급

        Atlassian refresh_token 특성:
        - 유효 기간: 90일 (사용 시마다 갱신)
        - Token Rotation: refresh 시 새 refresh_token 발급
        - 90일간 미사용 또는 사용자가 앱 연결 해제 시 무효화

        Raises:
            HTTPException(401): refresh_token 만료/무효화 시
                - 사용자가 다시 OAuth 인증을 해야 함
        
        TODO : 주기적 refresh_token 유효성 검사 및 재발급 기능 고려
        """
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
                # refresh_token 만료 또는 무효화 시 재인증 필요
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Jira 인증이 만료되었습니다. 다시 연결해주세요. (/api/v1/auth/jira/install)",
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
        """
        유효한 Access Token 반환 (필요 시 자동 갱신)

        Access Token이 만료 5분 전이면 refresh_token으로 갱신.
        refresh_token도 만료/무효화된 경우 재인증 안내 예외 발생.

        Args:
            db: SQLAlchemy Session
            jira_token: DB에서 조회한 JiraOAuthToken 객체

        Returns:
            유효한 access_token 문자열

        Raises:
            HTTPException(401): refresh_token 만료 시 (재인증 필요)
        """
        buffer_time = timedelta(minutes=5)
        if jira_token.expires_at <= datetime.now(timezone.utc) + buffer_time:
            logger.info(f"Refreshing Jira Access Token: Cloud ID = {jira_token.cloud_id}")

            try:
                new_tokens = await self.refresh_access_token(jira_token.refresh_token)

                jira_token.access_token = new_tokens.access_token
                jira_token.refresh_token = new_tokens.refresh_token
                jira_token.expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=new_tokens.expires_in
                )
                db.commit()
                db.refresh(jira_token)

            except HTTPException as e:
                if e.status_code == 401:
                    # refresh_token 만료 → 토큰 레코드는 유지하되 로그 기록
                    logger.warning(
                        f"Jira refresh_token expired for cloud_id={jira_token.cloud_id}. "
                        "User needs to re-authenticate."
                    )
                raise

        return jira_token.access_token


@lru_cache(maxsize=1)
def get_jira_oauth_service() -> JiraOAuthService:
    return JiraOAuthService()
