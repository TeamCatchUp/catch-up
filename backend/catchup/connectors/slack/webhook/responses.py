from __future__ import annotations

from typing import Any

from catchup.server.connector.slack.schemas import SlackAcceptedWebhookResponse
from catchup.server.connector.slack.schemas import SlackChallengeWebhookResponse
from catchup.server.connector.slack.schemas import SlackErrorWebhookResponse
from catchup.server.connector.slack.schemas import SlackIgnoredWebhookResponse
from catchup.server.connector.slack.schemas import SlackStatusWebhookResponse


def url_verification_response(*, challenge: str | None) -> SlackChallengeWebhookResponse:
    return SlackChallengeWebhookResponse(challenge=challenge)


def ignored_event_response(
    *,
    event_type: str,
    reason: str,
    **extra: Any,
) -> SlackIgnoredWebhookResponse:
    return SlackIgnoredWebhookResponse(
        status="ignored",
        event_type=event_type,
        reason=reason,
        blocked_count=extra.get("blocked_count"),
    )


def ignored_wrapper_response(*, wrapper_type: str) -> SlackIgnoredWebhookResponse:
    return SlackIgnoredWebhookResponse(
        status="ignored",
        wrapper_type=wrapper_type,
    )


def accepted_incremental_response(
    *,
    event_type: str,
    record_keys: list[str],
    blocked_count: int = 0,
) -> SlackAcceptedWebhookResponse:
    return SlackAcceptedWebhookResponse(
        status="accepted",
        event_type=event_type,
        record_keys=record_keys,
        blocked_count=blocked_count or None,
    )


def accepted_async_response(*, event_type: str) -> SlackStatusWebhookResponse:
    return SlackStatusWebhookResponse(
        status="accepted",
        event_type=event_type,
    )


def processed_metadata_response(*, event_type: str) -> SlackStatusWebhookResponse:
    return SlackStatusWebhookResponse(
        status="processed",
        event_type=event_type,
    )


def metadata_error_response() -> SlackErrorWebhookResponse:
    return SlackErrorWebhookResponse(
        status="error",
        reason="processing_failed",
    )
