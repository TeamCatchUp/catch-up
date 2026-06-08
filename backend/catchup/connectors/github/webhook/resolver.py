from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from catchup.connectors.github.schemas import InstallationRepositoriesWebhookPayload
from catchup.connectors.github.schemas import InstallationWebhookPayload

_REPOSITORY_REFRESH_EVENTS = frozenset({
    "repository",
})

_USER_REFRESH_EVENTS = frozenset({
    "organization",
    "membership",
    "member",
})


@dataclass(slots=True, frozen=True)
class GithubMetadataResolution:
    action: str | None
    installation: InstallationWebhookPayload | None = None
    installation_repositories: InstallationRepositoriesWebhookPayload | None = None
    installation_id: int | None = None
    refresh_target: str | None = None
    ignored_reason: str | None = None
    ignored_action: str | None = None


def resolve_github_metadata_event(
    *,
    event_name: str,
    payload: dict[str, Any],
) -> GithubMetadataResolution:
    if event_name == "installation":
        data = InstallationWebhookPayload(**payload)
        if data.action not in {"created", "deleted", "suspended", "unsuspended"}:
            return GithubMetadataResolution(
                action=None,
                ignored_reason="unsupported_action",
                ignored_action=data.action,
            )
        return GithubMetadataResolution(
            action=f"installation_{data.action}",
            installation=data,
            installation_id=data.installation.id,
        )

    if event_name == "installation_repositories":
        data = InstallationRepositoriesWebhookPayload(**payload)
        return GithubMetadataResolution(
            action="installation_repositories",
            installation_repositories=data,
            installation_id=data.installation.id,
        )

    installation_id = _extract_installation_id(payload)
    if installation_id is None:
        return GithubMetadataResolution(
            action=None,
            ignored_reason="missing_installation_id",
        )

    return GithubMetadataResolution(
        action="metadata_refresh",
        installation_id=installation_id,
        refresh_target=_resolve_refresh_target(event_name),
    )


def _extract_installation_id(payload: dict[str, Any]) -> int | None:
    installation = payload.get("installation") or {}
    if not isinstance(installation, dict):
        return None

    raw = installation.get("id")
    if raw in (None, ""):
        return None

    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _resolve_refresh_target(event_name: str) -> str:
    if event_name in _REPOSITORY_REFRESH_EVENTS:
        return "repositories"
    if event_name in _USER_REFRESH_EVENTS:
        return "users"
    return "metadata"
