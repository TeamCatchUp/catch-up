from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from catchup.db.models import SyncConnector
from catchup.sync.common.schemas import (
    FullSyncDispatchRequest,
    SyncDispatchResult,
)
from catchup.sync.event_publisher.redis_stream_publisher import get_event_publisher
from catchup.sync.registry import get_full_sync_target_resolver
from catchup.sync.services.full_sync_orchestrator import FullSyncDispatchOrchestrator
from catchup.sync.services.sync_orchestrator import SyncDispatchOrchestrator

logger = logging.getLogger(__name__)

class SyncDispatchService:
    def __init__(self, orchestrator: FullSyncDispatchOrchestrator):
        self._full_sync_orchestrator = orchestrator

    async def dispatch_full_sync(
        self,
        *,
        db: Session,
        connector: SyncConnector,
        request: FullSyncDispatchRequest,
        base_url: str | None,
    ) -> SyncDispatchResult:
        logger.info(
            "[SYNC][FULL SYNC][DISPATCH] Dispatching request: connector=%s, scope_id=%s, target_count=%s, sync_days=%s, trigger=%s",
            connector,
            request.scope_id,
            len(request.target_ids) if request.target_ids else 0,
            request.sync_days,
            request.trigger,
        )

        resolver = get_full_sync_target_resolver(connector)

        return await self._full_sync_orchestrator.dispatch(
            db=db,
            connector=connector,
            request=request,
            base_url=base_url,
            resolver=resolver,
        )

_sync_dispatch_service = SyncDispatchService(
    orchestrator=FullSyncDispatchOrchestrator(
        orchestrator=SyncDispatchOrchestrator(
            event_publisher=get_event_publisher(),
        )
    )
)


def get_sync_dispatch_service() -> SyncDispatchService:
    return _sync_dispatch_service
