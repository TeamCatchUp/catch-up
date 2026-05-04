from __future__ import annotations

from functools import lru_cache
from uuid import uuid4

import structlog

from catchup.configs.config import settings
from catchup.db.models import SyncConnector
from catchup.db.models import SyncType
from catchup.sync.common.exceptions import SyncInternalException
from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.common.protocols import EventPublisherProtocol
from catchup.sync.common.schemas import FullSyncDispatchRequest
from catchup.sync.common.schemas import FullSyncTarget
from catchup.sync.common.schemas import SyncDispatchResult
from catchup.sync.common.schemas import SyncEventSeed
from catchup.sync.dispatch.service import DispatchService
from catchup.sync.dispatch.types import DispatchRequest
from catchup.sync.event_publisher.redis_stream_publisher import get_event_publisher
from catchup.sync.full.registry import get_full_sync_target_resolver

logger = structlog.get_logger(__name__)


def _build_event_seed(
    target: FullSyncTarget,
    *,
    sync_from_ts: str | None,
) -> SyncEventSeed:
    # resolver가 확정한 FullSyncTarget을 dispatch/event 계층의 최소 payload로 바꾼다.
    # worker는 이 event의 target_type으로 Channel Talk channel/space 실행을 구분한다.
    return SyncEventSeed(
        event_id=uuid4().hex,
        target_type=target.target_type,
        target_id=target.target_id,
        target_name=target.target_name,
        sync_from_ts=sync_from_ts,
        metadata=dict(target.metadata),
        max_attempts=settings.SYNC_JOB_MAX_ATTEMPTS,
    )


class FullSyncService:
    def __init__(self, dispatch_service: DispatchService):
        self._dispatch_service = dispatch_service

    def _normalize_scope_id(self, request: FullSyncDispatchRequest) -> str:
        scope_id = request.scope_id.strip()
        if scope_id:
            return scope_id
        raise SyncRequestException("scope_id is required")

    def _build_dispatch_request(
        self,
        *,
        connector: SyncConnector,
        request: FullSyncDispatchRequest,
        event_seeds: list[SyncEventSeed],
        scope_id: str,
    ) -> DispatchRequest:
        # DispatchService는 connector/scope/job 단위로 event_seeds를 저장하고 queue에 publish한다.
        return DispatchRequest(
            connector=connector,
            sync_type=SyncType.FULL,
            scope_id=scope_id,
            trigger=request.trigger,
            event_seeds=event_seeds,
        )

    async def dispatch(
        self,
        *,
        connector: SyncConnector,
        request: FullSyncDispatchRequest,
    ) -> SyncDispatchResult:
        logger.info(
            "full_sync_dispatch_requested",
            connector=connector.value,
            scope_id=request.scope_id,
            target_count=len(request.targets) if request.targets else 0,
            sync_from_ts=request.sync_from_ts,
            trigger=request.trigger.value,
        )

        scope_id = self._normalize_scope_id(request)
        resolver = get_full_sync_target_resolver(connector)
        sync_from_ts = request.sync_from_ts
        # connector resolver가 요청 targets를 실제 동기화 가능한 FullSyncTarget으로 확정한다.
        resolved = await resolver.resolve_full_sync_targets(request=request)
        event_seeds = [
            _build_event_seed(target, sync_from_ts=sync_from_ts)
            for target in resolved.targets
        ]
        return await self._dispatch_service.dispatch(
            self._build_dispatch_request(
                connector=connector,
                request=request,
                event_seeds=event_seeds,
                scope_id=scope_id,
            )
        )


def create_full_sync_service(
    *,
    publisher: EventPublisherProtocol | None = None,
    dispatch_service: DispatchService | None = None,
) -> FullSyncService:
    resolved_dispatch_service = dispatch_service
    if resolved_dispatch_service is None:
        resolved_dispatch_service = DispatchService(
            event_publisher=publisher or get_event_publisher(),
        )

    return FullSyncService(dispatch_service=resolved_dispatch_service)


@lru_cache(maxsize=1)
def get_full_sync_service() -> FullSyncService:
    try:
        return create_full_sync_service()
    except SyncInternalException:
        raise
    except Exception as exc:
        logger.error(
            "full_sync_service_init_failed",
            error=str(exc),
            exc_info=True,
        )
        raise SyncInternalException(
            message="full sync service initialization failed",
            metadata={
                "error_message": str(exc),
            },
        ) from exc
