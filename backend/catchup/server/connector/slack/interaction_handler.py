from __future__ import annotations

import asyncio
from typing import Any

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.chat.chat_room import process_answer_feedback
from catchup.chat.exceptions import FeedbackImmutableError
from catchup.chat.exceptions import LikedWithNegativeFeedbackError
from catchup.chat.schemas import FeedbackRequest
from catchup.configs.config import settings
from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.db.chat_room import get_chat_room
from catchup.db.chat_room import get_message
from catchup.db.engine import SessionLocal
from catchup.db.models import SourceType
from catchup.db.slack.oauth_repository import get_slack_token_by_team_id
from catchup.db.user_source_mapping import find_user_id_by_source_mapping
from catchup.observability.langfuse.feedback import upsert_feedback
from catchup.server.connector.slack.feedback_actions import COMMENT_ACTION_ID
from catchup.server.connector.slack.feedback_actions import COMMENT_BLOCK_ID
from catchup.server.connector.slack.feedback_actions import FEEDBACK_REASON_OPTIONS
from catchup.server.connector.slack.feedback_actions import HELPFUL_ACTION_ID
from catchup.server.connector.slack.feedback_actions import NOT_HELPFUL_ACTION_ID
from catchup.server.connector.slack.feedback_actions import REASON_ACTION_ID
from catchup.server.connector.slack.feedback_actions import REASON_BLOCK_ID
from catchup.server.connector.slack.feedback_actions import (
    SUPPORTED_FEEDBACK_ACTION_IDS,
)
from catchup.server.connector.slack.feedback_actions import FeedbackProcessResult
from catchup.server.connector.slack.feedback_actions import SlackFeedbackActionPayload
from catchup.server.connector.slack.feedback_actions import SlackFeedbackContext
from catchup.server.connector.slack.feedback_actions import SlackFeedbackModalContext
from catchup.server.connector.slack.feedback_actions import (
    parse_feedback_action_payload,
)
from catchup.server.connector.slack.feedback_actions import parse_feedback_modal_context
from catchup.server.connector.slack.feedback_actions import resolve_feedback_context
from catchup.server.connector.slack.feedback_actions import (
    serialize_feedback_modal_context,
)
from catchup.server.connector.slack.schemas import SlackWebhookRequest

logger = structlog.get_logger(__name__)


async def handle_block_actions(
    *,
    request: SlackWebhookRequest,
) -> dict[str, Any]:
    action = _extract_first_action(request.event)
    if not action:
        return {}

    action_id = str(action.get("action_id") or "").strip()
    if action_id not in SUPPORTED_FEEDBACK_ACTION_IDS:
        return {}

    action_payload = parse_feedback_action_payload(action.get("value"))
    if action_payload is None:
        await _post_feedback_notice(request, "피드백 정보를 읽지 못했어요.")
        return {}

    if action_id == NOT_HELPFUL_ACTION_ID:
        preflight_result = await run_in_threadpool(
            _preflight_feedback_sync,
            _read_nested_str(request.event, "user", "id"),
            action_payload,
        )
        if preflight_result is not FeedbackProcessResult.READY:
            await _post_feedback_notice(
                request,
                _feedback_notice_message(preflight_result, NOT_HELPFUL_ACTION_ID),
            )
            return {}
        handled = await _open_not_helpful_modal_if_possible(request, action_payload)
        if not handled:
            await _post_feedback_notice(request, "의견 입력 창을 열지 못했어요.")
        return {}

    feedback_result = await run_in_threadpool(
        _process_feedback_sync,
        _read_nested_str(request.event, "user", "id"),
        action_payload,
        None,
        None,
    )
    await _handle_feedback_result(request, feedback_result, HELPFUL_ACTION_ID)
    return {}


async def handle_view_submission(
    *,
    request: SlackWebhookRequest,
) -> dict[str, Any]:
    payload = request.event
    modal_context = parse_feedback_modal_context(
        _read_nested_str(payload, "view", "private_metadata")
    )
    if modal_context is None:
        return {"response_action": "clear"}

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
        modal_context.action_payload,
        reasons,
        comment,
    )
    await _handle_feedback_result(
        request,
        feedback_result,
        NOT_HELPFUL_ACTION_ID,
        fallback_context=modal_context.feedback_context,
    )
    return {"response_action": "clear"}


def _process_feedback_sync(
    slack_user_id: str,
    payload: SlackFeedbackActionPayload,
    reasons: list[str] | None,
    comment: str | None,
) -> FeedbackProcessResult:
    preflight_result = _preflight_feedback_sync(slack_user_id, payload)
    if preflight_result is not FeedbackProcessResult.READY:
        return preflight_result

    body = FeedbackRequest(
        is_liked=payload.is_liked,
        reasons=reasons,
        comment=comment,
    )
    try:
        updated_message = process_answer_feedback(
            message_id=payload.message_id,
            body=body,
        )
    except FeedbackImmutableError:
        return FeedbackProcessResult.ALREADY_SUBMITTED
    except LikedWithNegativeFeedbackError:
        return FeedbackProcessResult.INVALID

    if settings.ENABLE_LANGFUSE:
        trace_id = getattr(updated_message, "trace_id", None)
        if trace_id:
            asyncio.run(
                upsert_feedback(
                    trace_id=trace_id,
                    content=body.model_dump(exclude_none=True),
                )
            )

    return FeedbackProcessResult.SUCCESS


def _preflight_feedback_sync(
    slack_user_id: str,
    payload: SlackFeedbackActionPayload,
) -> FeedbackProcessResult:
    with SessionLocal() as db:
        user_id = find_user_id_by_source_mapping(
            db,
            source_type=SourceType.SLACK,
            external_user_identifier=slack_user_id,
        )
        if user_id is None:
            return FeedbackProcessResult.NOT_FOUND

        room = get_chat_room(
            db=db,
            session_id=payload.session_id,
            user_id=user_id,
        )
        if room is None:
            return FeedbackProcessResult.NOT_FOUND

        message = get_message(
            db=db,
            room_id=room.id,
            message_id=payload.message_id,
        )
        if message is None:
            return FeedbackProcessResult.NOT_FOUND
        if message.is_liked is not None:
            return FeedbackProcessResult.ALREADY_SUBMITTED
    return FeedbackProcessResult.READY


async def _handle_feedback_result(
    request: SlackWebhookRequest,
    feedback_result: FeedbackProcessResult,
    action_id: str,
    *,
    fallback_context: SlackFeedbackContext | None = None,
) -> None:
    if feedback_result in {
        FeedbackProcessResult.SUCCESS,
        FeedbackProcessResult.ALREADY_SUBMITTED,
    }:
        await _remove_feedback_buttons_if_possible(
            request,
            fallback_context=fallback_context,
        )

    await _post_feedback_notice(
        request,
        _feedback_notice_message(feedback_result, action_id),
        fallback_context=fallback_context,
    )


async def _open_not_helpful_modal_if_possible(
    request: SlackWebhookRequest,
    action_payload: SlackFeedbackActionPayload,
) -> bool:
    trigger_id = _read_nested_str(request.event, "trigger_id")
    if not trigger_id:
        return False

    client = await run_in_threadpool(_build_slack_client_sync, request.team_id)
    if client is None:
        return False

    feedback_context = resolve_feedback_context(
        team_id=request.team_id,
        payload=request.event,
    )
    if feedback_context is None:
        return False

    await client.open_view(
        trigger_id=trigger_id,
        view=_build_not_helpful_modal(
            SlackFeedbackModalContext(
                action_payload=action_payload,
                feedback_context=feedback_context,
            )
        ),
    )
    return True


def _build_not_helpful_modal(
    modal_context: SlackFeedbackModalContext,
) -> dict[str, Any]:
    return {
        "type": "modal",
        "callback_id": "feedback_not_helpful_modal",
        "private_metadata": serialize_feedback_modal_context(modal_context),
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
    del comment
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
    fallback_context: SlackFeedbackContext | None = None,
) -> None:
    feedback_context = resolve_feedback_context(
        team_id=request.team_id,
        payload=request.event,
        fallback=fallback_context,
    )
    if feedback_context is None:
        return

    client = await run_in_threadpool(_build_slack_client_sync, feedback_context.team_id)
    if client is None:
        return

    message_payload = request.event.get("message") if isinstance(request.event.get("message"), dict) else None
    message_text = _read_nested_str(request.event, "message", "text")
    blocks = message_payload.get("blocks") if isinstance(message_payload, dict) else None
    if not isinstance(blocks, list):
        latest_message = await client.get_message(
            feedback_context.channel_id,
            feedback_context.message_ts,
        )
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
            channel=feedback_context.channel_id,
            ts=feedback_context.message_ts,
            text=message_text or "Catch Up",
            blocks=updated_blocks,
        )
    except Exception:
        logger.warning(
            "slack_feedback_button_cleanup_failed",
            team_id=feedback_context.team_id,
            channel_id=feedback_context.channel_id,
            message_ts=feedback_context.message_ts,
            exc_info=True,
        )


async def _post_feedback_notice(
    request: SlackWebhookRequest,
    text: str,
    *,
    fallback_context: SlackFeedbackContext | None = None,
) -> None:
    feedback_context = resolve_feedback_context(
        team_id=request.team_id,
        payload=request.event,
        fallback=fallback_context,
    )
    if feedback_context is None or not feedback_context.slack_user_id:
        return

    client = await run_in_threadpool(_build_slack_client_sync, feedback_context.team_id)
    if client is None:
        return

    try:
        await client.post_ephemeral(
            channel=feedback_context.channel_id,
            user=feedback_context.slack_user_id,
            thread_ts=feedback_context.thread_ts,
            text=text,
        )
    except Exception:
        logger.warning(
            "slack_feedback_notice_failed",
            team_id=feedback_context.team_id,
            channel_id=feedback_context.channel_id,
            slack_user_id=feedback_context.slack_user_id,
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

def _read_nested_str(payload: dict[str, Any], *keys: str) -> str:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return str(current or "").strip()


def _success_message_for_action(action_id: str) -> str:
    if action_id == HELPFUL_ACTION_ID:
        return "피드백을 남겨주셔서 감사해요! 더 나은 답을 드릴 수 있도록 계속 발전할게요."
    if action_id == NOT_HELPFUL_ACTION_ID:
        return "소중한 의견 감사해요. 반영해서 꼭 개선할게요."
    return "피드백을 저장했어요."


def _feedback_notice_message(feedback_result: FeedbackProcessResult, action_id: str) -> str:
    if feedback_result is FeedbackProcessResult.SUCCESS:
        return _success_message_for_action(action_id)
    if feedback_result is FeedbackProcessResult.ALREADY_SUBMITTED:
        return "이미 피드백이 제출된 답변이에요."
    if feedback_result is FeedbackProcessResult.INVALID:
        return "피드백을 저장하지 못했어요."
    return "접근 권한이 없거나 답변을 찾지 못했어요."
