from __future__ import annotations

import asyncio

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.db.atlassian.oauth_repository import get_token_by_cloud_id
from catchup.db.engine import SessionLocal
from catchup.db.jira import domain_repository as jira_entities
from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.common.protocols import FullSyncTargetResolverProtocol
from catchup.sync.common.schemas import FullSyncDispatchRequest
from catchup.sync.common.schemas import FullSyncResolvedTargets
from catchup.sync.full.targets import resolve_full_sync_targets_from_rows

logger = structlog.get_logger(__name__)


class JiraFullSyncTargetResolver(FullSyncTargetResolverProtocol):
    def _load_token_sync(self, cloud_id: str):
        with SessionLocal() as db:
            return get_token_by_cloud_id(db, cloud_id)

    def _load_projects_sync(self, cloud_id: str):
        with SessionLocal() as db:
            return jira_entities.get_projects_by_cloud_id(db, cloud_id)

    async def resolve_full_sync_targets(
        self,
        *,
        request: FullSyncDispatchRequest,
    ) -> FullSyncResolvedTargets:
        # Jira는 scope_id=cloud_id, target_type=project, target_id=project_key 계약이다.
        cloud_id = request.scope_id.strip()
        if not cloud_id:
            raise SyncRequestException("scope_id is required")

        token, projects = await asyncio.gather(
            run_in_threadpool(self._load_token_sync, cloud_id),
            run_in_threadpool(self._load_projects_sync, cloud_id),
        )
        if token is None:
            raise SyncRequestException(
                "jira cloud is not connected",
                metadata={"cloud_id": cloud_id},
            )

        # listing 때 저장된 project snapshot과 요청 project_key를 매칭한다.
        requested_project_keys, resolved_targets = resolve_full_sync_targets_from_rows(
            request_targets=request.targets,
            rows=projects,
            target_type="project",
            key_getter=lambda project: project.project_key,
            name_getter=lambda project: project.project_name or project.project_key,
            error_message="requested targets contain unknown projects",
            error_metadata={"cloud_id": cloud_id},
            log_context={
                "connector": "jira",
                "cloud_id": cloud_id,
                "target_type": "project",
            },
        )

        logger.info(
            "jira_full_sync_targets_resolved",
            cloud_id=cloud_id,
            requested_count=len(requested_project_keys),
            resolved_count=len(resolved_targets.targets),
        )

        return resolved_targets


_jira_full_sync_target_resolver = JiraFullSyncTargetResolver()


def get_jira_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _jira_full_sync_target_resolver
