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
