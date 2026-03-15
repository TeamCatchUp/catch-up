"""
Slack OAuth Service

Slack OAuth 2.0 V2 인증을 담당하는 서비스.
- Authorization URL 생성
- Code → Token 교환
- Token 갱신
- Workspace 정보 조회
- 인증 상태 확인
- Token 취소
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from catchup.connectors.slack.schemas import SlackOAuthTokenResponse
from catchup.configs.config import settings
from catchup.db.models import SlackOAuthToken

logger = logging.getLogger(__name__)


class SlackOAuthService:
    """
    Slack OAuth 2.0 V2 서비스
    - Authorization URL 생성
    - Code → Token 교환
    - Token 갱신 TODO : Token Rotation 적용
    - Workspace 정보 조회
    """

    def __init__(self):
        self.client_id = settings.SLACK_CLIENT_ID
        self.client_secret = settings.SLACK_CLIENT_SECRET
        self.redirect_uri = settings.SLACK_REDIRECT_URI
        self.bot_scopes = settings.SLACK_BOT_SCOPES
        self.auth_url = settings.SLACK_AUTH_URL
        self.token_url = settings.SLACK_TOKEN_URL
        self.api_url = settings.SLACK_API_URL
        self._max_rate_limit_retries = 3

    def get_authorization_url(self, state: str | None = None) -> str:
        params = {
            "client_id": self.client_id,
            "scope": self.bot_scopes,
            "redirect_uri": self.redirect_uri,
        }

        if state:
            params["state"] = state

        return f"{self.auth_url}?{urlencode(params)}"

    async def exchange_code_for_tokens(self, code: str) -> SlackOAuthTokenResponse:
        """Authorization Code를 Token으로 교환"""
        async with httpx.AsyncClient() as client:
            response = await self._request_with_retry(
                client,
                "POST",
                self.token_url,
                data={
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
                auth=(self.client_id, self.client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            data = response.json()

            if not data.get("ok"):
                error = data.get("error", "unknown_error")
                logger.error(f"Slack OAuth Token 교환 실패: {error}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Slack OAuth 실패: {error}",
                )

            return self._parse_token_response(data)

    async def refresh_access_token(
        self, refresh_token: str
    ) -> SlackOAuthTokenResponse:
        """Token Rotation을 사용하는 경우 토큰 갱신"""
        async with httpx.AsyncClient() as client:
            response = await self._request_with_retry(
                client,
                "POST",
                self.token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                auth=(self.client_id, self.client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            data = response.json()

            if not data.get("ok"):
                error = data.get("error", "unknown_error")
                logger.error(f"Slack Token 갱신 실패: {error}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Slack Token 갱신 실패: {error}",
                )

            return self._parse_token_response(data)

    async def get_team_info(self, access_token: str) -> dict:
        """Team(Workspace) 정보 조회"""
        async with httpx.AsyncClient() as client:
            response = await self._request_with_retry(
                client,
                "GET",
                f"{self.api_url}/team.info",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            data = response.json()

            if not data.get("ok"):
                logger.error(f"Slack Team 정보 조회 실패: {data.get('error')}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Team 정보 조회 실패: {data.get('error')}",
                )

            return data.get("team", {})

    async def test_auth(self, access_token: str) -> dict:
        """인증 상태 확인 (auth.test)"""
        async with httpx.AsyncClient() as client:
            response = await self._request_with_retry(
                client,
                "POST",
                f"{self.api_url}/auth.test",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            data = response.json()

            if not data.get("ok"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"인증 실패: {data.get('error')}",
                )

            return data

    async def revoke_token(self, access_token: str) -> bool:
        """Token 취소 (연결 해제 시)"""
        async with httpx.AsyncClient() as client:
            response = await self._request_with_retry(
                client,
                "POST",
                f"{self.api_url}/auth.revoke",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            data = response.json()
            return data.get("ok", False)

    def _get_retry_after(self, response: httpx.Response) -> int:
        retry_after = response.headers.get("Retry-After")
        if retry_after is None:
            return 1

        try:
            return max(1, int(retry_after))
        except ValueError:
            return 1

    async def _request_with_retry(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        **kwargs,
    ) -> httpx.Response:
        retry_count = 0

        while True:
            response = await client.request(method, url, **kwargs)
            if response.status_code != status.HTTP_429_TOO_MANY_REQUESTS:
                return response

            retry_after = self._get_retry_after(response)
            if retry_count >= self._max_rate_limit_retries:
                logger.error(
                    "[SLACK][API] Rate limit retry exhausted: url=%s, retry_after=%ss",
                    url,
                    retry_after,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Slack API rate limit exceeded",
                )

            retry_count += 1
            logger.warning(
                "[SLACK][API] Rate limited. Waiting %ss before retry (attempt %s/%s): %s",
                retry_after,
                retry_count,
                self._max_rate_limit_retries,
                url,
            )
            await asyncio.sleep(retry_after)

    async def get_valid_access_token(
        self, db: Session, slack_token: SlackOAuthToken
    ) -> str:
        """
        유효한 Access Token 반환
        - Token Rotation 사용 시 만료 임박하면 갱신
        - Token Rotation 미사용 시 그대로 반환
        """
        # Token Rotation 미사용 (만료 시간 없음)
        if slack_token.bot_token_expires_at is None:
            return slack_token.bot_access_token

        # Token Rotation 사용: 5분 버퍼로 갱신 체크
        buffer_time = timedelta(minutes=5)
        if slack_token.bot_token_expires_at <= datetime.now(timezone.utc) + buffer_time:
            if not slack_token.bot_refresh_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token 만료되었으나 refresh token 없음",
                )

            logger.info(f"Slack Access Token 갱신: Team ID = {slack_token.team_id}")
            new_tokens = await self.refresh_access_token(slack_token.bot_refresh_token)

            slack_token.bot_access_token = new_tokens.access_token
            slack_token.bot_scopes = new_tokens.scope

            if new_tokens.refresh_token:
                slack_token.bot_refresh_token = new_tokens.refresh_token

            if new_tokens.expires_in:
                slack_token.bot_token_expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=new_tokens.expires_in
                )

            db.commit()
            db.refresh(slack_token)

        return slack_token.bot_access_token

    def _parse_token_response(self, data: dict) -> SlackOAuthTokenResponse:
        return SlackOAuthTokenResponse.model_validate(data)


@lru_cache(maxsize=1)
def get_slack_oauth_service() -> SlackOAuthService:
    return SlackOAuthService()
