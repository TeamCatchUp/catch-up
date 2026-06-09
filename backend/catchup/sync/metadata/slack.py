from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from catchup.connectors.slack.webhook.resolver import resolve_slack_metadata_event
from catchup.db.engine import SessionLocal
from catchup.server.connector.slack.responses import ignored_event_response
from catchup.server.connector.slack.responses import metadata_error_response
from catchup.server.connector.slack.responses import processed_metadata_response
from catchup.server.connector.slack.schemas import SlackWebhookRequest
from catchup.server.connector.slack.schemas import SlackWebhookResponse
from catchup.sync.metadata import slack_store

logger = structlog.get_logger(__name__)

_METADATA_HANDLERS: dict[str, Callable[[Session, str, dict[str, Any]], None]] = {
    "channel_upsert": slack_store.handle_channel_upsert,
    "channel_delete": slack_store.handle_channel_delete,
    "channel_archive": slack_store.handle_channel_archive,
    "member": slack_store.handle_member_event,
    "user": slack_store.handle_user_event,
}


async def handle_metadata_event(
    request: SlackWebhookRequest,
) -> SlackWebhookResponse:
    resolved = resolve_slack_metadata_event(
        event_type=request.event_type,
        event=request.event,
    )
    if resolved.action is None:
        return ignored_event_response(
            event_type=request.event_type,
            reason=resolved.ignored_reason or "unsupported_event",
        )

    handler = _METADATA_HANDLERS[resolved.action]
    return await run_in_threadpool(
        _handle_metadata_event_sync,
        request,
        handler,
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


def _run_metadata_handler(
    *,
    db: Session,
    team_id: str,
    event: dict[str, Any],
    handler: Callable[[Session, str, dict[str, Any]], None],
) -> None:
    handler(db, team_id, event)
