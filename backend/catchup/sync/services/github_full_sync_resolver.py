from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from catchup.db.github import domain_repository as github_entities
from catchup.db.github.installation_repository import get_installation_by_installation_id
from catchup.sync.common.exceptions import SyncRequestError
from catchup.sync.common.protocols import FullSyncTargetResolverProtocol
from catchup.sync.common.schemas import (
    FullSyncResolvedTargets,
    FullSyncDispatchRequest,
    FullSyncTarget,
)

logger = logging.getLogger(__name__)


def _normalize_requested_repo_ids(target_ids: list[str] | None) -> list[str]:
    if target_ids is None:
        raise SyncRequestError("target_ids is required")

    normalized: list[str] = []
    seen: set[str] = set()
    
    for item in target_ids:
        candidate = (item or "").strip()
        if not candidate:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    
    if not normalized:
        raise SyncRequestError(
            "target_ids is empty after normalization",
            metadata={"requested_target_ids": target_ids},
        )

    return normalized
    


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
            raise SyncRequestError("scope_id is required")

        try:
            installation_id = int(scope_id)
        except ValueError as exc:
            raise SyncRequestError(
                "scope_id must be a github installation_id",
                metadata={"scope_id": request.scope_id},
            ) from exc
    
        installation = get_installation_by_installation_id(db, installation_id)
        if installation is None:
            raise SyncRequestError(
                "github installation not found",
                metadata={"installation_id": installation_id},
            )

        repositories = github_entities.get_repositories_by_installation(
            db,
            installation_id,
        )
        requested_repo_ids = _normalize_requested_repo_ids(request.target_ids)
        repository_map = {str(repo.repo_id): repo for repo in repositories}
        invalid_target_ids = [
            repo_id
            for repo_id in requested_repo_ids
            if repo_id not in repository_map
        ]
        if invalid_target_ids:
            raise SyncRequestError(
                "requested target_ids contain unknown repositories",
                metadata={
                    "installation_id": installation_id,
                    "requested_target_ids": requested_repo_ids,
                    "invalid_target_ids": invalid_target_ids,
                },
            )

        resolved_repositories = [
            repository_map[repo_id]
            for repo_id in requested_repo_ids
        ]

        targets = [
            FullSyncTarget(
                target_type="repository",
                target_id=str(repo.repo_id),
                target_name=repo.full_name,
                metadata={},
            )
            for repo in resolved_repositories
        ]

        logger.info(
            "[GITHUB][FULL SYNC][RESOLVER] Targets resolved: installation_id=%s, requested=%s, resolved=%s",
            installation_id,
            len(requested_repo_ids),
            len(targets),
        )

        return FullSyncResolvedTargets(
            targets=targets,
            invalid_target_ids=[],
        )


_github_full_sync_target_resolver = GithubFullSyncTargetResolver()


def get_github_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _github_full_sync_target_resolver
