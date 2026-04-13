from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import urlencode

import structlog

from catchup.chat.integrations.slack_app_mention import SlackChatAnswerRef
from catchup.configs.config import auth_settings

logger = structlog.get_logger(__name__)

VIEW_DETAIL_ACTION_ID = "view_detail"
HELPFUL_ACTION_ID = "feedback_helpful"
NOT_HELPFUL_ACTION_ID = "feedback_not_helpful"
SUPPORTED_FEEDBACK_ACTION_IDS = frozenset({HELPFUL_ACTION_ID, NOT_HELPFUL_ACTION_ID})

REASON_BLOCK_ID = "feedback_reason_block"
REASON_ACTION_ID = "feedback_reason_action"
COMMENT_BLOCK_ID = "feedback_comment_block"
COMMENT_ACTION_ID = "feedback_comment_action"

FEEDBACK_REASON_OPTIONS = [
    ("원하는 답이 아니에요", "IRRELEVANT_ANSWER"),
    ("출처가 정확하지 않아요", "NO_CITATION"),
    ("내용이 부족해요", "MISSING_INFO"),
    ("관련 없는 결과가 포함됐어요", "IRRELEVANT_SOURCE"),
]

DETAIL_BUTTON_TEXT = "Catch Up에서 자세히 보기"
HELPFUL_BUTTON_TEXT = "👍도움됐어요"
NOT_HELPFUL_BUTTON_TEXT = "👎 아쉬워요"
DETAIL_PROMPT_TEXT = "답변이 도움이 됐나요?"


class FeedbackProcessResult(StrEnum):
    READY = "ready"
    SUCCESS = "success"
    INVALID = "invalid"
    NOT_FOUND = "not_found"
    ALREADY_SUBMITTED = "already_submitted"


@dataclass(slots=True, frozen=True)
class SlackFeedbackActionPayload:
    # 변경 설명:
    # - 예전에는 button value를 orchestration 쪽에서 JSON 문자열로 직접 만들었다.
    # - 이제 feedback action payload를 타입으로 먼저 표현하고,
    #   Slack 직렬화는 이 shared 모듈이 담당한다.
    session_id: uuid.UUID
    message_id: int
    is_liked: bool


@dataclass(slots=True, frozen=True)
class SlackFeedbackContext:
    team_id: str
    channel_id: str
    message_ts: str
    slack_user_id: str | None = None
    thread_ts: str | None = None


@dataclass(slots=True, frozen=True)
class SlackFeedbackModalContext:
    action_payload: SlackFeedbackActionPayload
    feedback_context: SlackFeedbackContext


def build_action_blocks(answer_ref: SlackChatAnswerRef | None) -> list[dict[str, Any]]:

    if answer_ref is None:
        return []

    blocks: list[dict[str, Any]] = [{"type": "divider"}]
    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": DETAIL_PROMPT_TEXT,
            },
            "accessory": {
                "type": "button",
                "action_id": VIEW_DETAIL_ACTION_ID,
                "text": {
                    "type": "plain_text",
                    "text": DETAIL_BUTTON_TEXT,
                    "emoji": False,
                },
                "url": build_chat_room_redirect_url(
                    answer_ref.session_id,
                    scroll_to=answer_ref.assistant_message_id,
                ),
            },
        }
    )

    if answer_ref.assistant_message_id is None:
        return blocks

    payloads = (
        SlackFeedbackActionPayload(
            session_id=answer_ref.session_id,
            message_id=answer_ref.assistant_message_id,
            is_liked=True,
        ),
        SlackFeedbackActionPayload(
            session_id=answer_ref.session_id,
            message_id=answer_ref.assistant_message_id,
            is_liked=False,
        ),
    )

    blocks.append(
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "action_id": HELPFUL_ACTION_ID,
                    "text": {
                        "type": "plain_text",
                        "text": HELPFUL_BUTTON_TEXT,
                        "emoji": False,
                    },
                    "style": "primary",
                    "value": serialize_feedback_action_payload(payloads[0]),
                },
                {
                    "type": "button",
                    "action_id": NOT_HELPFUL_ACTION_ID,
                    "text": {
                        "type": "plain_text",
                        "text": NOT_HELPFUL_BUTTON_TEXT,
                        "emoji": False,
                    },
                    "style": "danger",
                    "value": serialize_feedback_action_payload(payloads[1]),
                },
            ],
        }
    )
    return blocks


def build_chat_room_redirect_url(
    session_id: uuid.UUID,
    *,
    scroll_to: int | None = None,
) -> str:
    frontend_base_url = resolve_frontend_base_url()
    url = f"{frontend_base_url}/chat/{session_id}"
    if scroll_to is None:
        return url
    return f"{url}?{urlencode({'scrollTo': scroll_to})}"


def resolve_frontend_base_url() -> str:
    return auth_settings.FRONTEND_BASE_URL.rstrip("/")


def serialize_feedback_action_payload(payload: SlackFeedbackActionPayload) -> str:
    return json.dumps(
        {
            "session_id": str(payload.session_id),
            "message_id": payload.message_id,
            "is_liked": payload.is_liked,
        },
        ensure_ascii=False,
    )


def parse_feedback_action_payload(value: Any) -> SlackFeedbackActionPayload | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        logger.warning("slack_block_action_invalid_value", value=value)
        return None
    if not isinstance(parsed, dict):
        return None

    session_id = _parse_uuid(parsed.get("session_id"))
    message_id = _parse_int(parsed.get("message_id"))
    is_liked = parsed.get("is_liked")
    if session_id is None or message_id is None or not isinstance(is_liked, bool):
        return None
    return SlackFeedbackActionPayload(
        session_id=session_id,
        message_id=message_id,
        is_liked=is_liked,
    )


def serialize_feedback_context(context: SlackFeedbackContext) -> str:
    return json.dumps(
        {
            "team_id": context.team_id,
            "channel_id": context.channel_id,
            "message_ts": context.message_ts,
            "slack_user_id": context.slack_user_id,
            "thread_ts": context.thread_ts,
        },
        ensure_ascii=False,
    )


def parse_feedback_context(value: str) -> SlackFeedbackContext | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        logger.warning("slack_feedback_modal_invalid_private_metadata", value=value)
        return None
    if not isinstance(parsed, dict):
        return None
    return _build_feedback_context_from_mapping(parsed)


def serialize_feedback_modal_context(context: SlackFeedbackModalContext) -> str:
    return json.dumps(
        {
            "action_payload": {
                "session_id": str(context.action_payload.session_id),
                "message_id": context.action_payload.message_id,
                "is_liked": context.action_payload.is_liked,
            },
            "feedback_context": {
                "team_id": context.feedback_context.team_id,
                "channel_id": context.feedback_context.channel_id,
                "message_ts": context.feedback_context.message_ts,
                "slack_user_id": context.feedback_context.slack_user_id,
                "thread_ts": context.feedback_context.thread_ts,
            },
        },
        ensure_ascii=False,
    )


def parse_feedback_modal_context(value: str) -> SlackFeedbackModalContext | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        logger.warning("slack_feedback_modal_invalid_private_metadata", value=value)
        return None
    if not isinstance(parsed, dict):
        return None

    action_payload = parse_feedback_action_payload(json.dumps(parsed.get("action_payload")))
    feedback_context = _build_feedback_context_from_mapping(
        parsed.get("feedback_context") if isinstance(parsed.get("feedback_context"), dict) else {}
    )
    if action_payload is None or feedback_context is None:
        return None
    return SlackFeedbackModalContext(
        action_payload=action_payload,
        feedback_context=feedback_context,
    )


def resolve_feedback_context(
    *,
    team_id: str,
    payload: dict[str, Any],
    fallback: SlackFeedbackContext | None = None,
) -> SlackFeedbackContext | None:
    fallback_data = fallback or SlackFeedbackContext(team_id="", channel_id="", message_ts="")
    candidate = {
        "team_id": team_id or fallback_data.team_id,
        "channel_id": _read_nested_str(payload, "container", "channel_id") or fallback_data.channel_id,
        "message_ts": (
            _read_nested_str(payload, "container", "message_ts")
            or _read_nested_str(payload, "message", "ts")
            or fallback_data.message_ts
        ),
        "thread_ts": (
            _read_nested_str(payload, "message", "thread_ts")
            or _read_nested_str(payload, "container", "thread_ts")
            or fallback_data.thread_ts
        ),
        "slack_user_id": _read_nested_str(payload, "user", "id") or fallback_data.slack_user_id,
    }
    return _build_feedback_context_from_mapping(candidate)


def _build_feedback_context_from_mapping(mapping: dict[str, Any]) -> SlackFeedbackContext | None:
    team_id = str(mapping.get("team_id") or "").strip()
    channel_id = str(mapping.get("channel_id") or "").strip()
    message_ts = str(mapping.get("message_ts") or "").strip()
    thread_ts = str(mapping.get("thread_ts") or "").strip() or None
    slack_user_id = str(mapping.get("slack_user_id") or "").strip() or None

    if not team_id or not channel_id or not message_ts:
        return None
    return SlackFeedbackContext(
        team_id=team_id,
        channel_id=channel_id,
        message_ts=message_ts,
        slack_user_id=slack_user_id,
        thread_ts=thread_ts,
    )


def _read_nested_str(payload: dict[str, Any], *keys: str) -> str:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return str(current or "").strip()


def _parse_uuid(raw_value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(raw_value))
    except (ValueError, TypeError, AttributeError):
        return None


def _parse_int(raw_value: Any) -> int | None:
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None
