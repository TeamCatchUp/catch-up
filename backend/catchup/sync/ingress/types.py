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
class SlackProcessedWebhookResponse:
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
    | SlackProcessedWebhookResponse
    | SlackErrorWebhookResponse
)
