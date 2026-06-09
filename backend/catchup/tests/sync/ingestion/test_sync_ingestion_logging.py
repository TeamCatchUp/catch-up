from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from catchup.db.models import SyncConnector
from catchup.sync.audit import SyncAuditContext
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.sync.ingestion.schemas import SyncExecutionRequest
from catchup.sync.ingestion.schemas import SyncExecutionResult
from catchup.sync.ingestion.schemas import SyncWindow


def _window() -> SyncWindow:
    return SyncWindow(
        window_start=datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc),
        window_end=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
    )


class _LoggedExecutionRequest(SyncExecutionRequest):
    audit_context: SyncAuditContext | None = None


class _PagedExecutionRequest(_LoggedExecutionRequest):
    def log_context(self) -> dict[str, object]:
        return {
            "batch_index": 0,
            "next_page_token_present": False,
        }


class _ConnectorLogSummaryStageResult(SimpleNamespace):
    def connector_log_summary(self) -> dict[str, object]:
        return {
            "batch_index": 3,
            "next_page_token_present": False,
            "raw_payload": object(),
        }


class _Port:
    async def fetch(self, *, execution, sync_window):
        return _ConnectorLogSummaryStageResult(
            bundles=("bundle-1", "bundle-2"),
            fetched_count=2,
            fetched_record_ids=("record-1", "record-2"),
        )

    async def transform(self, *, execution, sync_window, fetched):
        return SimpleNamespace(
            documents=("document-1", "document-2"),
            prepared_document_ids=("document-1", "document-2"),
        )

    async def summarize(self, *, execution, sync_window, transformed):
        return SimpleNamespace(
            summary_applied=True,
            document_count=len(transformed.documents),
        )

    async def persist(self, *, execution, sync_window, transformed, summary):
        return SimpleNamespace(
            persisted_count=len(transformed.documents),
            persisted_ids=("document-1", "document-2"),
        )

    def build_result(
        self,
        *,
        execution,
        sync_window,
        fetched,
        transformed,
        summary,
        persisted,
    ):
        return SyncExecutionResult(
            connector=SyncConnector.CHANNEL_TALK,
            tenant_id=execution.tenant_id,
            target=execution.target,
        )


class _FailingTransformPort(_Port):
    async def transform(self, *, execution, sync_window, fetched):
        raise RuntimeError("transform failed")


class SyncIngestionLoggingTest(IsolatedAsyncioTestCase):
    async def test_logs_shared_pipeline_stage_completion(self) -> None:
        execution = _LoggedExecutionRequest(
            connector=SyncConnector.CHANNEL_TALK,
            tenant_id="channel-123",
            target="user_chat",
            audit_context=SyncAuditContext(
                connector=SyncConnector.CHANNEL_TALK,
                scope_id="channel-123",
                target_id="user_chat",
                job_id="job-123",
                task_id="event-123",
            ),
        )

        with patch(
            "catchup.sync.ingestion.logging.logger"
        ) as logger:
            result = await run_sync_ingestion(
                port=_Port(),
                execution=execution,
                sync_window=_window(),
            )

        self.assertEqual(result.tenant_id, "channel-123")

        events = [call.args[0] for call in logger.info.call_args_list]
        self.assertEqual(events[0], "sync_ingestion_pipeline_started")
        self.assertIn("sync_ingestion_pipeline_completed", events)

        stage_calls = [
            call
            for call in logger.debug.call_args_list
            if call.args[0] == "sync_ingestion_stage_completed"
        ]
        self.assertEqual(
            [call.kwargs["stage"] for call in stage_calls],
            ["fetch", "transform", "summarize", "persist", "build_result"],
        )
        self.assertNotIn(
            "sync_ingestion_stage_completed",
            events,
        )

        start_context = logger.info.call_args_list[0].kwargs
        self.assertEqual(start_context["connector_type"], "channel_talk")
        self.assertNotIn("connector", start_context)
        self.assertEqual(start_context["tenant_id"], "channel-123")
        self.assertEqual(start_context["target"], "user_chat")
        self.assertEqual(start_context["scope_id"], "channel-123")
        self.assertEqual(start_context["target_id"], "user_chat")
        self.assertEqual(start_context["job_id"], "job-123")
        self.assertEqual(start_context["task_id"], "event-123")
        self.assertEqual(
            start_context["sync_window_start"],
            "2026-04-21T00:00:00+00:00",
        )
        self.assertEqual(
            start_context["sync_window_end"],
            "2026-04-22T00:00:00+00:00",
        )

        fetch_context = stage_calls[0].kwargs
        self.assertEqual(fetch_context["fetched_count"], 2)
        self.assertEqual(fetch_context["batch_index"], 3)
        self.assertFalse(fetch_context["next_page_token_present"])
        self.assertNotIn("raw_payload", fetch_context)
        self.assertEqual(fetch_context["bundles_count"], 2)
        self.assertEqual(fetch_context["fetched_record_ids_count"], 2)

        persist_context = stage_calls[3].kwargs
        self.assertEqual(persist_context["persisted_count"], 2)
        self.assertEqual(persist_context["persisted_ids_count"], 2)
        self.assertIsInstance(persist_context["duration_ms"], int)

    async def test_logs_pipeline_failure_with_failed_stage(self) -> None:
        execution = SyncExecutionRequest(
            connector=SyncConnector.CHANNEL_TALK,
            tenant_id="channel-123",
            target="user_chat",
        )

        with patch(
            "catchup.sync.ingestion.logging.logger"
        ) as logger:
            with self.assertRaisesRegex(RuntimeError, "transform failed"):
                await run_sync_ingestion(
                    port=_FailingTransformPort(),
                    execution=execution,
                    sync_window=_window(),
                )

        logger.warning.assert_called_once()
        failure_call = logger.warning.call_args
        self.assertEqual(failure_call.args[0], "sync_ingestion_pipeline_failed")
        self.assertEqual(failure_call.kwargs["stage"], "transform")
        self.assertEqual(failure_call.kwargs["error_type"], "RuntimeError")
        self.assertEqual(failure_call.kwargs["error_message"], "transform failed")
        self.assertTrue(failure_call.kwargs["exc_info"])

    async def test_stage_summary_does_not_duplicate_pipeline_context_keys(self) -> None:
        execution = _PagedExecutionRequest(
            connector=SyncConnector.JIRA,
            tenant_id="cloud-123",
            target="issue",
        )

        with patch(
            "catchup.sync.ingestion.logging.logger"
        ) as logger:
            await run_sync_ingestion(
                port=_Port(),
                execution=execution,
                sync_window=_window(),
            )

        fetch_call = next(
            call
            for call in logger.debug.call_args_list
            if call.args[0] == "sync_ingestion_stage_completed"
            and call.kwargs["stage"] == "fetch"
        )
        self.assertEqual(fetch_call.kwargs["batch_index"], 0)
        self.assertFalse(fetch_call.kwargs["next_page_token_present"])
