from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.chat.exceptions import LikedWithNegativeFeedbackError
from catchup.chat.integrations.slack_app_mention import UNMAPPED_USER_MESSAGE
from catchup.chat.schemas import FeedbackRequest
from catchup.configs.config import settings
from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.db.chat_room import get_chat_room_by_session_id
from catchup.db.chat_room import get_message
from catchup.db.engine import SessionLocal
from catchup.db.models import SourceType
from catchup.db.slack.oauth_repository import get_slack_token_by_team_id
from catchup.db.user_source_mapping import find_user_id_by_source_mapping
from catchup.observability.langfuse.feedback import upsert_feedback
from catchup.server.connector.slack.feedback_actions import DELETE_POLICY_ACTION_ID
from catchup.server.connector.slack.feedback_actions import DELETE_POLICY_BLOCK_ID
from catchup.server.connector.slack.feedback_actions import FEEDBACK_MODAL_CALLBACK_ID
from catchup.server.connector.slack.feedback_actions import HELPFUL_ACTION_ID
from catchup.server.connector.slack.feedback_actions import NOT_HELPFUL_ACTION_ID
from catchup.server.connector.slack.feedback_actions import REASON_ACTION_ID
from catchup.server.connector.slack.feedback_actions import REASON_BLOCK_ID
from catchup.server.connector.slack.feedback_actions import (
    SUPPORTED_FEEDBACK_ACTION_IDS,
)
from catchup.server.connector.slack.feedback_actions import WARNING_BANNER_BLOCK_ID
from catchup.server.connector.slack.feedback_actions import FeedbackProcessResult
from catchup.server.connector.slack.feedback_actions import SlackFeedbackActionPayload
from catchup.server.connector.slack.feedback_actions import SlackFeedbackContext
from catchup.server.connector.slack.feedback_actions import SlackFeedbackDeletePolicy
from catchup.server.connector.slack.feedback_actions import SlackFeedbackModalContext
from catchup.server.connector.slack.feedback_actions import build_delete_policy_options
from catchup.server.connector.slack.feedback_actions import build_feedback_notice_text
from catchup.server.connector.slack.feedback_actions import (
    build_feedback_reason_options,
)
from catchup.server.connector.slack.feedback_actions import build_signup_prompt_blocks
from catchup.server.connector.slack.feedback_actions import build_warning_banner_block
from catchup.server.connector.slack.feedback_actions import (
    feedback_reason_requires_delete_policy,
)
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

SLACK_MESSAGE_BLOCK_LIMIT = 50


@dataclass(slots=True)
class SlackFeedbackSubmissionTarget:
    catchup_user_id: int
    message: Any


@dataclass(slots=True, frozen=True)
class SlackNotHelpfulSubmission:
    reason: str
    delete_policy: str | None = None


async def handle_block_actions(
    *,
    request: SlackWebhookRequest,
) -> dict[str, Any]:
    action = _extract_first_action(request.event)
    if not action:
        return {}

    action_id = str(action.get("action_id") or "").strip()
    if action_id == REASON_ACTION_ID and _is_not_helpful_modal_interaction(request.event):
        await _refresh_not_helpful_modal(request)
        return {}

    if action_id not in SUPPORTED_FEEDBACK_ACTION_IDS:
        return {}

    action_payload = parse_feedback_action_payload(action.get("value"))
    if action_payload is None:
        await _post_feedback_notice(
            request,
            "피드백 정보를 읽지 못했어요.",
        )
        return {}

    if action_id == NOT_HELPFUL_ACTION_ID:
        preflight_result = await run_in_threadpool(
            _preflight_feedback_sync,
            _read_nested_str(request.event, "user", "id"),
            action_payload,
        )
        if preflight_result is not FeedbackProcessResult.READY:
            await _handle_feedback_result(
                request,
                preflight_result,
                NOT_HELPFUL_ACTION_ID,
            )
            return {}
        handled = await _open_not_helpful_modal_if_possible(request, action_payload)
        if not handled:
            await _post_feedback_notice(
                request,
                "의견 입력 창을 열지 못했어요.",
            )
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

    submission = _parse_not_helpful_submission(payload)
    validation_errors = _validate_feedback_submission(submission)
    if validation_errors:
        return {
            "response_action": "errors",
            "errors": validation_errors,
        }

    feedback_result = await run_in_threadpool(
        _process_feedback_sync,
        _read_nested_str(payload, "user", "id"),
        modal_context.action_payload,
        [submission.reason],
        None,
    )
    await _handle_feedback_result(
        request,
        feedback_result,
        NOT_HELPFUL_ACTION_ID,
        fallback_context=modal_context.feedback_context,
        submission=submission,
    )
    return {"response_action": "clear"}


def _process_feedback_sync(
    slack_user_id: str,
    payload: SlackFeedbackActionPayload,
    reasons: list[str] | None,
    comment: str | None,
) -> FeedbackProcessResult:
    body = FeedbackRequest(
        is_liked=payload.is_liked,
        reasons=reasons,
        comment=comment,
    )
    with SessionLocal() as db:
        submission_target = _resolve_feedback_submission_target(
            db=db,
            slack_user_id=slack_user_id,
            payload=payload,
        )
        if isinstance(submission_target, FeedbackProcessResult):
            return submission_target
        try:
            updated_message = _save_feedback_submission(
                db=db,
                submission_target=submission_target,
                body=body,
            )
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
        result = _resolve_feedback_submission_target(
            db=db,
            slack_user_id=slack_user_id,
            payload=payload,
        )
        if isinstance(result, FeedbackProcessResult):
            return result
    return FeedbackProcessResult.READY


async def _handle_feedback_result(
    request: SlackWebhookRequest,
    feedback_result: FeedbackProcessResult,
    action_id: str,
    *,
    fallback_context: SlackFeedbackContext | None = None,
    submission: SlackNotHelpfulSubmission | None = None,
) -> None:
    if feedback_result is FeedbackProcessResult.NOT_REGISTERED:
        await _post_feedback_signup_prompt(
            request,
            fallback_context=fallback_context,
        )
        return

    if feedback_result is FeedbackProcessResult.SUCCESS:
        feedback_result = await _apply_feedback_message_effect(
            request,
            action_id=action_id,
            fallback_context=fallback_context,
            submission=submission,
        )

    await _post_feedback_notice(
        request,
        build_feedback_notice_text(
            feedback_result,
            action_id=action_id,
            reason=submission.reason if submission is not None else None,
            delete_policy=submission.delete_policy if submission is not None else None,
        ),
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
            ),
            selected_reason=None,
            selected_delete_policy=None,
        ),
    )
    return True


def _build_not_helpful_modal(
    modal_context: SlackFeedbackModalContext,
    *,
    selected_reason: str | None,
    selected_delete_policy: str | None,
) -> dict[str, Any]:
    reason_options = build_feedback_reason_options(selected_reason=selected_reason)
    delete_policy_options = build_delete_policy_options(selected_policy=selected_delete_policy)
    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "사유를 알려주시면 팀에게 더 나은 답변을 전달할 수 있어요.",
            },
        },
        {"type": "divider"},
        {
            "type": "input",
            "block_id": REASON_BLOCK_ID,
            "dispatch_action": True,
            "label": {
                "type": "plain_text",
                "text": "어떤 부분이 아쉬웠나요?",
            },
            "element": {
                "type": "radio_buttons",
                "action_id": REASON_ACTION_ID,
                "options": reason_options,
                **_build_initial_option_field(reason_options, selected_reason),
            },
        },
    ]
    if feedback_reason_requires_delete_policy(selected_reason):
        blocks.extend(
            [
                {"type": "divider"},
                {
                    "type": "input",
                    "block_id": DELETE_POLICY_BLOCK_ID,
                    "label": {
                        "type": "plain_text",
                        "text": "이 답변을 삭제할까요?",
                    },
                    "element": {
                        "type": "radio_buttons",
                        "action_id": DELETE_POLICY_ACTION_ID,
                        "options": delete_policy_options,
                        **_build_initial_option_field(
                            delete_policy_options,
                            selected_delete_policy,
                        ),
                    },
                },
            ]
        )
    return {
        "type": "modal",
        "callback_id": FEEDBACK_MODAL_CALLBACK_ID,
        "private_metadata": serialize_feedback_modal_context(modal_context),
        "title": {
            "type": "plain_text",
            "text": "의견 보내기",
        },
        "submit": {
            "type": "plain_text",
            "text": "보내기",
        },
        "close": {
            "type": "plain_text",
            "text": "취소",
        },
        "blocks": blocks,
    }


async def _refresh_not_helpful_modal(request: SlackWebhookRequest) -> None:
    modal_context = parse_feedback_modal_context(
        _read_nested_str(request.event, "view", "private_metadata")
    )
    if modal_context is None:
        return

    view_id = _read_nested_str(request.event, "view", "id")
    view_hash = _read_nested_str(request.event, "view", "hash")
    if not view_id or not view_hash:
        return

    client = await run_in_threadpool(_build_slack_client_sync, request.team_id)
    if client is None:
        return

    selected_reason, selected_delete_policy = _parse_modal_state(request.event)
    await client.update_view(
        view_id=view_id,
        hash=view_hash,
        view=_build_not_helpful_modal(
            modal_context,
            selected_reason=selected_reason,
            selected_delete_policy=selected_delete_policy,
        ),
    )


def _parse_not_helpful_submission(payload: dict[str, Any]) -> SlackNotHelpfulSubmission:
    selected_reason, selected_delete_policy = _parse_modal_state(payload)
    return SlackNotHelpfulSubmission(
        reason=selected_reason,
        delete_policy=selected_delete_policy,
    )


def _parse_modal_state(payload: dict[str, Any]) -> tuple[str, str | None]:
    values = payload.get("view", {}).get("state", {}).get("values", {})
    reason_state = values.get(REASON_BLOCK_ID, {}).get(REASON_ACTION_ID, {})
    selected_reason = _read_selected_option_value(reason_state)
    delete_policy_state = values.get(DELETE_POLICY_BLOCK_ID, {}).get(DELETE_POLICY_ACTION_ID, {})
    selected_delete_policy = _read_selected_option_value(delete_policy_state) or None
    return selected_reason, selected_delete_policy


def _validate_feedback_submission(
    submission: SlackNotHelpfulSubmission,
) -> dict[str, str] | None:
    errors: dict[str, str] = {}
    if not submission.reason:
        errors[REASON_BLOCK_ID] = "아쉬웠던 이유를 하나 선택해 주세요."
    if feedback_reason_requires_delete_policy(submission.reason) and not submission.delete_policy:
        errors[DELETE_POLICY_BLOCK_ID] = "답변 처리 방식을 하나 선택해 주세요."
    return errors or None


def _extract_first_action(payload: dict[str, Any]) -> dict[str, Any] | None:
    actions = payload.get("actions")
    if not isinstance(actions, list) or not actions:
        return None
    action = actions[0]
    return action if isinstance(action, dict) else None


async def _post_feedback_signup_prompt(
    request: SlackWebhookRequest,
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
            text=UNMAPPED_USER_MESSAGE,
            blocks=build_signup_prompt_blocks(UNMAPPED_USER_MESSAGE),
        )
    except Exception:
        logger.warning(
            "slack_feedback_signup_prompt_failed",
            team_id=feedback_context.team_id,
            channel_id=feedback_context.channel_id,
            slack_user_id=feedback_context.slack_user_id,
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


def _read_nested_str(payload: dict[str, Any], *keys: str) -> str:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return str(current or "").strip()


def _is_not_helpful_modal_interaction(payload: dict[str, Any]) -> bool:
    callback_id = _read_nested_str(payload, "view", "callback_id")
    return callback_id == FEEDBACK_MODAL_CALLBACK_ID


def _read_selected_option_value(state: dict[str, Any]) -> str:
    selected_option = state.get("selected_option")
    if not isinstance(selected_option, dict):
        return ""
    return str(selected_option.get("value") or "").strip()


def _build_initial_option_field(
    options: list[dict[str, Any]],
    selected_value: str | None,
) -> dict[str, Any]:
    if not selected_value:
        return {}
    for option in options:
        if str(option.get("value") or "").strip() == selected_value:
            return {"initial_option": option}
    return {}


async def _apply_feedback_message_effect(
    request: SlackWebhookRequest,
    *,
    action_id: str,
    fallback_context: SlackFeedbackContext | None,
    submission: SlackNotHelpfulSubmission | None,
) -> FeedbackProcessResult:
    if action_id != NOT_HELPFUL_ACTION_ID or submission is None:
        return FeedbackProcessResult.SUCCESS
    return await _apply_not_helpful_message_effect(
        request,
        fallback_context=fallback_context,
        submission=submission,
    )


async def _apply_not_helpful_message_effect(
    request: SlackWebhookRequest,
    *,
    fallback_context: SlackFeedbackContext | None,
    submission: SlackNotHelpfulSubmission,
) -> FeedbackProcessResult:
    feedback_context = resolve_feedback_context(
        team_id=request.team_id,
        payload=request.event,
        fallback=fallback_context,
    )
    if feedback_context is None:
        return FeedbackProcessResult.ANSWER_NOT_FOUND

    client = await run_in_threadpool(_build_slack_client_sync, feedback_context.team_id)
    if client is None:
        return FeedbackProcessResult.INVALID

    if feedback_reason_requires_delete_policy(submission.reason):
        if submission.delete_policy == SlackFeedbackDeletePolicy.DELETE_ANSWER.value:
            return await _delete_feedback_message(
                client=client,
                feedback_context=feedback_context,
            )
        return await _mark_feedback_message_as_inaccurate(
            client=client,
            feedback_context=feedback_context,
        )
    return FeedbackProcessResult.SUCCESS


async def _delete_feedback_message(
    *,
    client: SlackApiClientWrapper,
    feedback_context: SlackFeedbackContext,
) -> FeedbackProcessResult:
    try:
        await client.delete_message(
            channel=feedback_context.channel_id,
            ts=feedback_context.message_ts,
        )
    except Exception:
        logger.warning(
            "slack_feedback_delete_message_failed",
            team_id=feedback_context.team_id,
            channel_id=feedback_context.channel_id,
            message_ts=feedback_context.message_ts,
            exc_info=True,
        )
        return FeedbackProcessResult.ANSWER_NOT_FOUND
    return FeedbackProcessResult.SUCCESS


async def _mark_feedback_message_as_inaccurate(
    *,
    client: SlackApiClientWrapper,
    feedback_context: SlackFeedbackContext,
) -> FeedbackProcessResult:
    blocks = feedback_context.message_blocks
    if not isinstance(blocks, list):
        return FeedbackProcessResult.ANSWER_NOT_FOUND

    updated_blocks = _prepend_warning_banner(blocks)
    try:
        await client.update_message(
            channel=feedback_context.channel_id,
            ts=feedback_context.message_ts,
            text=feedback_context.message_text or "Catch Up",
            blocks=updated_blocks,
        )
    except Exception:
        logger.warning(
            "slack_feedback_update_message_failed",
            team_id=feedback_context.team_id,
            channel_id=feedback_context.channel_id,
            message_ts=feedback_context.message_ts,
            exc_info=True,
        )
        return FeedbackProcessResult.INVALID
    return FeedbackProcessResult.SUCCESS


def _prepend_warning_banner(blocks: list[Any]) -> list[dict[str, Any]]:
    updated_blocks = [
        deepcopy(block)
        for block in blocks
        if isinstance(block, dict)
        and str(block.get("block_id") or "").strip() != WARNING_BANNER_BLOCK_ID
    ]
    return _fit_warning_banner_blocks([build_warning_banner_block(), *updated_blocks])


def _fit_warning_banner_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(blocks) <= SLACK_MESSAGE_BLOCK_LIMIT:
        return blocks
    return blocks[:SLACK_MESSAGE_BLOCK_LIMIT]


def _resolve_feedback_submission_target(
    *,
    db: Any,
    slack_user_id: str,
    payload: SlackFeedbackActionPayload,
) -> SlackFeedbackSubmissionTarget | FeedbackProcessResult:
    catchup_user_id = find_user_id_by_source_mapping(
        db,
        source_type=SourceType.SLACK,
        external_user_identifier=slack_user_id,
    )
    if catchup_user_id is None:
        return FeedbackProcessResult.NOT_REGISTERED

    room = get_chat_room_by_session_id(
        db=db,
        session_id=payload.session_id,
    )
    if room is None:
        return FeedbackProcessResult.ANSWER_NOT_FOUND

    message = get_message(
        db=db,
        room_id=room.id,
        message_id=payload.message_id,
    )
    if message is None:
        return FeedbackProcessResult.ANSWER_NOT_FOUND

    if _feedback_already_submitted(message):
        return FeedbackProcessResult.ALREADY_SUBMITTED

    return SlackFeedbackSubmissionTarget(
        catchup_user_id=catchup_user_id,
        message=message,
    )


def _save_feedback_submission(
    *,
    db: Any,
    submission_target: SlackFeedbackSubmissionTarget,
    body: FeedbackRequest,
) -> Any:
    if body.is_liked is True and (body.reasons or body.comment):
        raise LikedWithNegativeFeedbackError("긍정 피드백에 부정 피드백 사유를 포함할 수 없습니다.")

    message = submission_target.message
    message.is_liked = body.is_liked
    if body.is_liked is False:
        message.feedback_reasons = body.reasons
        message.feedback_comment = body.comment
    else:
        message.feedback_reasons = []
        message.feedback_comment = None

    _set_feedback_user_id(
        message=message,
        catchup_user_id=submission_target.catchup_user_id,
    )
    db.commit()
    db.refresh(message)
    return message


def _feedback_already_submitted(message: Any) -> bool:
    if getattr(message, "is_liked", None) is not None:
        return True
    return _read_feedback_user_id(message) is not None


def _read_feedback_user_id(message: Any) -> int | None:
    raw_value = getattr(message, "feedback_user", getattr(message, "feeback_user", None))
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _set_feedback_user_id(
    *,
    message: Any,
    catchup_user_id: int,
) -> None:
    if hasattr(message, "feedback_user"):
        message.feedback_user = str(catchup_user_id)
        return
    setattr(message, "feeback_user", str(catchup_user_id))
