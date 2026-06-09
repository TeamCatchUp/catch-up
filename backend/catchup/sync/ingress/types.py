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


def ignored_github_event_response(
    *,
    event: str,
    reason: str,
    **extra: Any,
) -> GithubIgnoredWebhookResponse:
    return GithubIgnoredWebhookResponse(
        status="ignored",
        event=event,
        reason=reason,
        blocked_count=extra.get("blocked_count"),
        action=extra.get("action"),
    )


def accepted_github_incremental_response(
    *,
    event: str,
    record_keys: list[str],
    blocked_count: int = 0,
) -> GithubAcceptedWebhookResponse:
    return GithubAcceptedWebhookResponse(
        status="accepted",
        event=event,
        record_keys=record_keys,
        blocked_count=blocked_count or None,
    )


def processed_github_metadata_response(
    *,
    event: str,
    installation_id: int,
    refresh_target: str,
) -> GithubProcessedWebhookResponse:
    return GithubProcessedWebhookResponse(
        status="processed",
        event=event,
        installation_id=installation_id,
        refresh_target=refresh_target,
    )


def github_installation_status_response(
    *,
    status: str,
    installation_id: int,
) -> GithubInstallationStatusWebhookResponse:
    return GithubInstallationStatusWebhookResponse(
        status=status,
        installation_id=installation_id,
    )


def github_installation_repositories_response(
    *,
    installation_id: int,
    added: int,
    removed: int,
) -> GithubInstallationRepositoriesWebhookResponse:
    return GithubInstallationRepositoriesWebhookResponse(
        status="processed",
        event="installation_repositories",
        installation_id=installation_id,
        added=added,
        removed=removed,
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


def ignored_jira_event_response(
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


def accepted_jira_incremental_response(
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


def processed_jira_metadata_response(
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
