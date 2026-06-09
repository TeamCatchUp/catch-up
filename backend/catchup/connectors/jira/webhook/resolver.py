from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class JiraMetadataResolution:
    action: str | None
    project: dict[str, Any] | None = None
    sprint: dict[str, Any] | None = None
    user: dict[str, Any] | None = None
    project_key: str | None = None
    ignored_reason: str | None = None


def resolve_jira_metadata_event(
    *,
    event_type: str,
    payload: dict[str, Any],
) -> JiraMetadataResolution:
    if event_type in {"jira:project_created", "jira:project_updated"}:
        project = _extract_project(payload)
        return JiraMetadataResolution(
            action="project_upsert",
            project=project,
            project_key=_extract_project_key(payload),
        )

    if event_type == "jira:project_deleted":
        return JiraMetadataResolution(
            action="project_delete",
            project_key=_extract_project_key(payload),
        )

    if event_type in {"sprint_created", "sprint_updated"}:
        return JiraMetadataResolution(
            action="sprint_upsert",
            sprint=_extract_sprint(payload),
            project_key=_extract_project_key(payload),
        )

    if event_type == "sprint_deleted":
        return JiraMetadataResolution(
            action="sprint_delete",
            sprint=_extract_sprint(payload),
            project_key=_extract_project_key(payload),
        )

    if event_type in {"user_created", "user_updated"}:
        return JiraMetadataResolution(
            action="user_upsert",
            user=_extract_user(payload),
        )

    if event_type == "user_deleted":
        return JiraMetadataResolution(
            action="user_delete",
            user=_extract_user(payload),
        )

    return JiraMetadataResolution(
        action=None,
        ignored_reason="unsupported_event",
    )


def _extract_project(payload: dict[str, Any]) -> dict[str, Any]:
    project = payload.get("project") or {}
    if not isinstance(project, dict):
        return {}
    return project


def _extract_sprint(payload: dict[str, Any]) -> dict[str, Any]:
    sprint = payload.get("sprint") or {}
    if not isinstance(sprint, dict):
        return {}
    return sprint


def _extract_project_key(payload: dict[str, Any]) -> str | None:
    project = _extract_project(payload)
    return project.get("key") or payload.get("projectKey")


def _extract_user(payload: dict[str, Any]) -> dict[str, Any]:
    user = payload.get("user") or payload.get("account") or {}
    if not isinstance(user, dict):
        return {}
    return user
