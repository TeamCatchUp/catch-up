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
from time import monotonic
from typing import Any

import structlog
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_base_client import async_default_handlers
from slack_sdk.web.async_client import AsyncWebClient

from catchup.configs.config import settings
from catchup.connectors.base.exceptions import ConnectorApiError
from catchup.connectors.base.exceptions import RateLimitError
from catchup.connectors.base.retry import parse_retry_after_header
from catchup.connectors.slack.rate_limiter import get_slack_rate_limiter

logger = structlog.getLogger(__name__)


class SlackConnectorApiError(ConnectorApiError):
    service = "slack"


class SlackRateLimitError(RateLimitError, SlackConnectorApiError):
    service = "slack"


class SlackApiClientWrapper:
    """
    Slack SDK AsyncWebClient 래퍼

    특징:
    - Slack SDK의 AsyncWebClient 사용 (aiohttp 기반)
    - Rate Limit 자동 처리 (Retry-After 기반)
    - 팀 단위 rate limiter로 호출 시작 시점 제어
    """

    def __init__(self, access_token: str, team_id: str):
        """
        SlackApiClientWrapper 초기화

        Args:
            access_token: Slack Bot Access Token (xoxb-...)
            team_id: Slack Team/Workspace ID
        """
        self.team_id = team_id
        retry_handlers = [
            *async_default_handlers(),
        ]
        self.client = AsyncWebClient(
            token=access_token,
            retry_handlers=retry_handlers,
        )

    @staticmethod
    def _response_get(response: Any, key: str, default: Any = None) -> Any:
        if response is None:
            return default

        getter = getattr(response, "get", None)
        if callable(getter):
            return getter(key, default)

        try:
            return response[key]
        except (KeyError, TypeError):
            return default

    @staticmethod
    def _extract_headers(response: Any) -> dict[str, str]:
        headers = getattr(response, "headers", None)
        if headers is None or not hasattr(headers, "items"):
            return {}
        return {str(key): str(value) for key, value in headers.items()}

    def _build_api_error(
        self,
        api_name: str,
        exc: SlackApiError,
    ) -> SlackConnectorApiError:
        response = exc.response
        status_code = getattr(response, "status_code", None)
        headers = self._extract_headers(response)
        header_lookup = {key.lower(): value for key, value in headers.items()}
        error_code = self._response_get(response, "error")
        has_retry_after = "retry-after" in header_lookup
        retry_after = (
            parse_retry_after_header(header_lookup.get("retry-after"), default=1)
            if has_retry_after
            else None
        )
        metadata = {
            "team_id": self.team_id,
            "api_name": api_name,
            "error": error_code,
            "headers": {
                key: value
                for key, value in headers.items()
                if key.lower() in {"retry-after", "x-slack-req-id"}
            },
        }
        if status_code is not None:
            metadata["status_code"] = status_code
        if retry_after is not None:
            metadata["retry_after"] = retry_after

        if status_code == 429 or error_code == "ratelimited" or retry_after is not None:
            delay = retry_after or 1
            return SlackRateLimitError(
                message=f"Slack API rate limited during {api_name}",
                retry_after=delay,
                metadata=metadata,
            )

        return SlackConnectorApiError(
            message=f"Slack API error during {api_name}: {error_code or exc}",
            status_code=status_code,
            metadata=metadata,
        )

    async def _call_api(
        self,
        api_name: str,
        client_method: str,
        **kwargs,
    ) -> dict[str, Any]:
        limiter = await get_slack_rate_limiter(self.team_id)
        started_at = monotonic()

        while True:
            delay = await limiter.acquire_delay()
            if delay > 0:
                await asyncio.sleep(delay)

            try:
                response = await getattr(self.client, client_method)(**kwargs)
                return response.data
            except SlackApiError as exc:
                error = self._build_api_error(api_name, exc)

                if isinstance(error, SlackRateLimitError):
                    waited = monotonic() - started_at
                    remaining = (
                        float(settings.SLACK_API_MAX_WAIT_SECONDS_PER_CALL) - waited
                    )
                    if remaining <= 0:
                        logger.error(
                            "slack_max_wait_seconds_exhausted",
                            team_id=self.team_id,
                            api_name=api_name,
                            waited_seconds=waited,
                            retry_after=error.retry_after,
                        )
                        raise error from exc

                    retry_after = max(1, int(error.retry_after or 1))
                    sleep_for = min(float(retry_after), max(0.0, remaining))

                    logger.warning(
                        "slack_api_rate_limited",
                        team_id=self.team_id,
                        api_name=api_name,
                        retry_after=retry_after,
                        sleep_for=sleep_for,
                        waited_seconds=waited,
                    )
                    await asyncio.sleep(sleep_for)
                    continue

                logger.error(
                    "slack_api_failed",
                    api_name=api_name,
                    team_id=self.team_id,
                    status_code=error.status_code,
                    error_code=error.metadata.get("error"),
                    retry_after=error.retry_after,
                )
                raise error from exc

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
        return await self._call_api(
            "conversations_list",
            "conversations_list",
            types=types,
            exclude_archived=exclude_archived,
            cursor=cursor,
            limit=limit,
        )

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
        return await self._call_api(
            "conversations_info",
            "conversations_info",
            channel=channel,
            include_num_members=include_num_members,
        )

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
        return await self._call_api(
            "conversations_members",
            "conversations_members",
            channel=channel,
            cursor=cursor,
            limit=limit,
        )

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
        return await self._call_api(
            "conversations_history",
            "conversations_history",
            channel=channel,
            oldest=oldest,
            latest=latest,
            cursor=cursor,
            limit=limit,
            inclusive=inclusive,
        )

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
        return await self._call_api(
            "conversations_replies",
            "conversations_replies",
            channel=channel,
            ts=ts,
            oldest=oldest,
            latest=latest,
            cursor=cursor,
            limit=limit,
            inclusive=inclusive,
        )

    async def list_message_ids(
        self,
        channel: str,
        oldest: str | None = None,
    ) -> list[str]:
        """
        기간 내 채널 메시지 ts 목록 조회

        Args:
            channel: 채널 ID
            oldest: 시작 timestamp

        Returns:
            메시지 ts 리스트
        """
        message_ids: list[str] = []
        cursor: str | None = None

        while True:
            response = await self.get_conversation_history(
                channel=channel,
                oldest=oldest,
                cursor=cursor,
                limit=settings.SLACK_MESSAGE_BATCH_SIZE,
            )

            for message in response.get("messages", []):
                message_ts = message.get("ts")
                if message_ts:
                    message_ids.append(message_ts)

            if not response.get("has_more"):
                break

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        return message_ids

    async def get_message(
        self,
        channel: str,
        ts: str,
    ) -> dict[str, Any] | None:
        """
        특정 ts의 메시지 1건 조회

        Args:
            channel: 채널 ID
            ts: 메시지 timestamp

        Returns:
            Slack 메시지 dict 또는 None
        """
        response = await self.get_conversation_history(
            channel=channel,
            oldest=ts,
            latest=ts,
            limit=1,
            inclusive=True,
        )

        for message in response.get("messages", []):
            if message.get("ts") == ts:
                return message

        return None

    async def post_message(
        self,
        *,
        channel: str,
        text: str,
        thread_ts: str | None = None,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return await self._call_api(
            "chat_postMessage",
            "chat_postMessage",
            channel=channel,
            text=text,
            thread_ts=thread_ts,
            blocks=blocks,
        )

    async def start_stream(
        self,
        *,
        channel: str,
        thread_ts: str,
        recipient_user_id: str,
        recipient_team_id: str,
        task_display_mode: str,
        chunks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self._call_api(
            "chat_startStream",
            "api_call",
            api_method="chat.startStream",
            json={
                "channel": channel,
                "thread_ts": thread_ts,
                "recipient_user_id": recipient_user_id,
                "recipient_team_id": recipient_team_id,
                "task_display_mode": task_display_mode,
                "chunks": chunks,
            },
        )

    async def append_stream(
        self,
        *,
        channel: str,
        ts: str,
        markdown_text: str | None = None,
        chunks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "channel": channel,
            "ts": ts,
        }
        if chunks is not None:
            payload["chunks"] = chunks
        if markdown_text is not None:
            payload["markdown_text"] = markdown_text

        return await self._call_api(
            "chat_appendStream",
            "api_call",
            api_method="chat.appendStream",
            json=payload,
        )

    async def stop_stream(
        self,
        *,
        channel: str,
        ts: str,
        chunks: list[dict[str, Any]] | None = None,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "channel": channel,
            "ts": ts,
        }
        if chunks:
            payload["chunks"] = chunks
        if blocks is not None:
            payload["blocks"] = blocks

        return await self._call_api(
            "chat_stopStream",
            "api_call",
            api_method="chat.stopStream",
            json=payload,
        )

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
        return await self._call_api(
            "users_list",
            "users_list",
            cursor=cursor,
            limit=limit,
        )

    # ================================================================
    # Team API
    # ================================================================

    async def get_team_info(self) -> dict[str, Any]:
        """
        Workspace(Team) 정보 조회

        Returns:
            team 정보 포함된 응답
        """
        return await self._call_api(
            "team_info",
            "team_info",
        )

    # ================================================================
    # Utility APIs
    # ================================================================

    async def auth_test(self) -> dict[str, Any]:
        """
        토큰 유효성 확인

        Returns:
            user_id, team_id, bot_id 등 포함된 응답
        """
        return await self._call_api(
            "auth_test",
            "auth_test",
        )
