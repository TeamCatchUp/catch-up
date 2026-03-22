from __future__ import annotations

import logging
from typing import Any

from catchup.connectors.slack.schemas import SlackEventWrapper
from catchup.db.engine import SessionLocal

from .incremental import handle_incremental_event
from .metadata import SUPPORTED_METADATA_EVENTS, handle_metadata_event
from .responses import (
    ignored_event_response,
    ignored_wrapper_response,
    url_verification_response,
)

logger = logging.getLogger(__name__)


def handle_webhook(
    *,
    payload: dict[str, Any],
) -> dict[str, Any]:
    event_wrapper = SlackEventWrapper(**payload)

    if event_wrapper.type == "url_verification":
        logger.info("[SLACK][WEBHOOK][INGRESS] URL verification received")
        return url_verification_response(challenge=event_wrapper.challenge)

    if event_wrapper.type != "event_callback":
        logger.warning(
            "[SLACK][WEBHOOK][INGRESS] Unknown wrapper type: type=%s",
            event_wrapper.type,
        )
        return ignored_wrapper_response(wrapper_type=event_wrapper.type)

    if not event_wrapper.event:
        logger.warning("[SLACK][WEBHOOK][INGRESS] Empty event callback")
        return {"status": "ignored", "reason": "empty_event"}

    if not event_wrapper.team_id:
        logger.warning("[SLACK][WEBHOOK][INGRESS] Missing team_id in callback")
        return {"status": "ignored", "reason": "missing_team_id"}

    event = event_wrapper.event
    event_type = str(event.get("type") or "").strip()
    event_subtype = str(event.get("subtype") or "").strip()
    team_id = event_wrapper.team_id

    logger.info(
        "[SLACK][WEBHOOK][INGRESS] Received event: team_id=%s, type=%s, subtype=%s",
        team_id,
        event_type,
        event_subtype,
    )

    if event_type in SUPPORTED_METADATA_EVENTS:
        return handle_metadata_event(
            team_id=team_id,
            event_type=event_type,
            event=event,
        )

    if event_type == "message":
        with SessionLocal() as db:
            return handle_incremental_event(
                db=db,
                team_id=team_id,
                event_type=event_type,
                event=event,
            )

    logger.debug(
        "[SLACK][WEBHOOK][INGRESS] Ignored unsupported event: team_id=%s, type=%s, subtype=%s",
        team_id,
        event_type,
        event_subtype,
    )
    return ignored_event_response(
        event_type=event_type,
        reason="unsupported_event",
    )
