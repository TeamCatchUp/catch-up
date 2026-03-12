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
)
from catchup.sync.services.full_sync_target_normalizer import (
    resolve_full_sync_targets_from_rows,
)

logger = logging.getLogger(__name__)


class JiraFullSyncTargetResolver(FullSyncTargetResolverProtocol):
    async def resolve_full_sync_targets(
        self,
        *,
        db: Session,
        request: FullSyncDispatchRequest,
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
        requested_project_keys, resolved_targets = resolve_full_sync_targets_from_rows(
            request_target_ids=request.target_ids,
            rows=projects,
            target_type="project",
            key_getter=lambda project: project.project_key,
            name_getter=lambda project: project.project_name or project.project_key,
            error_message="requested target_ids contain unknown projects",
            error_metadata={"cloud_id": cloud_id},
            log_context={
                "connector": "jira",
                "cloud_id": cloud_id,
                "target_type": "project",
            },
        )

        logger.info(
            "[JIRA][FULL SYNC][RESOLVER] Targets resolved: cloud_id=%s, requested=%s, resolved=%s",
            cloud_id,
            len(requested_project_keys),
            len(resolved_targets.targets),
        )

        return resolved_targets


_jira_full_sync_target_resolver = JiraFullSyncTargetResolver()


def get_jira_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _jira_full_sync_target_resolver
