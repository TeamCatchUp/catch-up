from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from fastapi.concurrency import run_in_threadpool

from catchup.db.engine import SessionLocal
from catchup.db.models import SyncConnector
from catchup.db.models import SyncEventStatus
from catchup.db.sync import finalize_manual_retry_failed
from catchup.db.sync import finalize_manual_retry_success
from catchup.server.sync.schemas import (
    SyncRecordGapResponse,
    SyncRecordRetryRequest,
    SyncRecordRetryResponse,
)
from catchup.sync.common.exceptions import SyncInternalError
from catchup.sync.common.exceptions import SyncRequestError
from catchup.sync.repair.context import RecordRepairContext
from catchup.sync.repair.context import load_record_repair_context
from catchup.sync.repair.github_record_repair_service import (
    get_github_record_repair_service,
)
from catchup.sync.repair.confluence_record_repair_service import (
    get_confluence_record_repair_service,
)
from catchup.sync.repair.jira_record_repair_service import (
    get_jira_record_repair_service,
)
from catchup.sync.repair.slack_record_repair_service import (
    get_slack_record_repair_service,
)


class RecordRepairHandler(Protocol):
    async def get_record_gaps(
        self,
        *,
        repair_context: RecordRepairContext,
    ) -> SyncRecordGapResponse: ...

    async def retry_records(
        self,
        *,
        request: SyncRecordRetryRequest,
        repair_context: RecordRepairContext,
    ) -> SyncRecordRetryResponse: ...


class RecordRepairService:
    def __init__(
        self,
        *,
        confluence_handler: RecordRepairHandler,
        github_handler: RecordRepairHandler,
        jira_handler: RecordRepairHandler,
        slack_handler: RecordRepairHandler,
    ):
        self._confluence_handler = confluence_handler
        self._github_handler = github_handler
        self._jira_handler = jira_handler
        self._slack_handler = slack_handler

    def _resolve_handler(
        self,
        connector: SyncConnector,
    ) -> RecordRepairHandler:
        if connector == SyncConnector.CONFLUENCE:
            return self._confluence_handler
        if connector == SyncConnector.GITHUB:
            return self._github_handler
        if connector == SyncConnector.JIRA:
            return self._jira_handler
        if connector == SyncConnector.SLACK:
            return self._slack_handler

        raise SyncRequestError(
            "record repair not supported for this connector",
            code="unsupported_connector",
            metadata={"connector": connector.value},
        )

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
                    raise SyncInternalError(
                        "failed to update retry event status",
                        code="event_status_update_failed",
                        metadata={"event_id": repair_context.event_id},
                    )

            return next_status

        return await run_in_threadpool(_update_status)

    async def get_record_gaps(
        self,
        *,
        event_id: str,
    ) -> SyncRecordGapResponse:
        repair_context = await self._load_repair_context(event_id=event_id)
        handler = self._resolve_handler(repair_context.connector)
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
        handler = self._resolve_handler(repair_context.connector)
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
        confluence_handler=get_confluence_record_repair_service(),
        github_handler=get_github_record_repair_service(),
        jira_handler=get_jira_record_repair_service(),
        slack_handler=get_slack_record_repair_service(),
    )
