from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from catchup.db.models import SyncConnector
from catchup.db.models import SyncEventStatus
from catchup.db.sync.admin_connector_status import AdminConnectorTargetRangeRow
from catchup.db.sync.admin_connector_status import _get_target_identity_key
from catchup.db.sync.admin_connector_status import _get_target_range_key
from catchup.db.sync.admin_connector_status import _merge_targets
from catchup.db.sync.admin_connector_status import _SyncTargetRow
from catchup.server.admin.api import _get_connector_status
from catchup.server.admin.schemas import ConnectorStatusSource


class AdminConnectorStatusApiTests(TestCase):
    def test_channel_talk_status_includes_target_type(self) -> None:
        succeeded_at = datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc)
        oldest_at = datetime(2025, 11, 3, tzinfo=timezone.utc)
        latest_at = datetime(2026, 5, 1, tzinfo=timezone.utc)

        db = SimpleNamespace()
        with patch(
            "catchup.server.admin.api.list_admin_connector_target_range_rows",
            return_value=[
                AdminConnectorTargetRangeRow(
                    target_type="channel",
                    scope_id="channel-123",
                    target_id="channel-123",
                    target_name="Support",
                    event_id="event-channel",
                    sync_status=SyncEventStatus.SUCCESS.value,
                    last_succeeded_at=succeeded_at,
                    last_failed_at=None,
                    oldest_at=oldest_at,
                    latest_at=latest_at,
                ),
                AdminConnectorTargetRangeRow(
                    target_type="space",
                    scope_id="channel-123",
                    target_id="space-123",
                    target_name="Help Center",
                    event_id="event-space",
                    sync_status=SyncEventStatus.FAILED.value,
                    last_succeeded_at=None,
                    last_failed_at=succeeded_at,
                    oldest_at=None,
                    latest_at=None,
                ),
            ],
        ) as list_rows:
            response = _get_connector_status(
                db,
                source=ConnectorStatusSource.CHANNEL_TALK,
            )

        list_rows.assert_called_once_with(
            db,
            connector=SyncConnector.CHANNEL_TALK,
        )
        payload = response.model_dump(mode="json")

        self.assertEqual(payload["source"], "channel_talk")
        self.assertEqual(payload["resource_type"], "channel_talk_targets")
        self.assertEqual(payload["total_targets"], 2)
        self.assertEqual(payload["targets"][0]["target_type"], "channel")
        self.assertEqual(payload["targets"][0]["oldest"], "2025-11-03")
        self.assertEqual(payload["targets"][0]["latest"], "2026-05-01")
        self.assertEqual(payload["targets"][1]["target_type"], "space")

    def test_existing_connector_status_omits_target_type(self) -> None:
        db = SimpleNamespace()
        with patch(
            "catchup.server.admin.api.list_admin_connector_target_range_rows",
            return_value=[
                AdminConnectorTargetRangeRow(
                    target_type=None,
                    scope_id="installation-123",
                    target_id="repo-123",
                    target_name="catchup/api",
                    event_id="event-repo",
                    sync_status=SyncEventStatus.PENDING.value,
                    last_succeeded_at=None,
                    last_failed_at=None,
                    oldest_at=None,
                    latest_at=None,
                ),
            ],
        ):
            response = _get_connector_status(
                db,
                source=ConnectorStatusSource.GITHUB,
            )

        payload = response.model_dump(mode="json")

        self.assertEqual(payload["source"], "github")
        self.assertEqual(payload["resource_type"], "repositories")
        self.assertNotIn("target_type", payload["targets"][0])


class AdminConnectorStatusTargetKeyTests(TestCase):
    def test_channel_talk_identity_uses_target_type_to_avoid_id_collision(self) -> None:
        channel_target = _SyncTargetRow(
            target_type="channel",
            scope_id="channel-123",
            target_id="same-id",
            target_name="Support",
            event_id="event-channel",
            sync_status=SyncEventStatus.SUCCESS.value,
            last_succeeded_at=None,
            last_failed_at=None,
        )
        space_target = _SyncTargetRow(
            target_type="space",
            scope_id="channel-123",
            target_id="same-id",
            target_name="Help Center",
            event_id="event-space",
            sync_status=SyncEventStatus.SUCCESS.value,
            last_succeeded_at=None,
            last_failed_at=None,
        )

        merged = _merge_targets(
            [channel_target, space_target],
            [],
            connector=SyncConnector.CHANNEL_TALK,
        )

        self.assertEqual(len(merged), 2)
        self.assertNotEqual(
            _get_target_identity_key(channel_target),
            _get_target_identity_key(space_target),
        )
        self.assertEqual(
            _get_target_range_key(
                SyncConnector.CHANNEL_TALK,
                target_type="channel",
                scope_id="channel-123",
                target_id="same-id",
                target_name="Support",
            ),
            ("channel", "channel-123", "same-id"),
        )
        self.assertEqual(
            _get_target_range_key(
                SyncConnector.CHANNEL_TALK,
                target_type="space",
                scope_id="channel-123",
                target_id="same-id",
                target_name="Help Center",
            ),
            ("space", "channel-123", "same-id"),
        )
