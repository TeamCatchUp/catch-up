from __future__ import annotations

import structlog

from catchup.connectors.slack.webhook.responses import accepted_async_response
from catchup.connectors.slack.webhook.responses import accepted_incremental_response
from catchup.connectors.slack.webhook.responses import ignored_event_response
from catchup.connectors.slack.webhook.responses import ignored_wrapper_response
from catchup.connectors.slack.webhook.responses import url_verification_response
from catchup.server.connector.slack.app_mention_adapter import schedule_app_mention
from catchup.server.connector.slack.interaction_handler import handle_block_actions
from catchup.server.connector.slack.interaction_handler import handle_view_submission
from catchup.server.connector.slack.schemas import SlackIgnoredWebhookResponse
from catchup.server.connector.slack.schemas import SlackWebhookRequest
from catchup.server.connector.slack.schemas import SlackWebhookResponse
from catchup.sync.incremental.resolve import resolve_slack_event
from catchup.sync.incremental.service import get_incremental_service
from catchup.sync.metadata.slack import handle_metadata_event

logger = structlog.get_logger(__name__)

SUPPORTED_METADATA_EVENTS = frozenset({
    "channel_created",
    "channel_rename",
    "group_created",
    "group_rename",
    "channel_deleted",
    "group_deleted",
    "channel_archive",
    "channel_unarchive",
    "group_archive",
    "group_unarchive",
    "member_joined_channel",
    "member_left_channel",
    "team_join",
    "user_change",
})


def _is_direct_message_chat_event(event: dict[str, object]) -> bool:
    if str(event.get("type") or "").strip() != "message":
        # DM 채널에서 발생하는 Message 이외의 이벤트를 무시한다
        return False

    if str(event.get("channel_type") or "").strip() != "im":
        # 공개 채널 / 비공개 Group 채널은 제외한다 (mpim)
        return False

    if "bot_id" in event:
        # Bot이 생성한 이벤트는 무시한다 (채널 초대, 자동 메세지 등 ...)
        return False

    if str(event.get("subtype") or "").strip():
        # 수정, 삭제 이벤트로 트리거 되지 않도록 방지
        return False

    channel_id = str(event.get("channel") or "").strip()
    slack_user_id = str(event.get("user") or "").strip()
    text = str(event.get("text") or "").strip()
    timestamp = str(event.get("ts") or "").strip()
    if not channel_id or not slack_user_id or not text or not timestamp:
        return False

    return channel_id.startswith("D")


async def handle_slack_webhook(
    *,
    request: SlackWebhookRequest,
) -> SlackWebhookResponse:
    if request.wrapper_type == "url_verification":
        logger.debug("slack_webhook_url_verification")
        return url_verification_response(challenge=request.challenge)

    if request.wrapper_type == "block_actions":
        return await handle_block_actions(request=request)

    if request.wrapper_type == "view_submission":
        return await handle_view_submission(request=request)

    if request.wrapper_type != "event_callback":
        logger.warning(
            "slack_webhook_ignored_unknown_wrapper",
            wrapper_type=request.wrapper_type,
        )
        return ignored_wrapper_response(wrapper_type=request.wrapper_type)

    if not request.event:
        logger.warning("slack_webhook_ignored_empty_event")
        return SlackIgnoredWebhookResponse(status="ignored", reason="empty_event")

    if not request.team_id:
        logger.warning("slack_webhook_ignored_missing_team_id")
        return SlackIgnoredWebhookResponse(status="ignored", reason="missing_team_id")

    if request.event_type in SUPPORTED_METADATA_EVENTS:
        return await handle_metadata_event(request)

    if request.event_type == "app_mention":
        # Slack Webhook Timeout을 위해 즉시 응답후 답변 생성 스케쥴링
        schedule_app_mention(request)
        return accepted_async_response(event_type=request.event_type)

    if request.event_type == "message":
        # DM Messages는 Incremental Sync 경로를 타지 않게 방어 / app_mention 생성을 스케쥴링
        if _is_direct_message_chat_event(request.event):
            logger.info(
                "slack_direct_message_routed_to_chat",
                team_id=request.team_id,
                channel_id=str(request.event.get("channel") or "").strip(),
                slack_user_id=str(request.event.get("user") or "").strip(),
            )
            schedule_app_mention(request)
            return accepted_async_response(event_type=request.event_type)

        return await _handle_incremental_event(request)

    logger.warning(
        "slack_webhook_ignored_unsupported_event",
        team_id=request.team_id,
        event_type=request.event_type,
        event_subtype=request.event_subtype,
    )
    return ignored_event_response(
        event_type=request.event_type,
        reason="unsupported_event",
    )


async def _handle_incremental_event(
    request: SlackWebhookRequest,
) -> SlackWebhookResponse:
    resolved = resolve_slack_event(team_id=request.team_id, event=request.event)
    if not resolved.changes:
        return ignored_event_response(
            event_type=request.event_type,
            reason=resolved.reason or "unsupported_message_payload",
        )

    result = await get_incremental_service().dispatch_changes(
        changes=resolved.changes,
    )
    if result.blocked_count > 0:
        if not result.record_keys:
            logger.info(
                "slack_incremental_blocked_before_full_sync",
                team_id=request.team_id,
                event_type=request.event_type,
                blocked_count=result.blocked_count,
            )
            return ignored_event_response(
                event_type=request.event_type,
                reason="full_sync_required",
                blocked_count=result.blocked_count,
            )

        logger.info(
            "slack_incremental_partially_blocked",
            team_id=request.team_id,
            event_type=request.event_type,
            record_key_count=len(result.record_keys),
            blocked_count=result.blocked_count,
        )

    return accepted_incremental_response(
        event_type=request.event_type,
        record_keys=result.record_keys,
        blocked_count=result.blocked_count,
    )
