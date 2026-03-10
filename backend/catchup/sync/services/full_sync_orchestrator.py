from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from catchup.configs.config import settings
from catchup.db.models import SyncConnector, SyncType
from catchup.sync.common.protocols import FullSyncTargetResolverProtocol
from catchup.sync.common.schemas import (
    FullSyncDispatchRequest,
    SyncDispatchResult,
    SyncEventSeed,
)
from catchup.sync.services.sync_orchestrator import SyncDispatchOrchestrator


class FullSyncDispatchOrchestrator:
    """Full Sync 전용 입력 해석 후 공통 dispatch orchestrator에 위임한다."""

    def __init__(self, orchestrator: SyncDispatchOrchestrator):
        self._orchestrator = orchestrator

    async def dispatch(
        self,
        *,
        db: Session,
        connector: SyncConnector,
        request: FullSyncDispatchRequest,
        base_url: str | None,
        resolver: FullSyncTargetResolverProtocol,
    ) -> SyncDispatchResult:
        scope_id = request.scope_id.strip()
        if not scope_id:
            raise ValueError("scope_id is required")

        sync_days = max(1, int(request.sync_days or settings.DEFAULT_SYNC_DAYS))
        sync_from = str(
            (
                datetime.now(timezone.utc) - timedelta(days=sync_days)
            ).timestamp()
        )

        resolved = await resolver.resolve_full_sync_targets(
            db=db,
            request=request,
            sync_from=sync_from,
        )

        event_seeds: list[SyncEventSeed] = []
        for target in resolved.targets:
            normalized_target_id = target.target_id.strip()
            if not normalized_target_id:
                continue

            normalized_target_type = target.target_type.strip() or "resource"
            normalized_target_name = target.target_name.strip() or normalized_target_id

            event_seeds.append(
                SyncEventSeed(
                    event_id=uuid4().hex,
                    target_type=normalized_target_type,
                    target_id=normalized_target_id,
                    target_name=normalized_target_name,
                    sync_from=sync_from,
                    metadata=dict(target.metadata),
                    max_attempts=settings.SYNC_JOB_MAX_ATTEMPTS,
                )
            )

        return await self._orchestrator.dispatch(
            db=db,
            connector=connector,
            sync_type=SyncType.FULL,
            scope_id=scope_id,
            trigger=request.trigger,
            event_seeds=event_seeds,
            base_url=base_url,
            sync_from=sync_from,
        )
