from __future__ import annotations

from dataclasses import dataclass
from unittest import TestCase

from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.common.schemas import FullSyncRequestedTarget
from catchup.sync.common.schemas import SyncTargetType
from catchup.sync.full.targets import resolve_full_sync_targets_from_rows


@dataclass(slots=True, frozen=True)
class _TargetRow:
    target_id: str
    target_name: str


def _target(
    target_type: SyncTargetType,
    target_id: str,
) -> FullSyncRequestedTarget:
    return FullSyncRequestedTarget(target_type=target_type, target_id=target_id)


class ResolveFullSyncTargetsFromRowsTests(TestCase):
    def test_resolves_typed_targets_for_single_type_connector(self) -> None:
        requested_ids, resolved_targets = resolve_full_sync_targets_from_rows(
            request_targets=[_target(SyncTargetType.CHANNEL, "channel-123")],
            rows=[_TargetRow("channel-123", "support")],
            target_type=SyncTargetType.CHANNEL,
            key_getter=lambda row: row.target_id,
            name_getter=lambda row: row.target_name,
            error_message="requested targets contain unknown channels",
            error_metadata={"team_id": "team-123"},
        )

        self.assertEqual(requested_ids, ["channel-123"])
        self.assertEqual(len(resolved_targets.targets), 1)
        self.assertEqual(resolved_targets.targets[0].target_type, SyncTargetType.CHANNEL)
        self.assertEqual(resolved_targets.targets[0].target_id, "channel-123")

    def test_rejects_wrong_target_type_before_id_matching(self) -> None:
        with self.assertRaisesRegex(
            SyncRequestException,
            "requested targets contain invalid target_type",
        ) as context:
            resolve_full_sync_targets_from_rows(
                request_targets=[_target(SyncTargetType.REPOSITORY, "channel-123")],
                rows=[_TargetRow("channel-123", "support")],
                target_type=SyncTargetType.CHANNEL,
                key_getter=lambda row: row.target_id,
                name_getter=lambda row: row.target_name,
                error_message="requested targets contain unknown channels",
                error_metadata={"team_id": "team-123"},
            )

        self.assertEqual(
            context.exception.metadata,
            {
                "team_id": "team-123",
                "expected_target_type": "channel",
                "invalid_targets": [
                    {
                        "target_type": "repository",
                        "target_id": "channel-123",
                    }
                ],
            },
        )

    def test_deduplicates_requested_targets_by_type_and_id(self) -> None:
        requested_ids, resolved_targets = resolve_full_sync_targets_from_rows(
            request_targets=[
                _target(SyncTargetType.CHANNEL, "channel-123"),
                _target(SyncTargetType.CHANNEL, "channel-123"),
            ],
            rows=[_TargetRow("channel-123", "support")],
            target_type=SyncTargetType.CHANNEL,
            key_getter=lambda row: row.target_id,
            name_getter=lambda row: row.target_name,
            error_message="requested targets contain unknown channels",
            error_metadata={"team_id": "team-123"},
        )

        self.assertEqual(requested_ids, ["channel-123"])
        self.assertEqual(len(resolved_targets.targets), 1)
