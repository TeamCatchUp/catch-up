from __future__ import annotations

from uuid import uuid4

from catchup.configs.config import settings
from catchup.db.models import SyncConnector, SyncType
from catchup.sync.common.exceptions import SyncRequestError
from catchup.sync.common.protocols import FullSyncTargetResolverProtocol
from catchup.sync.common.schemas import (
    FullSyncDispatchRequest,
    FullSyncTarget,
    SyncDispatchResult,
    SyncEventSeed,
)
from catchup.sync.services.sync_orchestrator import SyncDispatchOrchestrator


def _build_event_seed(
    target: FullSyncTarget,
    *,
    sync_from_ts: str | None,
) -> SyncEventSeed:
    return SyncEventSeed(
        event_id=uuid4().hex,
        target_type=target.target_type,
        target_id=target.target_id,
        target_name=target.target_name,
        sync_from_ts=sync_from_ts,
        metadata=dict(target.metadata),
        max_attempts=settings.SYNC_JOB_MAX_ATTEMPTS,
    )


class FullSyncDispatchOrchestrator:
    """Full Sync 전용 입력 해석 후 공통 dispatch orchestrator에 위임한다."""

    def __init__(self, orchestrator: SyncDispatchOrchestrator):
        self._orchestrator = orchestrator

    async def dispatch(
        self,
        *,
        connector: SyncConnector,
        request: FullSyncDispatchRequest,
        base_url: str | None,
        resolver: FullSyncTargetResolverProtocol,
    ) -> SyncDispatchResult:
        scope_id = request.scope_id.strip()
        if not scope_id:
            raise SyncRequestError("scope_id is required")

        sync_from_ts = request.sync_from_ts

        resolved = await resolver.resolve_full_sync_targets(request=request)

        event_seeds = [
            _build_event_seed(target, sync_from_ts=sync_from_ts)
            for target in resolved.targets
        ]

        return await self._orchestrator.dispatch(
            connector=connector,
            sync_type=SyncType.FULL,
            scope_id=scope_id,
            trigger=request.trigger,
            event_seeds=event_seeds,
            base_url=base_url,
            sync_from_ts=sync_from_ts,
        )
