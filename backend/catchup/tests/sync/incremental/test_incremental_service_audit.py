from __future__ import annotations

from datetime import datetime
from datetime import timezone
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from catchup.audit.actions import SyncTriggerAction
from catchup.audit.base import AuditStatus
from catchup.audit.metadata import IncrementalSyncTriggerMetadata
from catchup.db.models import SyncConnector
from catchup.sync.common.schemas import SyncEventKind
from catchup.sync.common.schemas import SyncTargetType
from catchup.sync.incremental.schemas import IncrementalIngestResult
from catchup.sync.incremental.schemas import RecordChange
from catchup.sync.incremental.service import IncrementalService


async def _run_immediately(func, *args, **kwargs):
    return func(*args, **kwargs)


def _build_change() -> RecordChange:
    return RecordChange(
        connector=SyncConnector.CHANNEL_TALK,
        scope_id="channel-123",
        record_type="user_chat",
        record_id="chat-123",
        parent_type=SyncTargetType.CHANNEL,
        parent_id="channel-123",
        event_kind=SyncEventKind.UPDATED,
        last_event_at=datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc),
    )


class IncrementalServiceAuditTests(IsolatedAsyncioTestCase):
    async def test_dispatch_changes_emits_audit_attempt_and_success(self) -> None:
        service = IncrementalService()
        change = _build_change()

        with (
            patch(
                "catchup.sync.incremental.service.run_in_threadpool",
                _run_immediately,
            ),
            patch(
                "catchup.sync.incremental.service.persist_incremental_changes",
                return_value=IncrementalIngestResult(
                    record_keys=[change.record_key],
                    blocked_count=0,
                    blocked_target_keys=[],
                    first_allowed_change=change,
                ),
            ),
            patch("catchup.audit.utils.emit_audit_event") as emit_audit_event,
        ):
            result = await service.dispatch_changes(changes=[change])

        self.assertEqual(result.record_keys, [change.record_key])
        self.assertEqual(emit_audit_event.call_count, 2)

        attempt = emit_audit_event.call_args_list[0].kwargs
        self.assertEqual(attempt["action"], SyncTriggerAction.INCREMENTAL)
        self.assertEqual(attempt["status"], AuditStatus.ATTEMPT)
        self.assertIsInstance(attempt["metadata"], IncrementalSyncTriggerMetadata)
        self.assertEqual(attempt["metadata"].connector, SyncConnector.CHANNEL_TALK)
        self.assertEqual(attempt["metadata"].scope_id, "channel-123")
        self.assertEqual(attempt["metadata"].target_id, "channel-123")
        self.assertEqual(attempt["metadata"].record_type, "user_chat")
        self.assertEqual(attempt["metadata"].record_ids, ["chat-123"])
        self.assertEqual(attempt["metadata"].change_count, 1)
        self.assertIsNone(attempt["metadata"].record_key_count)
        self.assertIsNone(attempt["metadata"].blocked_count)

        success = emit_audit_event.call_args_list[1].kwargs
        self.assertEqual(success["action"], SyncTriggerAction.INCREMENTAL)
        self.assertEqual(success["status"], AuditStatus.SUCCESS)
        metadata = success["metadata"]
        self.assertIsInstance(metadata, IncrementalSyncTriggerMetadata)
        self.assertEqual(metadata.record_key_count, 1)
        self.assertEqual(metadata.blocked_count, 0)
