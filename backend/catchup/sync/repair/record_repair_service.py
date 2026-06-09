from __future__ import annotations

from functools import lru_cache

from fastapi.concurrency import run_in_threadpool

from catchup.db.engine import SessionLocal
from catchup.db.models import SyncEventStatus
from catchup.db.sync import finalize_manual_retry_failed
from catchup.db.sync import finalize_manual_retry_success
from catchup.server.sync.schemas import SyncRecordGapResponse
from catchup.server.sync.schemas import SyncRecordRetryRequest
from catchup.server.sync.schemas import SyncRecordRetryResponse
from catchup.sync.common.exceptions import SyncInternalException
from catchup.sync.repair.context import RecordRepairContext
from catchup.sync.repair.context import load_record_repair_context
from catchup.sync.repair.registry import RecordRepairHandlerRegistry
from catchup.sync.repair.registry import get_record_repair_handler_registry


class RecordRepairService:
    def __init__(
        self,
        *,
        registry: RecordRepairHandlerRegistry,
    ) -> None:
        self._registry = registry

    async def _load_repair_context(
        self,
        *,
        event_id: str,
    ) -> RecordRepairContext:
        return await run_in_threadpool(load_record_repair_context, event_id)

    async def _mark_retry_event_status(
        self,
        *,
        repair_context: RecordRepairContext,
        has_retry_failure: bool,
    ) -> SyncEventStatus:
        def _update_status() -> SyncEventStatus:
            with SessionLocal() as db:
                if has_retry_failure:
                    updated = finalize_manual_retry_failed(db, repair_context.event_id)
                    next_status = SyncEventStatus.FAILED
                else:
                    updated = finalize_manual_retry_success(db, repair_context.event_id)
                    next_status = SyncEventStatus.SUCCESS

                if not updated:
                    raise SyncInternalException(
                        "failed to update retry event status",
                        code="event_status_update_failed",
                        metadata={"event_id": repair_context.event_id},
                    )

                db.commit()

            return next_status

        return await run_in_threadpool(_update_status)

    async def get_record_gaps(
        self,
        *,
        event_id: str,
    ) -> SyncRecordGapResponse:
        repair_context = await self._load_repair_context(event_id=event_id)
        handler = self._registry.handler_for(repair_context.connector)
        response = await handler.get_record_gaps(
            repair_context=repair_context,
        )
        return response.model_copy(
            update={
                "event_id": repair_context.event_id,
                "attempt": repair_context.attempt,
                "event_status": repair_context.event_status,
                "target_name": repair_context.target_name,
            }
        )

    async def retry_records(
        self,
        *,
        request: SyncRecordRetryRequest,
    ) -> SyncRecordRetryResponse:
        repair_context = await self._load_repair_context(event_id=request.event_id)
        handler = self._registry.handler_for(repair_context.connector)
        response = await handler.retry_records(
            request=request,
            repair_context=repair_context,
        )
        final_status = await self._mark_retry_event_status(
            repair_context=repair_context,
            has_retry_failure=any(
                bool(item.failed_ids) or bool(item.remaining_missing_ids)
                for item in response.records
            ),
        )
        return response.model_copy(
            update={
                "event_id": repair_context.event_id,
                "event_status": final_status,
                "target_name": repair_context.target_name,
            }
        )


@lru_cache(maxsize=1)
def get_record_repair_service() -> RecordRepairService:
    return RecordRepairService(
        registry=get_record_repair_handler_registry(),
    )
