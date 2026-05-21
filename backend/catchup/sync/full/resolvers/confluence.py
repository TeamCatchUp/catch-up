from __future__ import annotations

import asyncio

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.db.atlassian.oauth_repository import get_token_by_cloud_id
from catchup.db.confluence import domain_repository as confluence_entities
from catchup.db.engine import SessionLocal
from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.common.protocols import FullSyncTargetResolverProtocol
from catchup.sync.common.schemas import FullSyncDispatchRequest
from catchup.sync.common.schemas import FullSyncResolvedTargets
from catchup.sync.common.schemas import FullSyncTarget
from catchup.sync.full.targets import resolve_full_sync_targets_from_rows

logger = structlog.get_logger(__name__)

_CONFLUENCE_FULL_SYNC_CONTENT_TYPES = ("page", "blogpost")


class ConfluenceFullSyncTargetResolver(FullSyncTargetResolverProtocol):
    def _load_token_sync(self, cloud_id: str):
        with SessionLocal() as db:
            return get_token_by_cloud_id(db, cloud_id)

    def _load_spaces_sync(self, cloud_id: str):
        with SessionLocal() as db:
            return confluence_entities.get_spaces_by_cloud_id(db, cloud_id)

    async def resolve_full_sync_targets(
        self,
        *,
        request: FullSyncDispatchRequest,
    ) -> FullSyncResolvedTargets:
        # Confluence는 요청은 space 단위로 받되, worker event는 space+content type 단위로 쪼갠다.
        cloud_id = request.scope_id.strip()
        if not cloud_id:
            raise SyncRequestException("scope_id is required")

        token, spaces = await asyncio.gather(
            run_in_threadpool(self._load_token_sync, cloud_id),
            run_in_threadpool(self._load_spaces_sync, cloud_id),
        )
        if token is None:
            raise SyncRequestException(
                "confluence cloud is not connected",
                metadata={"cloud_id": cloud_id},
            )

        # listing 때 저장된 space snapshot과 요청 space_key를 매칭한다.
        requested_space_keys, resolved_targets = resolve_full_sync_targets_from_rows(
            request_targets=request.targets,
            rows=spaces,
            target_type="space",
            key_getter=lambda space: space.space_key,
            name_getter=lambda space: space.space_name or space.space_key,
            error_message="requested targets contain unknown spaces",
            error_metadata={"cloud_id": cloud_id},
            log_context={
                "connector": "confluence",
                "cloud_id": cloud_id,
                "target_type": "space",
            },
        )
        content_targets = [
            FullSyncTarget(
                target_type=target.target_type,
                target_id=target.target_id,
                target_name=f"{target.target_name} / {content_type}",
                metadata={
                    **target.metadata,
                    "space_key": target.target_id,
                    "space_name": target.target_name,
                    "content_type": content_type,
                    "record_type": content_type,
                },
            )
            for target in resolved_targets.targets
            for content_type in _CONFLUENCE_FULL_SYNC_CONTENT_TYPES
        ]

        logger.info(
            "confluence_full_sync_targets_resolved",
            cloud_id=cloud_id,
            requested_count=len(requested_space_keys),
            resolved_count=len(content_targets),
            content_types=list(_CONFLUENCE_FULL_SYNC_CONTENT_TYPES),
        )

        return FullSyncResolvedTargets(targets=content_targets)


_confluence_full_sync_target_resolver = ConfluenceFullSyncTargetResolver()


def get_confluence_full_sync_target_resolver() -> FullSyncTargetResolverProtocol:
    return _confluence_full_sync_target_resolver
