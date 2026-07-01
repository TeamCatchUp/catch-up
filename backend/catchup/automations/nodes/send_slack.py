from __future__ import annotations

import asyncio
import re
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from urllib.parse import unquote
from urllib.parse import unquote_plus

import structlog

from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.db.engine import SessionLocal
from catchup.db.slack.oauth_repository import get_slack_token_by_id

logger = structlog.get_logger(__name__)

_USER_CHAT_URL_RE = re.compile(
    r"https?://[^\s<|>]+/(?:user-chats|user_chats)/(?P<user_chat_id>[^\s<|>/?#]+)"
)
_SEARCH_WINDOW_MINIMUM = timedelta(minutes=30)
_SEARCH_WINDOW_BUFFER = timedelta(minutes=10)
_SLACK_MARKDOWN_BLOCK_TEXT_LIMIT = 12_000
_LINK_SEARCH_MAX_ATTEMPTS = 5
_LINK_SEARCH_INITIAL_DELAY_SECONDS = 5.0
_LINK_SEARCH_BACKOFF_FACTOR = 2.0
_LINK_SEARCH_MAX_DELAY_SECONDS = 25.0


def _message_contains_user_chat_id(message: dict[str, Any], user_chat_id: str) -> bool:
    """메시지 내 Channel Talk user_chat_id URL 포함 여부를 확인한다."""
    texts: list[str] = []
    _collect_strings(message, texts)
    for text in texts:
        for match in _USER_CHAT_URL_RE.finditer(text):
            segment = match.group("user_chat_id")
            candidates = {segment, unquote(segment), unquote_plus(segment)}
            if any(
                c == user_chat_id or c.endswith(f"-{user_chat_id}") for c in candidates
            ):
                return True
    return False


def _collect_strings(value: Any, result: list[str]) -> None:
    if isinstance(value, str):
        result.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            _collect_strings(v, result)
    elif isinstance(value, list):
        for item in value:
            _collect_strings(item, result)


def _is_bot_message(message: dict[str, Any]) -> bool:
    if message.get("bot_id"):
        return True
    return message.get("subtype") == "bot_message"


def _slack_ts(value: datetime) -> str:
    return f"{value.timestamp():.6f}"


def _build_thread_reply_blocks(message: str) -> list[dict[str, str]] | None:
    if len(message) > _SLACK_MARKDOWN_BLOCK_TEXT_LIMIT:
        return None
    return [{"type": "markdown", "text": message}]


async def _find_linked_message(
    client: SlackApiClientWrapper,
    *,
    channel_id: str,
    user_chat_id: str,
    oldest_at: datetime,
) -> dict[str, Any] | None:
    """채널 히스토리에서 user_chat_id가 링크된 최신 봇 메시지를 찾는다.

    Channel Talk의 자체 Slack 연동이 메시지를 올리는 시점은 이 파이프라인이
    통제할 수 없으므로, latest 경계를 매 호출 시점의 now로 새로 잡아야
    호출 사이에 새로 올라온 메시지를 포착할 수 있다.
    """
    now = datetime.now(timezone.utc)
    cursor: str | None = None
    newest_match: dict[str, Any] | None = None

    while True:
        response = await client.get_conversation_history(
            channel=channel_id,
            oldest=_slack_ts(oldest_at),
            latest=_slack_ts(now),
            cursor=cursor,
            limit=15,
            inclusive=True,
        )
        for message in response.get("messages", []):
            if not isinstance(message, dict):
                continue
            if not _is_bot_message(message):
                continue
            if not _message_contains_user_chat_id(message, user_chat_id):
                continue
            msg_ts = str(message.get("ts", ""))
            if newest_match is None or msg_ts > str(newest_match.get("ts", "")):
                newest_match = message
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not response.get("has_more") or not cursor:
            break

    return newest_match


async def send_slack_node(state: dict[str, Any]) -> dict[str, Any]:
    """Channel Talk 연동 Slack 스레드에 대응 가이드를 발송한다."""
    guide_text: str = state.get("guide_text") or ""
    if not guide_text:
        logger.warning("send_slack_node_skipped", reason="empty_guide_text")
        return {}

    user_chat_id: str = state["user_chat_id"]
    channel_id: str = state["slack_channel_id"]
    credential_id: int = state["slack_credential_id"]

    def _get_token_sync() -> Any:
        with SessionLocal() as db:
            return get_slack_token_by_id(db, credential_id)

    token = await asyncio.to_thread(_get_token_sync)
    if token is None or not token.bot_access_token or not token.team_id:
        raise RuntimeError(
            f"Slack credentials not found for credential_id={credential_id}"
        )

    client = SlackApiClientWrapper(token.bot_access_token, token.team_id)

    quiet_period_seconds: int | None = state.get("quiet_period_seconds")
    search_window = max(
        _SEARCH_WINDOW_MINIMUM,
        timedelta(seconds=quiet_period_seconds) + _SEARCH_WINDOW_BUFFER
        if quiet_period_seconds
        else _SEARCH_WINDOW_MINIMUM,
    )

    oldest_at = datetime.now(timezone.utc) - search_window

    newest_match: dict[str, Any] | None = None
    delay_seconds = _LINK_SEARCH_INITIAL_DELAY_SECONDS
    for attempt in range(1, _LINK_SEARCH_MAX_ATTEMPTS + 1):
        newest_match = await _find_linked_message(
            client,
            channel_id=channel_id,
            user_chat_id=user_chat_id,
            oldest_at=oldest_at,
        )
        if newest_match is not None:
            break
        if attempt == _LINK_SEARCH_MAX_ATTEMPTS:
            break
        logger.warning(
            "send_slack_node_link_not_found_retrying",
            user_chat_id=user_chat_id,
            attempt=attempt,
            next_delay_seconds=delay_seconds,
        )
        await asyncio.sleep(delay_seconds)
        delay_seconds = min(
            delay_seconds * _LINK_SEARCH_BACKOFF_FACTOR, _LINK_SEARCH_MAX_DELAY_SECONDS
        )

    if newest_match is None:
        logger.error(
            "send_slack_node_link_not_found",
            user_chat_id=user_chat_id,
            channel_id=channel_id,
            attempts=_LINK_SEARCH_MAX_ATTEMPTS,
        )
        raise RuntimeError(
            f"Channel Talk linked Slack message not found for user_chat_id={user_chat_id}"
        )

    message_ts = str(newest_match.get("ts") or "").strip()
    if not message_ts:
        raise RuntimeError("Matched Slack message is missing ts")

    await client.post_message(
        channel=channel_id,
        text=guide_text,
        thread_ts=message_ts,
        blocks=_build_thread_reply_blocks(guide_text),
    )

    logger.info(
        "send_slack_node_completed",
        channel_id=channel_id,
        thread_ts=message_ts,
        user_chat_id=user_chat_id,
    )
    return {}
