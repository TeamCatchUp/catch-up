from __future__ import annotations

import logging

from catchup.db.engine import SessionLocal
from catchup.db.github import domain_repository as github_entities
from catchup.db.github.installation_repository import get_installation_by_installation_id
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


class GithubFullSyncTargetResolver(FullSyncTargetResolverProtocol):

    async def resolve_full_sync_targets(
        self,
        *,
        request: FullSyncDispatchRequest,
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

        with SessionLocal() as db:
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
        requested_repo_ids, resolved_targets = resolve_full_sync_targets_from_rows(
            request_target_ids=request.target_ids,
            rows=repositories,
            target_type="repository",
            key_getter=lambda repo: str(repo.repo_id),
            name_getter=lambda repo: repo.full_name,
            error_message="requested target_ids contain unknown repositories",
            error_metadata={"installation_id": installation_id},
            log_context={
                "connector": "github",
                "installation_id": installation_id,
                "target_type": "repository",
            },
        )

        logger.info(
            "[GITHUB][FULL SYNC][RESOLVER] Targets resolved: installation_id=%s, requested=%s, resolved=%s",
            installation_id,
            len(requested_repo_ids),
            len(resolved_targets.targets),
        )

        return resolved_targets


_github_full_sync_target_resolver = GithubFullSyncTargetResolver()


def get_github_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _github_full_sync_target_resolver
