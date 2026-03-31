from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from catchup.connectors.slack import webhook_service
from catchup.db.engine import SessionLocal
from catchup.sync.ingress.types import SlackWebhookRequest
from catchup.sync.ingress.types import SlackWebhookResponse

from catchup.connectors.slack.webhook.responses import ignored_event_response
from catchup.connectors.slack.webhook.responses import metadata_error_response
from catchup.connectors.slack.webhook.responses import processed_metadata_response

logger = structlog.get_logger(__name__)

CHANNEL_UPSERT_EVENTS = frozenset(
    {"channel_created", "channel_rename", "group_created", "group_rename"}
)
CHANNEL_DELETE_EVENTS = frozenset({"channel_deleted", "group_deleted"})
CHANNEL_ARCHIVE_EVENTS = frozenset(
    {"channel_archive", "channel_unarchive", "group_archive", "group_unarchive"}
)
MEMBER_EVENTS = frozenset({"member_joined_channel", "member_left_channel"})
USER_EVENTS = frozenset({"team_join", "user_change"})


def is_supported_channel_membership_event(event: dict[str, Any]) -> bool:
    channel_type = str(event.get("channel_type") or "").strip().upper()
    if channel_type:
        return channel_type in {"C", "G"}

    channel_id = str(event.get("channel") or "").strip()
    return channel_id.startswith(("C", "G"))


async def handle_metadata_event(
    request: SlackWebhookRequest,
) -> SlackWebhookResponse:
    if request.event_type in MEMBER_EVENTS:
        if not is_supported_channel_membership_event(request.event):
            return ignored_event_response(
                event_type=request.event_type,
                reason="unsupported_channel",
            )

    resolved = _resolve_metadata_handler(request.event_type)
    if resolved is None:
        return ignored_event_response(
            event_type=request.event_type,
            reason="unsupported_event",
        )

    return await run_in_threadpool(
        _handle_metadata_event_sync,
        request,
        resolved,
    )


def _handle_metadata_event_sync(
    request: SlackWebhookRequest,
    handler: Callable[[Session, str, dict[str, Any]], None],
) -> SlackWebhookResponse:
    with SessionLocal() as db:
        try:
            _run_metadata_handler(
                db=db,
                team_id=request.team_id,
                event=request.event,
                handler=handler,
            )
            db.commit()
            return processed_metadata_response(event_type=request.event_type)
        except Exception as exc:
            db.rollback()
            logger.error(
                "slack_metadata_sync_failed",
                team_id=request.team_id,
                event_type=request.event_type,
                error=str(exc),
            )
            return metadata_error_response()


def _resolve_metadata_handler(
    event_type: str,
) -> Callable[[Session, str, dict[str, Any]], None] | None:
    if event_type in CHANNEL_UPSERT_EVENTS:
        return webhook_service.handle_channel_upsert

    if event_type in CHANNEL_DELETE_EVENTS:
        return webhook_service.handle_channel_delete

    if event_type in CHANNEL_ARCHIVE_EVENTS:
        return webhook_service.handle_channel_archive

    if event_type in MEMBER_EVENTS:
        return webhook_service.handle_member_event

    if event_type in USER_EVENTS:
        return webhook_service.handle_user_event

    return None


def _run_metadata_handler(
    *,
    db: Session,
    team_id: str,
    event: dict[str, Any],
    handler: Callable[[Session, str, dict[str, Any]], None],
) -> None:
    handler(db, team_id, event)
