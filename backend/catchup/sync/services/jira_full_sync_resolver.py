from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from catchup.db.atlassian.oauth_repository import get_token_by_cloud_id
from catchup.db.jira import domain_repository as jira_entities
from catchup.sync.common.exceptions import SyncRequestError
from catchup.sync.common.protocols import FullSyncTargetResolverProtocol
from catchup.sync.common.schemas import (
    FullSyncResolvedTargets,
    FullSyncDispatchRequest,
    FullSyncTarget,
)

logger = logging.getLogger(__name__)


def _normalize_requested_project_keys(target_ids: list[str] | None) -> list[str]:
    if target_ids is None:
        raise SyncRequestError("target_ids is required")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in target_ids:
        candidate = (item or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)

    if not normalized:
        raise SyncRequestError(
            "target_ids is empty after normalization",
            metadata={"requested_target_ids": target_ids},
        )

    return normalized


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
            raise SyncRequestError("scope_id is required")

        token = get_token_by_cloud_id(db, cloud_id)
        if token is None:
            raise SyncRequestError(
                "jira cloud is not connected",
                metadata={"cloud_id": cloud_id},
            )

        projects = jira_entities.get_projects_by_cloud_id(db, cloud_id)
        requested_project_keys = _normalize_requested_project_keys(request.target_ids)
        project_map = {
            (project.project_key or "").strip(): project
            for project in projects
            if (project.project_key or "").strip()
        }
        invalid_target_ids = [
            project_key
            for project_key in requested_project_keys
            if project_key not in project_map
        ]
        if invalid_target_ids:
            raise SyncRequestError(
                "requested target_ids contain unknown projects",
                metadata={
                    "cloud_id": cloud_id,
                    "requested_target_ids": requested_project_keys,
                    "invalid_target_ids": invalid_target_ids,
                },
            )

        resolved_projects = [
            project_map[project_key]
            for project_key in requested_project_keys
        ]

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
            "[JIRA][FULL SYNC][RESOLVER] Targets resolved: cloud_id=%s, requested=%s, resolved=%s",
            cloud_id,
            len(requested_project_keys),
            len(targets),
        )

        return FullSyncResolvedTargets(
            targets=targets,
            invalid_target_ids=[],
            scope_metadata={"cloud_id": cloud_id},
        )


_jira_full_sync_target_resolver = JiraFullSyncTargetResolver()


def get_jira_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _jira_full_sync_target_resolver
