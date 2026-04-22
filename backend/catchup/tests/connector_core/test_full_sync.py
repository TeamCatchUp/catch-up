from __future__ import annotations

from datetime import datetime
from datetime import timezone
from importlib.util import module_from_spec
from importlib.util import spec_from_file_location
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest import TestCase

from pydantic import ValidationError

from catchup.connector_core.application.full_sync import ConnectorFullSyncApplication
from catchup.connector_core.descriptors.channel_talk import CHANNEL_TALK_DESCRIPTOR
from catchup.connector_core.domain.structure import ConnectorKey
from catchup.connector_core.ports.full_sync import FullSyncWindow

_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "connector_core"
    / "adapters"
    / "channel_talk"
    / "full_sync_adapter.py"
)
_SPEC = spec_from_file_location(
    "catchup.tests.connector_core._channel_talk_full_sync_adapter",
    _MODULE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

ChannelTalkFullSyncAdapter = _MODULE.ChannelTalkFullSyncAdapter
ChannelTalkFullSyncExecutionRequest = _MODULE.ChannelTalkFullSyncExecutionRequest
ChannelTalkFullSyncExecutionResult = _MODULE.ChannelTalkFullSyncExecutionResult
ChannelTalkFullSyncFetchResult = _MODULE.ChannelTalkFullSyncFetchResult
ChannelTalkFullSyncTransformResult = _MODULE.ChannelTalkFullSyncTransformResult
ChannelTalkFullSyncSummaryResult = _MODULE.ChannelTalkFullSyncSummaryResult
ChannelTalkFullSyncPersistResult = _MODULE.ChannelTalkFullSyncPersistResult
ChannelTalkFullSyncCheckpoint = _MODULE.ChannelTalkFullSyncCheckpoint
ChannelTalkUserChatState = _MODULE.ChannelTalkUserChatState

ChannelTalkFullSyncCheckpoint.model_rebuild(_types_namespace=_MODULE.__dict__)
ChannelTalkFullSyncFetchResult.model_rebuild(_types_namespace=_MODULE.__dict__)
ChannelTalkFullSyncTransformResult.model_rebuild(_types_namespace=_MODULE.__dict__)
ChannelTalkFullSyncSummaryResult.model_rebuild(_types_namespace=_MODULE.__dict__)
ChannelTalkFullSyncPersistResult.model_rebuild(_types_namespace=_MODULE.__dict__)
ChannelTalkFullSyncExecutionRequest.model_rebuild(_types_namespace=_MODULE.__dict__)
ChannelTalkFullSyncExecutionResult.model_rebuild(_types_namespace=_MODULE.__dict__)


def _window() -> FullSyncWindow:
    return FullSyncWindow(
        window_start=datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc),
        window_end=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
    )


class ChannelTalkFullSyncContractTests(TestCase):
    def test_execution_request_exposes_explicit_channel_talk_user_chat_contract(
        self,
    ) -> None:
        execution = ChannelTalkFullSyncExecutionRequest(
            tenant_id="channel-123",
        )

        self.assertEqual(execution.connector, ConnectorKey.CHANNEL_TALK)
        self.assertEqual(execution.channel_id, "channel-123")
        self.assertEqual(execution.target, "user_chat")
        self.assertNotIn("stage", execution.model_dump())
        self.assertNotIn("states", execution.model_dump())
        self.assertNotIn("window", execution.model_dump())

    def test_execution_request_rejects_blank_tenant_id(self) -> None:
        with self.assertRaisesRegex(ValidationError, "tenant_id is required"):
            ChannelTalkFullSyncExecutionRequest(
                tenant_id=" ",
            )

    def test_window_rejects_inverted_bounds(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            "window_start must be less than or equal to window_end",
        ):
            FullSyncWindow(
                window_start=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
                window_end=datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc),
            )

    def test_execution_request_keeps_only_tenant_checkpoint_alignment(self) -> None:
        with self.assertRaisesRegex(ValidationError, "checkpoint.tenant_id"):
            ChannelTalkFullSyncExecutionRequest(
                tenant_id="channel-123",
                checkpoint=ChannelTalkFullSyncCheckpoint(
                    tenant_id="other-channel",
                    state=ChannelTalkUserChatState.OPENED,
                    window=_window(),
                ),
            )

    def test_checkpoint_remains_target_scoped_without_redundant_stage(self) -> None:
        checkpoint = ChannelTalkFullSyncCheckpoint(
            tenant_id="channel-123",
            state=ChannelTalkUserChatState.OPENED,
            window=_window(),
            next_cursor="cursor-1",
        )

        self.assertEqual(checkpoint.target, "user_chat")
        self.assertNotIn("stage", checkpoint.model_dump())

    def test_descriptor_enables_runtime_full_sync_for_user_chat_contract(self) -> None:
        descriptor = CHANNEL_TALK_DESCRIPTOR

        self.assertTrue(descriptor.runtime.supports_full_sync)
        self.assertEqual(descriptor.runtime.targets[0], "user_chat")


class ConnectorFullSyncApplicationTests(IsolatedAsyncioTestCase):
    async def test_application_runs_fetch_transform_summarize_persist_flow_with_explicit_types(
        self,
    ) -> None:
        application = ConnectorFullSyncApplication(port=ChannelTalkFullSyncAdapter())
        sync_window = FullSyncWindow(
            window_start=datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc),
            window_end=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
        )

        result = await application.run_full_sync(
            execution=ChannelTalkFullSyncExecutionRequest(
                tenant_id="channel-123",
            ),
            sync_window=sync_window,
        )

        self.assertIsInstance(result, ChannelTalkFullSyncExecutionResult)
        self.assertIsInstance(result.fetched, ChannelTalkFullSyncFetchResult)
        self.assertIsInstance(
            result.transformed,
            ChannelTalkFullSyncTransformResult,
        )
        self.assertIsInstance(result.summary, ChannelTalkFullSyncSummaryResult)
        self.assertIsInstance(result.persisted, ChannelTalkFullSyncPersistResult)
        self.assertEqual(result.connector, ConnectorKey.CHANNEL_TALK)
        self.assertEqual(result.channel_id, "channel-123")
        self.assertNotIn("stage", result.model_dump())
        self.assertNotIn("stage", result.fetched.model_dump())
        self.assertEqual(
            result.fetched.states,
            (
                ChannelTalkUserChatState.OPENED,
                ChannelTalkUserChatState.CLOSED,
                ChannelTalkUserChatState.SNOOZED,
            ),
        )
        self.assertEqual(result.fetched.states[0], ChannelTalkUserChatState.OPENED)
        self.assertEqual(result.collected_count, 0)
        self.assertEqual(result.document_count, 0)
        self.assertIn("fetched_record_ids", result.fetched.model_dump())
        self.assertNotIn("fetched_user_chat_ids", result.fetched.model_dump())
        self.assertFalse(result.summary.summary_applied)
        self.assertEqual(result.persisted.persisted_count, 0)
        self.assertEqual(result.fetched.sync_window, sync_window)

    async def test_application_rejects_checkpoint_window_mismatch_during_fetch(self) -> None:
        application = ConnectorFullSyncApplication(port=ChannelTalkFullSyncAdapter())
        execution = ChannelTalkFullSyncExecutionRequest(
            tenant_id="channel-123",
            checkpoint=ChannelTalkFullSyncCheckpoint(
                tenant_id="channel-123",
                state=ChannelTalkUserChatState.OPENED,
                window=_window(),
                next_cursor="cursor-1",
            ),
        )
        mismatched_window = FullSyncWindow(
            window_start=datetime(2026, 4, 20, 0, 0, tzinfo=timezone.utc),
            window_end=datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc),
        )

        with self.assertRaisesRegex(
            ValueError,
            "checkpoint.window must match sync_window",
        ):
            await application.run_full_sync(
                execution=execution,
                sync_window=mismatched_window,
            )

    async def test_application_resolves_fetch_states_inside_adapter(self) -> None:
        application = ConnectorFullSyncApplication(port=ChannelTalkFullSyncAdapter())

        result = await application.run_full_sync(
            execution=ChannelTalkFullSyncExecutionRequest(
                tenant_id="channel-123",
                checkpoint=ChannelTalkFullSyncCheckpoint(
                    tenant_id="channel-123",
                    state=ChannelTalkUserChatState.CLOSED,
                    window=_window(),
                    next_cursor="cursor-1",
                ),
            ),
            sync_window=_window(),
        )

        self.assertEqual(
            result.fetched.states,
            (
                ChannelTalkUserChatState.OPENED,
                ChannelTalkUserChatState.CLOSED,
                ChannelTalkUserChatState.SNOOZED,
            ),
        )
        self.assertEqual(result.fetched.next_checkpoint.state, ChannelTalkUserChatState.CLOSED)
