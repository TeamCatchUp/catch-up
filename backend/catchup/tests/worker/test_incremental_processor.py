from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import patch

from catchup.db.models import SyncConnector
from catchup.sync.common.schemas import ClaimState
from catchup.sync.common.schemas import IncrementalSyncContext
from catchup.sync.common.schemas import SyncEventKind
from catchup.sync.common.schemas import SyncStreamMessage
from catchup.sync.common.schemas import SyncStreamTask
from catchup.sync.common.schemas import SyncTargetType
from catchup.sync.common.schemas import TargetSyncResult
from catchup.worker.incremental_processor import process_incremental_message
from catchup.worker.schemas import ClaimResult

_PROCESSOR_MODULE = "catchup.worker.incremental_processor"


async def _run_immediately(func, *args, **kwargs):
    return func(*args, **kwargs)


def _context() -> IncrementalSyncContext:
    return IncrementalSyncContext(
        event_id="event-123",
        job_id="job-123",
        connector=SyncConnector.JIRA,
        scope_id="cloud-123",
        target_type=SyncTargetType.PROJECT,
        target_id="GRT",
        target_name="GRT",
        attempt=0,
        max_attempts=3,
        record_key="jira:cloud-123:project:GRT:issue:GRT-1",
        generation=1,
        record_type="issue",
        record_id="GRT-1",
        parent_type=SyncTargetType.PROJECT,
        parent_id="GRT",
        event_kind=SyncEventKind.UPDATED,
        last_event_at="2026-05-08T05:00:00+00:00",
    )


def _message(context: IncrementalSyncContext | None = None) -> SyncStreamMessage:
    context = context or _context()
    return SyncStreamMessage(
        message_id="message-123",
        task=SyncStreamTask.incremental(
            event_id=context.event_id,
            job_id=context.job_id,
            connector=context.connector,
            scope_id=context.scope_id,
            target_type=context.target_type,
            target_id=context.target_id,
            record_key=context.record_key,
            generation=context.generation,
            record_type=context.record_type,
            record_id=context.record_id,
            parent_type=context.parent_type,
            parent_id=context.parent_id,
            event_kind=context.event_kind,
            last_event_at=context.last_event_at,
            attempt=context.attempt,
            max_attempts=context.max_attempts,
        ),
    )


class IncrementalProcessorStartedHookTest(IsolatedAsyncioTestCase):
    async def test_invokes_start_hook_once_before_handle(self) -> None:
        context = _context()
        call_order: list[str] = []

        async def on_target_started(*, context):
            call_order.append("hook_started")

        async def handle(*, context, service_cache):
            call_order.append("handle")
            return TargetSyncResult(synced_count=1, error_count=0, skipped=False)

        async def on_target_completed(*, context, result):
            call_order.append("hook_completed")

        handler = SimpleNamespace(
            on_target_started=AsyncMock(side_effect=on_target_started),
            handle=AsyncMock(side_effect=handle),
            on_target_completed=AsyncMock(side_effect=on_target_completed),
        )

        with (
            patch(f"{_PROCESSOR_MODULE}.run_in_threadpool", _run_immediately),
            patch(
                f"{_PROCESSOR_MODULE}._claim_incremental_task",
                return_value=ClaimResult(state=ClaimState.CLAIMED, context=context),
            ),
            patch(f"{_PROCESSOR_MODULE}.select_handler", return_value=handler),
            patch(
                f"{_PROCESSOR_MODULE}._mark_incremental_success_sync", return_value=True
            ),
        ):
            await process_incremental_message(
                _message(context),
                service_cache={},
                lease_owner="worker-1",
            )

        self.assertEqual(handler.on_target_started.await_count, 1)
        self.assertEqual(handler.handle.await_count, 1)
        self.assertLess(call_order.index("hook_started"), call_order.index("handle"))

    async def test_does_not_start_unclaimed_or_unsupported_tasks(
        self,
    ) -> None:
        message = _message()

        for state in (ClaimState.INVALID_INCREMENTAL_TASK, ClaimState.STALE_TASK):
            with self.subTest(state=state):
                with (
                    patch(f"{_PROCESSOR_MODULE}.run_in_threadpool", _run_immediately),
                    patch(
                        f"{_PROCESSOR_MODULE}._claim_incremental_task",
                        return_value=ClaimResult(state=state),
                    ),
                    patch(f"{_PROCESSOR_MODULE}.select_handler") as select_handler,
                    patch(f"{_PROCESSOR_MODULE}.deadletter", AsyncMock()),
                ):
                    await process_incremental_message(
                        message,
                        service_cache={},
                        lease_owner="worker-1",
                    )

                select_handler.assert_not_called()

        context = _context()
        with (
            patch(f"{_PROCESSOR_MODULE}.run_in_threadpool", _run_immediately),
            patch(
                f"{_PROCESSOR_MODULE}._claim_incremental_task",
                return_value=ClaimResult(state=ClaimState.CLAIMED, context=context),
            ),
            patch(f"{_PROCESSOR_MODULE}.select_handler", return_value=None),
            patch(f"{_PROCESSOR_MODULE}.deadletter", AsyncMock()),
        ):
            await process_incremental_message(
                _message(context),
                service_cache={},
                lease_owner="worker-1",
            )
