from __future__ import annotations

import asyncio

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.db.engine import SessionLocal
from catchup.db.github import domain_repository as github_entities
from catchup.db.github.installation_repository import (
    get_installation_by_installation_id,
)
from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.common.protocols import FullSyncTargetResolverProtocol
from catchup.sync.common.schemas import FullSyncDispatchRequest
from catchup.sync.common.schemas import FullSyncResolvedTargets
from catchup.sync.common.schemas import FullSyncTarget
from catchup.sync.full.targets import resolve_full_sync_targets_from_rows

logger = structlog.get_logger(__name__)

_GITHUB_FULL_SYNC_STREAM_TYPES = ("issue", "pull_request")


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
        # GitHub은 요청은 repository 단위로 받되, worker event는 repository+stream 단위로 쪼갠다.
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

        # listing 때 저장된 repository snapshot과 요청 repo_id를 매칭한다.
        requested_repo_ids, resolved_targets = resolve_full_sync_targets_from_rows(
            request_targets=request.targets,
            rows=repositories,
            target_type="repository",
            key_getter=lambda repo: str(repo.repo_id),
            name_getter=lambda repo: repo.full_name,
            error_message="requested targets contain unknown repositories",
            error_metadata={"installation_id": installation_id},
            log_context={
                "connector": "github",
                "installation_id": installation_id,
                "target_type": "repository",
            },
        )
        stream_targets = [
            FullSyncTarget(
                target_type=target.target_type,
                target_id=target.target_id,
                target_name=f"{target.target_name} / {stream_type}",
                metadata={
                    **target.metadata,
                    "repo_id": target.target_id,
                    "repo_full_name": target.target_name,
                    "stream_type": stream_type,
                    "record_type": stream_type,
                },
            )
            for target in resolved_targets.targets
            for stream_type in _GITHUB_FULL_SYNC_STREAM_TYPES
        ]

        logger.info(
            "github_full_sync_targets_resolved",
            installation_id=installation_id,
            requested_count=len(requested_repo_ids),
            resolved_count=len(stream_targets),
            stream_types=list(_GITHUB_FULL_SYNC_STREAM_TYPES),
        )

        return FullSyncResolvedTargets(targets=stream_targets)


_github_full_sync_target_resolver = GithubFullSyncTargetResolver()


def get_github_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _github_full_sync_target_resolver
