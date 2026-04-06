from __future__ import annotations

import asyncio

from fastapi.concurrency import run_in_threadpool
import structlog

from catchup.db.engine import SessionLocal
from catchup.db.github import domain_repository as github_entities
from catchup.db.github.installation_repository import get_installation_by_installation_id
from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.common.protocols import FullSyncTargetResolverProtocol
from catchup.sync.common.schemas import (
    FullSyncResolvedTargets,
    FullSyncDispatchRequest,
)
from catchup.sync.full.targets import (
    resolve_full_sync_targets_from_rows,
)

logger = structlog.get_logger(__name__)


class GithubFullSyncTargetResolver(FullSyncTargetResolverProtocol):
    def _load_installation_sync(self, installation_id: int):
        with SessionLocal() as db:
            return get_installation_by_installation_id(db, installation_id)

    def _load_repositories_sync(self, installation_id: int):
        with SessionLocal() as db:
            return github_entities.get_repositories_by_installation(db, installation_id)

    async def resolve_full_sync_targets(
        self,
        *,
        request: FullSyncDispatchRequest,
    ) -> FullSyncResolvedTargets:
        scope_id = request.scope_id.strip()
        if not scope_id:
            raise SyncRequestException("scope_id is required")

        try:
            installation_id = int(scope_id)
        except ValueError as exc:
            raise SyncRequestException(
                "scope_id must be a github installation_id",
                metadata={"scope_id": request.scope_id},
            ) from exc

        installation, repositories = await asyncio.gather(
            run_in_threadpool(self._load_installation_sync, installation_id),
            run_in_threadpool(self._load_repositories_sync, installation_id),
        )
        if installation is None:
            raise SyncRequestException(
                "github installation not found",
                metadata={"installation_id": installation_id},
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
            "github_full_sync_targets_resolved",
            installation_id=installation_id,
            requested_count=len(requested_repo_ids),
            resolved_count=len(resolved_targets.targets),
        )

        return resolved_targets


_github_full_sync_target_resolver = GithubFullSyncTargetResolver()


def get_github_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _github_full_sync_target_resolver
