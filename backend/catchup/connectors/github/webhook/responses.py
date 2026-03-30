from __future__ import annotations

from typing import Any

from catchup.sync.ingress.types import GithubAcceptedWebhookResponse
from catchup.sync.ingress.types import GithubIgnoredWebhookResponse
from catchup.sync.ingress.types import GithubInstallationRepositoriesWebhookResponse
from catchup.sync.ingress.types import GithubInstallationStatusWebhookResponse
from catchup.sync.ingress.types import GithubProcessedWebhookResponse


def ignored_event_response(
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


def accepted_incremental_response(
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


def processed_metadata_response(
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


def installation_status_response(
    *,
    status: str,
    installation_id: int,
) -> GithubInstallationStatusWebhookResponse:
    return GithubInstallationStatusWebhookResponse(
        status=status,
        installation_id=installation_id,
    )


def installation_repositories_response(
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
