from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.chat.chat_room import process_answer_feedback
from catchup.chat.exceptions import FeedbackImmutableError
from catchup.chat.exceptions import LikedWithNegativeFeedbackError
from catchup.chat.schemas import FeedbackRequest
from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.db.chat_room import get_chat_room
from catchup.db.chat_room import get_message
from catchup.db.engine import SessionLocal
from catchup.db.models import SourceType
from catchup.db.slack.oauth_repository import get_slack_token_by_team_id
from catchup.db.user_source_mapping import find_user_id_by_source_mapping
from catchup.observability.langfuse.feedback import upsert_feedback
from catchup.configs.config import settings
from catchup.server.connector.slack.schemas import SlackWebhookRequest

logger = structlog.get_logger(__name__)

HELPFUL_ACTION_ID = "feedback_helpful"
NOT_HELPFUL_ACTION_ID = "feedback_not_helpful"
REASON_BLOCK_ID = "feedback_reason_block"
REASON_ACTION_ID = "feedback_reason_action"
COMMENT_BLOCK_ID = "feedback_comment_block"
COMMENT_ACTION_ID = "feedback_comment_action"
SUPPORTED_FEEDBACK_ACTION_IDS = frozenset({HELPFUL_ACTION_ID, NOT_HELPFUL_ACTION_ID})
FEEDBACK_REASON_OPTIONS = [
    ("원하는 답이 아니에요", "IRRELEVANT_ANSWER"),
    ("출처가 정확하지 않아요", "NO_CITATION"),
    ("내용이 부족해요", "MISSING_INFO"),
    ("관련 없는 결과가 포함됐어요", "IRRELEVANT_SOURCE"),
]


async def handle_block_actions(
    *,
    request: SlackWebhookRequest,
) -> dict[str, Any]:
    action = _extract_first_action(request.event)
    if not action:
        return _ack_response()

    action_id = str(action.get("action_id") or "").strip()
    if action_id not in SUPPORTED_FEEDBACK_ACTION_IDS:
        return _ack_response()

    action_value = _parse_action_value(action.get("value"))
    if action_value is None:
        await _post_feedback_notice(request, "피드백 정보를 읽지 못했어요.")
        return _ack_response()

    if action_id == NOT_HELPFUL_ACTION_ID:
        preflight_result = await run_in_threadpool(
            _preflight_feedback_sync,
            _read_nested_str(request.event, "user", "id"),
            action_value,
        )
        if preflight_result != "ready":
            await _post_feedback_notice(
                request,
                _feedback_notice_message(preflight_result, NOT_HELPFUL_ACTION_ID),
            )
            return _ack_response()
        handled = await _open_not_helpful_modal_if_possible(request, action_value)
        if not handled:
            await _post_feedback_notice(request, "의견 입력 창을 열지 못했어요.")
        return _ack_response()

    feedback_result = await run_in_threadpool(
        _process_feedback_sync,
        _read_nested_str(request.event, "user", "id"),
        action_value,
        None,
        None,
    )
    await _handle_feedback_result(request, feedback_result, HELPFUL_ACTION_ID)
    return _ack_response()


async def handle_view_submission(
    *,
    request: SlackWebhookRequest,
) -> dict[str, Any]:
    payload = request.event
    private_metadata = _parse_private_metadata(
        _read_nested_str(payload, "view", "private_metadata")
    )
    if private_metadata is None:
        return _clear_modal_response()

    reasons, comment = _parse_view_submission_feedback(payload)
    validation_errors = _validate_feedback_submission(reasons, comment)
    if validation_errors:
        return {
            "response_action": "errors",
            "errors": validation_errors,
        }

    feedback_result = await run_in_threadpool(
        _process_feedback_sync,
        _read_nested_str(payload, "user", "id"),
        private_metadata,
        reasons,
        comment,
    )
    await _handle_feedback_result(
        request,
        feedback_result,
        NOT_HELPFUL_ACTION_ID,
        fallback_metadata=private_metadata,
    )
    return _clear_modal_response()


def _process_feedback_sync(
    slack_user_id: str,
    payload: dict[str, Any],
    reasons: list[str] | None,
    comment: str | None,
) -> str:
    preflight_result = _preflight_feedback_sync(slack_user_id, payload)
    if preflight_result != "ready":
        return preflight_result

    message_id = _parse_message_id(payload.get("message_id"))
    is_liked = payload.get("is_liked")
    if message_id is None or not isinstance(is_liked, bool):
        return "invalid"

    body = FeedbackRequest(
        is_liked=is_liked,
        reasons=reasons,
        comment=comment,
    )
    try:
        updated_message = process_answer_feedback(
            message_id=message_id,
            body=body,
        )
    except FeedbackImmutableError:
        return "already_submitted"
    except LikedWithNegativeFeedbackError:
        return "invalid"

    if settings.ENABLE_LANGFUSE:
        trace_id = getattr(updated_message, "trace_id", None)
        if trace_id:
            asyncio.run(
                upsert_feedback(
                    trace_id=trace_id,
                    content=body.model_dump(exclude_none=True),
                )
            )

    return "success"


def _preflight_feedback_sync(
    slack_user_id: str,
    payload: dict[str, Any],
) -> str:
    session_id = _parse_session_id(payload.get("session_id"))
    message_id = _parse_message_id(payload.get("message_id"))
    is_liked = payload.get("is_liked")
    if session_id is None or message_id is None or not isinstance(is_liked, bool):
        return "invalid"

    with SessionLocal() as db:
        user_id = find_user_id_by_source_mapping(
            db,
            source_type=SourceType.SLACK,
            external_user_identifier=slack_user_id,
        )
        if user_id is None:
            return "not_found"

        room = get_chat_room(
            db=db,
            session_id=session_id,
            user_id=user_id,
        )
        if room is None:
            return "not_found"

        message = get_message(
            db=db,
            room_id=room.id,
            message_id=message_id,
        )
        if message is None:
            return "not_found"
        if message.is_liked is not None:
            return "already_submitted"
    return "ready"


async def _handle_feedback_result(
    request: SlackWebhookRequest,
    feedback_result: str,
    action_id: str,
    *,
    fallback_metadata: dict[str, Any] | None = None,
) -> None:
    if feedback_result in {"success", "already_submitted"}:
        await _remove_feedback_buttons_if_possible(request, fallback_metadata=fallback_metadata)

    await _post_feedback_notice(
        request,
        _feedback_notice_message(feedback_result, action_id),
        fallback_metadata=fallback_metadata,
    )


async def _open_not_helpful_modal_if_possible(
    request: SlackWebhookRequest,
    action_value: dict[str, Any],
) -> bool:
    trigger_id = _read_nested_str(request.event, "trigger_id")
    if not trigger_id:
        return False

    client = await run_in_threadpool(_build_slack_client_sync, request.team_id)
    if client is None:
        return False

    metadata = {
        "session_id": action_value.get("session_id"),
        "message_id": action_value.get("message_id"),
        "is_liked": False,
        "team_id": request.team_id,
        "channel_id": _read_nested_str(request.event, "container", "channel_id"),
        "message_ts": _read_nested_str(request.event, "container", "message_ts") or _read_nested_str(request.event, "message", "ts"),
        "thread_ts": _read_nested_str(request.event, "message", "thread_ts") or _read_nested_str(request.event, "container", "thread_ts"),
    }
    await client.open_view(
        trigger_id=trigger_id,
        view=_build_not_helpful_modal(metadata),
    )
    return True


def _build_not_helpful_modal(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "modal",
        "callback_id": "feedback_not_helpful_modal",
        "private_metadata": json.dumps(metadata, ensure_ascii=False),
        "title": {
            "type": "plain_text",
            "text": "아쉬워요",
        },
        "submit": {
            "type": "plain_text",
            "text": "보내기",
        },
        "close": {
            "type": "plain_text",
            "text": "취소",
        },
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "아쉬웠던 부분을 알려주시면, 더 나은 답을 드릴 수 있도록 개선할게요.",
                },
            },
            {
                "type": "input",
                "block_id": REASON_BLOCK_ID,
                "label": {
                    "type": "plain_text",
                    "text": "사유 선택 (단일 선택)",
                },
                "element": {
                    "type": "radio_buttons",
                    "action_id": REASON_ACTION_ID,
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": label,
                            },
                            "value": value,
                        }
                        for label, value in FEEDBACK_REASON_OPTIONS
                    ],
                },
            },
            {
                "type": "input",
                "block_id": COMMENT_BLOCK_ID,
                "optional": True,
                "label": {
                    "type": "plain_text",
                    "text": "추가 의견 입력",
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": COMMENT_ACTION_ID,
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "구체적으로 작성해 주시면 개선에 큰 도움이 돼요",
                    },
                },
            },
        ],
    }


def _parse_view_submission_feedback(payload: dict[str, Any]) -> tuple[list[str], str | None]:
    values = payload.get("view", {}).get("state", {}).get("values", {})
    reason_state = values.get(REASON_BLOCK_ID, {}).get(REASON_ACTION_ID, {})
    selected_option = reason_state.get("selected_option")
    reasons = []
    if isinstance(selected_option, dict):
        selected_reason = str(selected_option.get("value") or "").strip()
        if selected_reason:
            reasons.append(selected_reason)

    comment_value = values.get(COMMENT_BLOCK_ID, {}).get(COMMENT_ACTION_ID, {}).get("value")
    comment = str(comment_value or "").strip() or None
    return reasons, comment


def _validate_feedback_submission(reasons: list[str], comment: str | None) -> dict[str, str] | None:
    errors: dict[str, str] = {}
    if not reasons:
        errors[REASON_BLOCK_ID] = "아쉬웠던 이유를 하나 선택해 주세요."
    return errors or None


def _extract_first_action(payload: dict[str, Any]) -> dict[str, Any] | None:
    actions = payload.get("actions")
    if not isinstance(actions, list) or not actions:
        return None
    action = actions[0]
    return action if isinstance(action, dict) else None


async def _remove_feedback_buttons_if_possible(
    request: SlackWebhookRequest,
    *,
    fallback_metadata: dict[str, Any] | None = None,
) -> None:
    metadata = fallback_metadata or {}
    team_id = request.team_id or str(metadata.get("team_id") or "")
    channel_id = _read_nested_str(request.event, "container", "channel_id") or str(
        metadata.get("channel_id") or ""
    )
    message_ts = (
        _read_nested_str(request.event, "container", "message_ts")
        or _read_nested_str(request.event, "message", "ts")
        or str(metadata.get("message_ts") or "")
    )

    if not team_id or not channel_id or not message_ts:
        return

    client = await run_in_threadpool(_build_slack_client_sync, team_id)
    if client is None:
        return

    message_payload = request.event.get("message") if isinstance(request.event.get("message"), dict) else None
    message_text = _read_nested_str(request.event, "message", "text")
    blocks = message_payload.get("blocks") if isinstance(message_payload, dict) else None
    if not isinstance(blocks, list):
        latest_message = await client.get_message(channel_id, message_ts)
        if latest_message is None:
            return
        message_text = str(latest_message.get("text") or message_text or "Catch Up")
        blocks = latest_message.get("blocks")

    if not isinstance(blocks, list):
        return

    updated_blocks = _strip_feedback_action_blocks(blocks)
    if updated_blocks == blocks:
        return

    try:
        await client.update_message(
            channel=channel_id,
            ts=message_ts,
            text=message_text or "Catch Up",
            blocks=updated_blocks,
        )
    except Exception:
        logger.warning(
            "slack_feedback_button_cleanup_failed",
            team_id=team_id,
            channel_id=channel_id,
            message_ts=message_ts,
            exc_info=True,
        )


async def _post_feedback_notice(
    request: SlackWebhookRequest,
    text: str,
    *,
    fallback_metadata: dict[str, Any] | None = None,
) -> None:
    metadata = fallback_metadata or {}
    team_id = request.team_id or str(metadata.get("team_id") or "")
    channel_id = _read_nested_str(request.event, "container", "channel_id") or str(
        metadata.get("channel_id") or ""
    )
    thread_ts = _read_nested_str(request.event, "message", "thread_ts") or str(
        metadata.get("thread_ts") or ""
    )
    slack_user_id = _read_nested_str(request.event, "user", "id")

    if not team_id or not channel_id or not slack_user_id:
        return

    client = await run_in_threadpool(_build_slack_client_sync, team_id)
    if client is None:
        return

    try:
        await client.post_ephemeral(
            channel=channel_id,
            user=slack_user_id,
            thread_ts=thread_ts or None,
            text=text,
        )
    except Exception:
        logger.warning(
            "slack_feedback_notice_failed",
            team_id=team_id,
            channel_id=channel_id,
            slack_user_id=slack_user_id,
            exc_info=True,
        )


def _build_slack_client_sync(team_id: str) -> SlackApiClientWrapper | None:
    with SessionLocal() as db:
        token = get_slack_token_by_team_id(db, team_id)
        if token is None:
            return None
        return SlackApiClientWrapper(token.bot_access_token, team_id)


def _strip_feedback_action_blocks(blocks: list[Any]) -> list[dict[str, Any]]:
    filtered_blocks: list[dict[str, Any]] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "actions":
            filtered_blocks.append(block)
            continue

        elements = block.get("elements")
        if not isinstance(elements, list):
            filtered_blocks.append(block)
            continue

        filtered_elements = [
            element
            for element in elements
            if not (
                isinstance(element, dict)
                and str(element.get("action_id") or "").strip() in SUPPORTED_FEEDBACK_ACTION_IDS
            )
        ]
        if not filtered_elements:
            continue

        next_block = dict(block)
        next_block["elements"] = filtered_elements
        filtered_blocks.append(next_block)
    return filtered_blocks


def _parse_action_value(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        logger.warning("slack_block_action_invalid_value", value=value)
        return None
    return parsed if isinstance(parsed, dict) else None


def _parse_private_metadata(value: str) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        logger.warning("slack_feedback_modal_invalid_private_metadata", value=value)
        return None
    return parsed if isinstance(parsed, dict) else None


def _read_nested_str(payload: dict[str, Any], *keys: str) -> str:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return str(current or "").strip()


def _parse_session_id(raw_value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(raw_value))
    except (ValueError, TypeError, AttributeError):
        return None


def _parse_message_id(raw_value: Any) -> int | None:
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _ack_response() -> dict[str, Any]:
    return {}


def _clear_modal_response() -> dict[str, str]:
    return {"response_action": "clear"}


def _success_message_for_action(action_id: str) -> str:
    if action_id == HELPFUL_ACTION_ID:
        return "피드백을 남겨주셔서 감사해요! 더 나은 답을 드릴 수 있도록 계속 발전할게요."
    if action_id == NOT_HELPFUL_ACTION_ID:
        return "소중한 의견 감사해요. 반영해서 꼭 개선할게요."
    return "피드백을 저장했어요."


def _feedback_notice_message(feedback_result: str, action_id: str) -> str:
    if feedback_result == "success":
        return _success_message_for_action(action_id)
    if feedback_result == "already_submitted":
        return "이미 피드백이 제출된 답변이에요."
    if feedback_result == "invalid":
        return "피드백을 저장하지 못했어요."
    return "접근 권한이 없거나 답변을 찾지 못했어요."
