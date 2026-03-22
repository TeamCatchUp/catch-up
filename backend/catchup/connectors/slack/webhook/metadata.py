from __future__ import annotations

import logging
from typing import Any, Callable

from sqlalchemy.orm import Session

from catchup.connectors.slack import webhook_service
from catchup.db.engine import SessionLocal

from .responses import (
    ignored_event_response,
    metadata_error_response,
    processed_metadata_response,
)

logger = logging.getLogger(__name__)

CHANNEL_UPSERT_EVENTS = frozenset(
    {"channel_created", "channel_rename", "group_created", "group_rename"}
)
CHANNEL_DELETE_EVENTS = frozenset({"channel_deleted", "group_deleted"})
CHANNEL_ARCHIVE_EVENTS = frozenset(
    {"channel_archive", "channel_unarchive", "group_archive", "group_unarchive"}
)
MEMBER_EVENTS = frozenset({"member_joined_channel", "member_left_channel"})
USER_EVENTS = frozenset({"team_join", "user_change"})

SUPPORTED_METADATA_EVENTS = frozenset().union(
    CHANNEL_UPSERT_EVENTS,
    CHANNEL_DELETE_EVENTS,
    CHANNEL_ARCHIVE_EVENTS,
    MEMBER_EVENTS,
    USER_EVENTS,
)


def is_supported_channel_membership_event(event: dict[str, Any]) -> bool:
    channel_type = str(event.get("channel_type") or "").strip().upper()
    if channel_type:
        return channel_type in {"C", "G"}

    channel_id = str(event.get("channel") or "").strip()
    return channel_id.startswith(("C", "G"))


def handle_metadata_event(
    *,
    team_id: str,
    event_type: str,
    event: dict[str, Any],
) -> dict[str, Any]:
    if event_type in MEMBER_EVENTS:
        if not is_supported_channel_membership_event(event):
            return ignored_event_response(
                event_type=event_type,
                reason="unsupported_channel",
            )

    resolved = _resolve_metadata_handler(event_type)
    if resolved is None:
        return ignored_event_response(
            event_type=event_type,
            reason="unsupported_event",
        )

    handler, label = resolved
    with SessionLocal() as db:
        try:
            _run_metadata_handler(
                db=db,
                team_id=team_id,
                event=event,
                handler=handler,
            )
            db.commit()
            return processed_metadata_response(event_type=event_type)
        except Exception as exc:
            db.rollback()
            logger.error(
                "[SLACK][WEBHOOK][METADATA] %s failed: team_id=%s, error=%s",
                label,
                team_id,
                exc,
            )
            return metadata_error_response()


def _resolve_metadata_handler(
    event_type: str,
) -> tuple[Callable[[Session, str, dict[str, Any]], None], str] | None:
    if event_type in CHANNEL_UPSERT_EVENTS:
        return webhook_service.handle_channel_upsert, "Channel upsert"

    if event_type in CHANNEL_DELETE_EVENTS:
        return webhook_service.handle_channel_delete, "Channel delete"

    if event_type in CHANNEL_ARCHIVE_EVENTS:
        return webhook_service.handle_channel_archive, "Channel archive"

    if event_type in MEMBER_EVENTS:
        return webhook_service.handle_member_event, "Member event"

    if event_type in USER_EVENTS:
        return webhook_service.handle_user_event, "User event"

    return None


def _run_metadata_handler(
    *,
    db: Session,
    team_id: str,
    event: dict[str, Any],
    handler: Callable[[Session, str, dict[str, Any]], None],
) -> None:
    handler(db, team_id, event)
