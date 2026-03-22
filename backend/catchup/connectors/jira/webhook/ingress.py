from __future__ import annotations

import logging
from typing import Any

from .incremental import SUPPORTED_INCREMENTAL_EVENTS, handle_incremental_event
from .metadata import SUPPORTED_METADATA_EVENTS, handle_metadata_event
from .responses import ignored_event_response

logger = logging.getLogger(__name__)


async def handle_webhook(
    *,
    cloud_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    event_type = str(payload.get("webhookEvent") or "").strip().lower()

    if event_type in SUPPORTED_METADATA_EVENTS:
        return await handle_metadata_event(
            cloud_id=cloud_id,
            event_type=event_type,
            payload=payload,
        )

    if event_type in SUPPORTED_INCREMENTAL_EVENTS:
        return await handle_incremental_event(
            cloud_id=cloud_id,
            event_type=event_type,
            payload=payload,
        )

    logger.info(
        "[JIRA][WEBHOOK][INGRESS] Ignored payload: cloud_id=%s, event_type=%s",
        cloud_id,
        event_type,
    )
    return ignored_event_response(
        event_type=event_type,
        reason="unsupported_event",
    )
