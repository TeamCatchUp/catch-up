from __future__ import annotations

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
SUPPORTED_FEEDBACK_ACTION_IDS = frozenset({HELPFUL_ACTION_ID, NOT_HELPFUL_ACTION_ID})


async def handle_block_actions(
    *,
    request: SlackWebhookRequest,
) -> dict[str, Any]:
    action = _extract_first_action(request.event)
    if not action:
        return _ephemeral_response("처리할 액션을 찾지 못했어요.")

    action_id = str(action.get("action_id") or "").strip()
    if action_id not in SUPPORTED_FEEDBACK_ACTION_IDS:
        return _ephemeral_response("지원하지 않는 액션이에요.")

    action_value = _parse_action_value(action.get("value"))
    if action_value is None:
        return _ephemeral_response("피드백 정보를 읽지 못했어요.")

    slack_user_id = _read_nested_str(request.event, "user", "id")
    if not slack_user_id:
        return _ephemeral_response("사용자 정보를 확인하지 못했어요.")

    feedback_result = await run_in_threadpool(
        _process_feedback_action_sync,
        slack_user_id,
        action_value,
    )
    if feedback_result in {"success", "already_submitted"}:
        await _remove_feedback_buttons_if_possible(request)
    if feedback_result == "success":
        return _ephemeral_response("피드백을 저장했어요.")
    if feedback_result == "already_submitted":
        return _ephemeral_response("이미 피드백이 제출된 답변이에요.")
    if feedback_result == "invalid":
        return _ephemeral_response("피드백을 저장하지 못했어요.")
    return _ephemeral_response("접근 권한이 없거나 답변을 찾지 못했어요.")


def _process_feedback_action_sync(
    slack_user_id: str,
    action_value: dict[str, Any],
) -> str:
    session_id = _parse_session_id(action_value.get("session_id"))
    message_id = _parse_message_id(action_value.get("message_id"))
    is_liked = action_value.get("is_liked")
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

    body = FeedbackRequest(
        is_liked=is_liked,
        reasons=None,
        comment=None,
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
            import asyncio
            asyncio.run(
                upsert_feedback(
                    trace_id=trace_id,
                    content=body.model_dump(exclude_none=True),
                )
            )

    return "success"


def _extract_first_action(payload: dict[str, Any]) -> dict[str, Any] | None:
    actions = payload.get("actions")
    if not isinstance(actions, list) or not actions:
        return None
    action = actions[0]
    return action if isinstance(action, dict) else None


async def _remove_feedback_buttons_if_possible(request: SlackWebhookRequest) -> None:
    team_id = request.team_id
    channel_id = _read_nested_str(request.event, "container", "channel_id")
    message_ts = _read_nested_str(request.event, "container", "message_ts") or _read_nested_str(request.event, "message", "ts")
    message_text = _read_nested_str(request.event, "message", "text") or "Catch Up"
    blocks = request.event.get("message", {}).get("blocks") if isinstance(request.event.get("message"), dict) else None

    if not team_id or not channel_id or not message_ts or not isinstance(blocks, list):
        return

    updated_blocks = _strip_feedback_action_blocks(blocks)
    if updated_blocks == blocks:
        return

    client = await run_in_threadpool(_build_slack_client_sync, team_id)
    if client is None:
        return

    try:
        await client.update_message(
            channel=channel_id,
            ts=message_ts,
            text=message_text,
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


def _ephemeral_response(text: str) -> dict[str, str]:
    return {
        "response_type": "ephemeral",
        "text": text,
    }
