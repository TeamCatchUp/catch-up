from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from catchup.db.atlassian.oauth_repository import get_token_by_cloud_id
from catchup.db.jira import domain_repository as jira_entities
from catchup.sync.common.protocols import FullSyncTargetResolverProtocol
from catchup.sync.common.schemas import (
    FullSyncResolvedTargets,
    FullSyncDispatchRequest,
    FullSyncTarget,
)

logger = logging.getLogger(__name__)


def _normalize_requested_project_keys(target_ids: list[str] | None) -> list[str]:
    if target_ids is None:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in target_ids:
        candidate = (item or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized


class JiraFullSyncResolverValidationError(Exception):
    """Jira full sync resolver validation error."""

    def __init__(self, detail: dict[str, object]):
        super().__init__(str(detail))
        self.detail = detail


class JiraFullSyncTargetResolver(FullSyncTargetResolverProtocol):
    async def resolve_full_sync_targets(
        self,
        *,
        db: Session,
        request: FullSyncDispatchRequest,
        sync_from: str,
    ) -> FullSyncResolvedTargets:
        cloud_id = request.scope_id.strip()
        if not cloud_id:
            raise JiraFullSyncResolverValidationError(
                detail={
                    "scope_id": request.scope_id,
                    "message": "scope_id is required",
                }
            )

        token = get_token_by_cloud_id(db, cloud_id)
        if token is None:
            raise JiraFullSyncResolverValidationError(
                detail={
                    "scope_id": request.scope_id,
                    "cloud_id": cloud_id,
                    "message": "jira cloud is not connected",
                }
            )

        projects = jira_entities.get_projects_by_cloud_id(db, cloud_id)
        requested_project_keys = _normalize_requested_project_keys(request.target_ids)
        if request.target_ids is not None and not requested_project_keys:
            raise JiraFullSyncResolverValidationError(
                detail={
                    "scope_id": request.scope_id,
                    "cloud_id": cloud_id,
                    "message": "target_ids is empty after normalization",
                    "requested_target_ids": request.target_ids,
                }
            )

        if requested_project_keys:
            requested_project_key_set = set(requested_project_keys)

            resolved_projects = [
                project
                for project in projects
                if (project.project_key or "").strip() in requested_project_key_set
            ]
            resolved_project_key_set = {(project.project_key or "").strip() for project in resolved_projects}
            invalid_target_ids = [
                project_key
                for project_key in requested_project_keys
                if project_key not in resolved_project_key_set
            ]
        else:
            resolved_projects = projects
            invalid_target_ids = []

        if not resolved_projects:
            raise JiraFullSyncResolverValidationError(
                detail={
                    "scope_id": request.scope_id,
                    "cloud_id": cloud_id,
                    "message": "no syncable projects found",
                    "requested_target_ids": requested_project_keys,
                }
            )

        targets = [
            FullSyncTarget(
                target_type="project",
                target_id=(project.project_key or "").strip(),
                target_name=(project.project_name or project.project_key or "").strip(),
                metadata={
                    "project_id": str(project.project_id),
                    "project_key": (project.project_key or "").strip(),
                    "project_name": (project.project_name or project.project_key or "").strip(),
                    "sync_from": sync_from,
                },
            )
            for project in resolved_projects
            if (project.project_key or "").strip()
        ]

        logger.info(
            "[JIRA][FULL SYNC][RESOLVER] Targets resolved: cloud_id=%s, resolved=%s, invalid=%s",
            cloud_id,
            len(targets),
            len(invalid_target_ids),
        )

        return FullSyncResolvedTargets(
            targets=targets,
            invalid_target_ids=invalid_target_ids,
            scope_metadata={"cloud_id": cloud_id},
        )


_jira_full_sync_target_resolver = JiraFullSyncTargetResolver()


def get_jira_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _jira_full_sync_target_resolver
