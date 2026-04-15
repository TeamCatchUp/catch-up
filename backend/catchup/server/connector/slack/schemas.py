from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class SlackWebhookRequest:
    wrapper_type: str
    team_id: str
    event: dict[str, Any]
    event_type: str
    event_subtype: str
    challenge: str | None = None

    @classmethod
    def from_raw(
        cls,
        *,
        wrapper_type: str,
        team_id: str,
        event: dict[str, Any] | None,
        challenge: str | None = None,
    ) -> SlackWebhookRequest:
        normalized_event = event or {}
        return cls(
            wrapper_type=str(wrapper_type or "").strip(),
            team_id=str(team_id or "").strip(),
            event=normalized_event,
            event_type=str(normalized_event.get("type") or "").strip(),
            event_subtype=str(normalized_event.get("subtype") or "").strip(),
            challenge=challenge,
        )


@dataclass(slots=True, frozen=True)
class SlackChallengeWebhookResponse:
    challenge: str | None


@dataclass(slots=True, frozen=True)
class SlackIgnoredWebhookResponse:
    status: str
    reason: str | None = None
    event_type: str | None = None
    wrapper_type: str | None = None
    blocked_count: int | None = None


@dataclass(slots=True, frozen=True)
class SlackAcceptedWebhookResponse:
    status: str
    event_type: str
    record_keys: list[str]
    blocked_count: int | None = None


@dataclass(slots=True, frozen=True)
class SlackStatusWebhookResponse:
    status: str
    event_type: str


@dataclass(slots=True, frozen=True)
class SlackErrorWebhookResponse:
    status: str
    reason: str


type SlackWebhookResponse = (
    SlackChallengeWebhookResponse
    | SlackIgnoredWebhookResponse
    | SlackAcceptedWebhookResponse
    | SlackStatusWebhookResponse
    | SlackErrorWebhookResponse
)
