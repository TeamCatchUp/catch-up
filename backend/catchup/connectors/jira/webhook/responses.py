from __future__ import annotations

from typing import Any

from catchup.sync.ingress.types import JiraAcceptedWebhookResponse
from catchup.sync.ingress.types import JiraIgnoredWebhookResponse
from catchup.sync.ingress.types import JiraProcessedWebhookResponse


def ignored_event_response(
    *,
    event_type: str,
    reason: str,
    **extra: Any,
) -> JiraIgnoredWebhookResponse:
    return JiraIgnoredWebhookResponse(
        status="ignored",
        event_type=event_type,
        reason=reason,
        blocked_count=extra.get("blocked_count"),
    )


def accepted_incremental_response(
    *,
    event_type: str,
    record_keys: list[str],
    blocked_count: int = 0,
) -> JiraAcceptedWebhookResponse:
    return JiraAcceptedWebhookResponse(
        status="accepted",
        event_type=event_type,
        record_keys=record_keys,
        blocked_count=blocked_count or None,
    )


def processed_metadata_response(
    *,
    event_type: str,
    entity: str,
    key: str | None = None,
    entity_id: int | str | None = None,
) -> JiraProcessedWebhookResponse:
    return JiraProcessedWebhookResponse(
        status="processed",
        event_type=event_type,
        entity=entity,
        key=key,
        id=entity_id,
    )
