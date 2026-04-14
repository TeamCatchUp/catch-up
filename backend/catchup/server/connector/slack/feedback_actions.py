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

FEEDBACK_MODAL_CALLBACK_ID = "feedback_not_helpful_modal"
REASON_BLOCK_ID = "feedback_reason_block"
REASON_ACTION_ID = "feedback_reason_action"
DELETE_POLICY_BLOCK_ID = "feedback_delete_policy_block"
DELETE_POLICY_ACTION_ID = "feedback_delete_policy_action"
WARNING_BANNER_BLOCK_ID = "catchup_feedback_warning_banner_v1"

FEEDBACK_REASON_OPTIONS = [
    ("사실과 다른 내용이 포함되어 있어요", "HALLUCINATION"),
    ("정보가 오래되었어요", "OUTDATED"),
    ("질문과 관련 없는 답변이에요", "IRRELEVANT_ANSWER"),
    ("중요한 내용이 빠져 있어요", "MISSING_INFO"),
]
DELETE_POLICY_OPTIONS = [
    ("답변을 유지하고, 부정확 표시만 추가할게요", "keep_with_warning"),
    ("답변을 삭제할게요", "delete_answer"),
]
DELETE_POLICY_REQUIRED_REASONS = frozenset({"HALLUCINATION", "OUTDATED"})

DETAIL_BUTTON_TEXT = "Catch Up에서 자세히 보기"
HELPFUL_BUTTON_TEXT = "👍도움됐어요"
NOT_HELPFUL_BUTTON_TEXT = "👎 아쉬워요"
DETAIL_PROMPT_TEXT = "답변이 도움이 됐나요?"
SIGNUP_BUTTON_TEXT = "CatchUp 회원가입"
WARNING_BANNER_TEXT = "⚠️ *이 답변은 정확하지 않을 수 있어요*"


class FeedbackProcessResult(StrEnum):
    READY = "ready"
    SUCCESS = "success"
    INVALID = "invalid"
    NOT_REGISTERED = "not_registered"
    ANSWER_NOT_FOUND = "answer_not_found"
    ALREADY_SUBMITTED = "already_submitted"


class SlackFeedbackDeletePolicy(StrEnum):
    KEEP_WITH_WARNING = "keep_with_warning"
    DELETE_ANSWER = "delete_answer"


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
    message_text: str | None = None
    message_blocks: list[dict[str, Any]] | None = None


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
            # TODO: Slack Bot v0
            # "accessory": {
            #     "type": "button",
            #     "action_id": VIEW_DETAIL_ACTION_ID,
            #     "text": {
            #         "type": "plain_text",
            #         "text": DETAIL_BUTTON_TEXT,
            #         "emoji": False,
            #     },
            #     "url": build_chat_room_redirect_url(
            #         answer_ref.session_id,
            #         scroll_to=answer_ref.assistant_message_id,
            #     ),
            # },
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


def build_signup_prompt_blocks(text: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "section",
            "block_id": "catchup_app_mention_signup_message_v1",
            "text": {
                "type": "mrkdwn",
                "text": text,
            },
        },
        {
            "type": "actions",
            "block_id": "catchup_app_mention_signup_actions_v1",
            "elements": [
                {
                    "type": "button",
                    "action_id": "catchup_signup_redirect_v1",
                    "text": {
                        "type": "plain_text",
                        "text": SIGNUP_BUTTON_TEXT,
                        "emoji": False,
                    },
                    "url": resolve_frontend_base_url(),
                }
            ],
        },
    ]


def build_feedback_reason_options(*, selected_reason: str | None = None) -> list[dict[str, Any]]:
    del selected_reason
    return _build_radio_options(FEEDBACK_REASON_OPTIONS)


def build_delete_policy_options(
    *,
    selected_policy: str | None = None,
) -> list[dict[str, Any]]:
    del selected_policy
    return _build_radio_options(DELETE_POLICY_OPTIONS)


def feedback_reason_requires_delete_policy(reason: str | None) -> bool:
    return str(reason or "").strip() in DELETE_POLICY_REQUIRED_REASONS


def build_warning_banner_block() -> dict[str, Any]:
    return {
        "type": "section",
        "block_id": WARNING_BANNER_BLOCK_ID,
        "text": {
            "type": "mrkdwn",
            "text": WARNING_BANNER_TEXT,
        },
    }


def build_feedback_notice_text(
    feedback_result: FeedbackProcessResult,
    *,
    action_id: str,
    reason: str | None = None,
    delete_policy: str | None = None,
) -> str:
    if feedback_result is FeedbackProcessResult.SUCCESS:
        return _build_success_notice_text(
            action_id=action_id,
            reason=reason,
            delete_policy=delete_policy,
        )
    if feedback_result is FeedbackProcessResult.ALREADY_SUBMITTED:
        return "이미 이 답변에 피드백을 남겼어요."
    if feedback_result is FeedbackProcessResult.INVALID:
        return "피드백을 저장하지 못했어요."
    if feedback_result is FeedbackProcessResult.NOT_REGISTERED:
        return "CatchUp에 등록된 사용자만 피드백을 남길 수 있어요."
    return "원본 답변을 찾을 수 없어요."


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
            "message_text": context.message_text,
            "message_blocks": context.message_blocks,
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
                "message_text": context.feedback_context.message_text,
                "message_blocks": context.feedback_context.message_blocks,
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
    message_payload = payload.get("message") if isinstance(payload.get("message"), dict) else {}
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
        "message_text": str(message_payload.get("text") or fallback_data.message_text or "").strip() or None,
        "message_blocks": (
            message_payload.get("blocks")
            if isinstance(message_payload.get("blocks"), list)
            else fallback_data.message_blocks
        ),
    }
    return _build_feedback_context_from_mapping(candidate)


def _build_feedback_context_from_mapping(mapping: dict[str, Any]) -> SlackFeedbackContext | None:
    team_id = str(mapping.get("team_id") or "").strip()
    channel_id = str(mapping.get("channel_id") or "").strip()
    message_ts = str(mapping.get("message_ts") or "").strip()
    thread_ts = str(mapping.get("thread_ts") or "").strip() or None
    slack_user_id = str(mapping.get("slack_user_id") or "").strip() or None
    message_text = str(mapping.get("message_text") or "").strip() or None
    message_blocks = mapping.get("message_blocks") if isinstance(mapping.get("message_blocks"), list) else None

    if not team_id or not channel_id or not message_ts:
        return None
    return SlackFeedbackContext(
        team_id=team_id,
        channel_id=channel_id,
        message_ts=message_ts,
        slack_user_id=slack_user_id,
        thread_ts=thread_ts,
        message_text=message_text,
        message_blocks=message_blocks,
    )


def _read_nested_str(payload: dict[str, Any], *keys: str) -> str:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return str(current or "").strip()


def _build_success_notice_text(
    *,
    action_id: str,
    reason: str | None,
    delete_policy: str | None,
) -> str:
    if action_id == HELPFUL_ACTION_ID:
        return "피드백을 남겨주셔서 감사해요! 더 나은 답을 드릴 수 있도록 계속 발전할게요."
    if not feedback_reason_requires_delete_policy(reason):
        return "🙏 알려주셔서 감사해요. 팀에게 더 정확한 정보를 전달할 수 있게 됐어요."
    if delete_policy == SlackFeedbackDeletePolicy.DELETE_ANSWER.value:
        return "🙏 알려주셔서 감사해요. 답변을 삭제했어요."
    return "🙏 알려주셔서 감사해요. 팀에게 이 답변이 정확하지 않을 수 있다는 점을 표시했어요."


def _build_radio_options(
    options: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    return [
        {
            "text": {
                "type": "plain_text",
                "text": label,
            },
            "value": value,
        }
        for label, value in options
    ]


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
