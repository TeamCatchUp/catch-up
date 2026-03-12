from __future__ import annotations

from functools import lru_cache
import logging

from sqlalchemy.orm import Session

from catchup.db.models import SyncConnector
from catchup.sync.common.exceptions import SyncInternalError
from catchup.sync.common.protocols import EventPublisherProtocol
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
            "[SYNC][FULL SYNC][DISPATCH] Dispatching request: connector=%s, scope_id=%s, target_count=%s, sync_from_ts=%s, trigger=%s",
            connector,
            request.scope_id,
            len(request.target_ids) if request.target_ids else 0,
            request.sync_from_ts,
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


def create_sync_dispatch_service(
    *,
    publisher: EventPublisherProtocol | None = None,
    orchestrator: FullSyncDispatchOrchestrator | None = None,
) -> SyncDispatchService:
    resolved_orchestrator = orchestrator
    if resolved_orchestrator is None:
        resolved_orchestrator = FullSyncDispatchOrchestrator(
            orchestrator=SyncDispatchOrchestrator(
                event_publisher=publisher or get_event_publisher(),
            )
        )

    return SyncDispatchService(orchestrator=resolved_orchestrator)


@lru_cache(maxsize=1)
def get_sync_dispatch_service() -> SyncDispatchService:
    try:
        return create_sync_dispatch_service()
    except SyncInternalError:
        raise
    except Exception as exc:
        logger.error(
            "[SYNC][DISPATCH][SERVICE] Initialization failed: error=%s",
            exc,
            exc_info=True,
        )
        raise SyncInternalError(
            message="sync dispatch service initialization failed",
            metadata={
                "error_message": str(exc),
            },
        ) from exc
