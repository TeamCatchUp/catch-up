from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class GithubWebhookRequest:
    event_name: str
    payload: dict[str, Any]

    @classmethod
    def from_raw(
        cls,
        *,
        event_name: str | None,
        payload: dict[str, Any],
    ) -> GithubWebhookRequest:
        return cls(
            event_name=str(event_name or "").strip().lower(),
            payload=payload,
        )


@dataclass(slots=True, frozen=True)
class JiraWebhookRequest:
    cloud_id: str
    event_type: str
    payload: dict[str, Any]

    @classmethod
    def from_raw(
        cls,
        *,
        cloud_id: str,
        payload: dict[str, Any],
    ) -> JiraWebhookRequest:
        return cls(
            cloud_id=cloud_id.strip(),
            event_type=str(payload.get("webhookEvent") or "").strip().lower(),
            payload=payload,
        )


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
