from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from catchup.db.github import domain_repository as github_entities
from catchup.db.github.installation_repository import get_installation_by_installation_id
from catchup.sync.common.schemas import FullSyncDispatchRequest
from catchup.sync.services.full_sync_orchestrator import (
    FullSyncResolvedTargets,
    FullSyncTarget,
    FullSyncTargetResolverProtocol,
)

logger = logging.getLogger(__name__)


class GithubFullSyncResolverValidationError(Exception):
    """GitHub full sync resolver validation error."""

    def __init__(self, detail: dict[str, object]):
        super().__init__(str(detail))
        self.detail = detail


class GithubFullSyncTargetResolver(FullSyncTargetResolverProtocol):

    async def resolve_full_sync_targets(
        self,
        *,
        db: Session,
        request: FullSyncDispatchRequest,
        sync_from: str,
    ) -> FullSyncResolvedTargets:
        scope_id = request.scope_id.strip()
        if not scope_id:
            raise GithubFullSyncResolverValidationError(
                detail={
                    "scope_id": request.scope_id,
                    "message": "scope_id is required",
                }
            )

        try:
            installation_id = int(scope_id)
        except ValueError as exc:
            raise GithubFullSyncResolverValidationError(
                detail={
                    "scope_id": request.scope_id,
                    "message": "scope_id must be a github installation_id",
                }
            ) from exc
    
        installation = get_installation_by_installation_id(db, installation_id)
        if installation is None:
            raise GithubFullSyncResolverValidationError(
                detail={
                    "scope_id": request.scope_id,
                    "installation_id": installation_id,
                    "message": "github installation not found",
                }
            )

        repositories = github_entities.get_repositories_by_installation(db, installation_id)

        if request.target_ids:
            requested_repo_ids = [item.strip() for item in request.target_ids if item and item.strip()]
            requested_repo_id_set = set(requested_repo_ids)

            resolved_repositories = [
                repo
                for repo in repositories
                if str(repo.repo_id) in requested_repo_id_set
            ]
            resolved_repo_id_set = {str(repo.repo_id) for repo in resolved_repositories}
            invalid_target_ids = [
                repo_id for repo_id in requested_repo_ids if repo_id not in resolved_repo_id_set
            ]
        else:
            resolved_repositories = repositories
            invalid_target_ids = []

        if not resolved_repositories:
            raise GithubFullSyncResolverValidationError(
                detail={
                    "scope_id": request.scope_id,
                    "installation_id": installation_id,
                    "message": "no syncable repositories found",
                    "requested_target_ids": request.target_ids or [],
                }
            )

        targets = [
            FullSyncTarget(
                target_type="repository",
                target_id=str(repo.repo_id),
                target_name=repo.full_name,
                metadata={
                    "repository_id": str(repo.repo_id),
                    "repository_full_name": repo.full_name,
                    "sync_from": sync_from,
                },
            )
            for repo in resolved_repositories
        ]

        logger.info(
            "[GITHUB][FULL SYNC][RESOLVER] Targets resolved: installation_id=%s, resolved=%s, invalid=%s",
            installation_id,
            len(targets),
            len(invalid_target_ids),
        )

        return FullSyncResolvedTargets(
            targets=targets,
            invalid_target_ids=invalid_target_ids,
            scope_metadata={"installation_id": str(installation_id)},
        )


_github_full_sync_target_resolver = GithubFullSyncTargetResolver()


def get_github_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _github_full_sync_target_resolver
