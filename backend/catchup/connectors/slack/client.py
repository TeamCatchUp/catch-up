"""
Slack API Client

Slack SDK의 AsyncWebClient를 래핑하여 동시 요청 제어 및 에러 핸들링 제공.

사용법:
    client = SlackApiClientWrapper(access_token, team_id)

    # 채널 목록 조회
    channels = await client.list_conversations()

    # 메시지 히스토리 조회
    history = await client.get_conversation_history(channel_id, oldest="1704067200")
"""

import asyncio
import logging
from typing import Any

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

from catchup.configs.config import settings

logger = logging.getLogger(__name__)


class SlackApiClientWrapper:
    """
    Slack SDK AsyncWebClient 래퍼

    특징:
    - Slack SDK의 AsyncWebClient 사용 (aiohttp 기반)
    - Rate Limit 자동 처리 (SDK 내장)
    - 세마포어로 동시 요청 수 제어
    """

    def __init__(self, access_token: str, team_id: str):
        """
        SlackApiClientWrapper 초기화

        Args:
            access_token: Slack Bot Access Token (xoxb-...)
            team_id: Slack Team/Workspace ID
        """
        self.team_id = team_id
        self.client = AsyncWebClient(token=access_token)
        self._semaphore = asyncio.Semaphore(settings.SLACK_SYNC_MAX_CONCURRENT_REQUESTS)

    # ================================================================
    # Channel APIs
    # ================================================================

    async def list_conversations(
        self,
        types: str = "public_channel,private_channel",
        exclude_archived: bool = True,
        cursor: str | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        """
        Bot이 참여한 채널 목록 조회

        Args:
            types: 조회할 채널 타입 (public_channel, private_channel, mpim, im)
            exclude_archived: 아카이브된 채널 제외 여부
            cursor: 페이지네이션 커서
            limit: 한 번에 가져올 채널 수 (최대 1000)

        Returns:
            channels, response_metadata 포함된 응답
        """
        async with self._semaphore:
            try:
                response = await self.client.conversations_list(
                    types=types,
                    exclude_archived=exclude_archived,
                    cursor=cursor,
                    limit=limit,
                )
                return response.data
            except SlackApiError as e:
                logger.error(f"conversations_list failed: {e.response['error']}")
                raise

    async def get_conversation_info(
        self,
        channel: str,
        include_num_members: bool = True,
    ) -> dict[str, Any]:
        """
        채널 상세 정보 조회

        Args:
            channel: 채널 ID
            include_num_members: 멤버 수 포함 여부

        Returns:
            channel 정보 포함된 응답
        """
        async with self._semaphore:
            try:
                response = await self.client.conversations_info(
                    channel=channel,
                    include_num_members=include_num_members,
                )
                return response.data
            except SlackApiError as e:
                logger.error(f"conversations_info failed for {channel}: {e.response['error']}")
                raise

    async def get_conversation_members(
        self,
        channel: str,
        cursor: str | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        """
        채널 멤버 목록 조회

        Args:
            channel: 채널 ID
            cursor: 페이지네이션 커서
            limit: 한 번에 가져올 멤버 수

        Returns:
            members (user_id 리스트), response_metadata 포함된 응답
        """
        async with self._semaphore:
            try:
                response = await self.client.conversations_members(
                    channel=channel,
                    cursor=cursor,
                    limit=limit,
                )
                return response.data
            except SlackApiError as e:
                logger.error(f"conversations_members failed for {channel}: {e.response['error']}")
                raise

    # ================================================================
    # Message APIs
    # ================================================================

    async def get_conversation_history(
        self,
        channel: str,
        oldest: str | None = None,
        latest: str | None = None,
        cursor: str | None = None,
        limit: int = 200,
        inclusive: bool = True,
    ) -> dict[str, Any]:
        """
        채널 메시지 히스토리 조회

        Args:
            channel: 채널 ID
            oldest: 시작 timestamp (이 시간 이후 메시지만)
            latest: 종료 timestamp (이 시간 이전 메시지만)
            cursor: 페이지네이션 커서
            limit: 한 번에 가져올 메시지 수 (최대 1000)
            inclusive: oldest/latest 포함 여부

        Returns:
            messages, has_more, response_metadata 포함된 응답
        """
        async with self._semaphore:
            try:
                response = await self.client.conversations_history(
                    channel=channel,
                    oldest=oldest,
                    latest=latest,
                    cursor=cursor,
                    limit=limit,
                    inclusive=inclusive,
                )
                return response.data
            except SlackApiError as e:
                logger.error(f"conversations_history failed for {channel}: {e.response['error']}")
                raise

    async def get_conversation_replies(
        self,
        channel: str,
        ts: str,
        oldest: str | None = None,
        latest: str | None = None,
        cursor: str | None = None,
        limit: int = 200,
        inclusive: bool = True,
    ) -> dict[str, Any]:
        """
        Thread Reply 조회

        Args:
            channel: 채널 ID
            ts: Thread Parent 메시지 timestamp
            oldest: 시작 timestamp
            latest: 종료 timestamp
            cursor: 페이지네이션 커서
            limit: 한 번에 가져올 Reply 수

        Returns:
            messages (첫 번째는 parent), has_more 포함된 응답
        """
        async with self._semaphore:
            try:
                response = await self.client.conversations_replies(
                    channel=channel,
                    ts=ts,
                    oldest=oldest,
                    latest=latest,
                    cursor=cursor,
                    limit=limit,
                    inclusive=inclusive,
                )
                return response.data
            except SlackApiError as e:
                logger.error(f"conversations_replies failed for {channel}/{ts}: {e.response['error']}")
                raise

    # ================================================================
    # User APIs
    # ================================================================

    async def list_users(
        self,
        cursor: str | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        """
        Workspace 사용자 목록 조회

        Args:
            cursor: 페이지네이션 커서
            limit: 한 번에 가져올 사용자 수

        Returns:
            members (user 리스트), response_metadata 포함된 응답
        """
        async with self._semaphore:
            try:
                response = await self.client.users_list(
                    cursor=cursor,
                    limit=limit,
                )
                return response.data
            except SlackApiError as e:
                logger.error(f"users_list failed: {e.response['error']}")
                raise

    # ================================================================
    # Team API
    # ================================================================

    async def get_team_info(self) -> dict[str, Any]:
        """
        Workspace(Team) 정보 조회

        Returns:
            team 정보 포함된 응답
        """
        async with self._semaphore:
            try:
                response = await self.client.team_info()
                return response.data
            except SlackApiError as e:
                logger.error(f"team_info failed: {e.response['error']}")
                raise

    # ================================================================
    # Utility APIs
    # ================================================================

    async def auth_test(self) -> dict[str, Any]:
        """
        토큰 유효성 확인

        Returns:
            user_id, team_id, bot_id 등 포함된 응답
        """
        async with self._semaphore:
            try:
                response = await self.client.auth_test()
                return response.data
            except SlackApiError as e:
                logger.error(f"auth_test failed: {e.response['error']}")
                raise
