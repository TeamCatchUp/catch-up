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
class GithubIgnoredWebhookResponse:
    status: str
    event: str
    reason: str
    blocked_count: int | None = None
    action: str | None = None


@dataclass(slots=True, frozen=True)
class GithubAcceptedWebhookResponse:
    status: str
    event: str
    record_keys: list[str]
    blocked_count: int | None = None


@dataclass(slots=True, frozen=True)
class GithubProcessedWebhookResponse:
    status: str
    event: str
    installation_id: int
    refresh_target: str


@dataclass(slots=True, frozen=True)
class GithubInstallationStatusWebhookResponse:
    status: str
    installation_id: int


@dataclass(slots=True, frozen=True)
class GithubInstallationRepositoriesWebhookResponse:
    status: str
    event: str
    installation_id: int
    added: int
    removed: int


type GithubWebhookResponse = (
    GithubIgnoredWebhookResponse
    | GithubAcceptedWebhookResponse
    | GithubProcessedWebhookResponse
    | GithubInstallationStatusWebhookResponse
    | GithubInstallationRepositoriesWebhookResponse
)


@dataclass(slots=True, frozen=True)
class JiraIgnoredWebhookResponse:
    status: str
    event_type: str
    reason: str
    blocked_count: int | None = None


@dataclass(slots=True, frozen=True)
class JiraAcceptedWebhookResponse:
    status: str
    event_type: str
    record_keys: list[str]
    blocked_count: int | None = None


@dataclass(slots=True, frozen=True)
class JiraProcessedWebhookResponse:
    status: str
    event_type: str
    entity: str
    key: str | None = None
    id: int | str | None = None


type JiraWebhookResponse = (
    JiraIgnoredWebhookResponse
    | JiraAcceptedWebhookResponse
    | JiraProcessedWebhookResponse
)
