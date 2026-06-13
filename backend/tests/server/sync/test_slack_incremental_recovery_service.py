from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import patch

import catchup.sync.repair.slack_incremental_recovery_service as recovery_module
from catchup.connectors.slack.client import SlackRateLimitError
from catchup.sync.repair.slack_incremental_recovery_service import (
    SlackIncrementalRecoveryService,
)
from catchup.sync.repair.slack_incremental_recovery_service import (
    SlackRecoveryCandidate,
)
from catchup.sync.repair.slack_incremental_recovery_service import SlackRecoveryPlan


class SlackIncrementalRecoveryServiceTests(IsolatedAsyncioTestCase):
    async def test_recover_retries_all_current_incremental_records(self) -> None:
        service = SlackIncrementalRecoveryService()
        fake_repository = SimpleNamespace(delete_documents=AsyncMock())
        fake_slack_service = SimpleNamespace(
            repository=fake_repository,
            retry_missing_records=AsyncMock(
                return_value=SimpleNamespace(
                    records=[SimpleNamespace(succeeded_count=2, failed_ids=[])]
                )
            ),
        )

        with (
            patch.object(
                service,
                "_load_candidates",
                AsyncMock(
                    return_value=SlackRecoveryPlan(
                        team_id="T123",
                        candidates=(
                            SlackRecoveryCandidate(
                                channel_id="C123",
                                rehydrate_record_ids=("1711.0001", "1711.0002"),
                                delete_record_ids=("1711.0003",),
                            ),
                        ),
                    )
                ),
            ) as load_candidates,
            patch.object(
                service,
                "_get_service",
                AsyncMock(return_value=fake_slack_service),
            ) as get_service,
            patch.object(
                service,
                "_mark_record_keys_recovered_sync",
                return_value=1,
            ) as mark_recovered,
        ):
            response = await service.recover()

        load_candidates.assert_awaited_once_with()
        get_service.assert_awaited_once_with("T123")
        fake_repository.delete_documents.assert_awaited_once_with(
            ["slack:message:T123:C123:1711.0003"]
        )
        fake_slack_service.retry_missing_records.assert_awaited_once_with(
            channel_id="C123",
            channel_name="C123",
            message_ids=["1711.0001", "1711.0002"],
        )
        self.assertEqual(mark_recovered.call_count, 2)
        self.assertEqual(
            mark_recovered.call_args_list[0].args[0],
            ["slack:T123:channel:C123:message:1711.0003"],
        )
        self.assertEqual(
            mark_recovered.call_args_list[1].args[0],
            [
                "slack:T123:channel:C123:message:1711.0001",
                "slack:T123:channel:C123:message:1711.0002",
            ],
        )
        self.assertEqual(response.total_incremental_records_before_recovery, 3)
        self.assertEqual(response.succeeded_records, 3)
        self.assertEqual(response.failed_records, 0)

    async def test_recover_keeps_processing_after_channel_failure(self) -> None:
        service = SlackIncrementalRecoveryService()
        fake_repository = SimpleNamespace(delete_documents=AsyncMock())
        fake_slack_service = SimpleNamespace(
            repository=fake_repository,
            retry_missing_records=AsyncMock(
                side_effect=[
                    RuntimeError("boom"),
                    SimpleNamespace(
                        records=[SimpleNamespace(succeeded_count=1, failed_ids=[])]
                    ),
                ]
            ),
        )

        with (
            patch.object(
                service,
                "_load_candidates",
                AsyncMock(
                    return_value=SlackRecoveryPlan(
                        team_id="T123",
                        candidates=(
                            SlackRecoveryCandidate(
                                channel_id="C123",
                                rehydrate_record_ids=("1711.0001",),
                                delete_record_ids=(),
                            ),
                            SlackRecoveryCandidate(
                                channel_id="C124",
                                rehydrate_record_ids=("1711.0002",),
                                delete_record_ids=(),
                            ),
                        ),
                    )
                ),
            ),
            patch.object(
                service,
                "_get_service",
                AsyncMock(return_value=fake_slack_service),
            ),
            patch.object(
                service,
                "_mark_record_keys_recovered_sync",
                return_value=1,
            ) as mark_recovered,
        ):
            response = await service.recover()

        self.assertEqual(fake_slack_service.retry_missing_records.await_count, 2)
        first_call = fake_slack_service.retry_missing_records.await_args_list[0]
        second_call = fake_slack_service.retry_missing_records.await_args_list[1]
        self.assertEqual(first_call.kwargs["message_ids"], ["1711.0001"])
        self.assertEqual(second_call.kwargs["message_ids"], ["1711.0002"])
        mark_recovered.assert_called_once_with(
            ["slack:T123:channel:C124:message:1711.0002"]
        )

        self.assertEqual(response.total_incremental_records_before_recovery, 2)
        self.assertEqual(response.succeeded_records, 1)
        self.assertEqual(response.failed_records, 1)

    async def test_recover_counts_team_service_init_failure_as_failed(self) -> None:
        service = SlackIncrementalRecoveryService()

        with (
            patch.object(
                service,
                "_load_candidates",
                AsyncMock(
                    return_value=SlackRecoveryPlan(
                        team_id="T123",
                        candidates=(
                            SlackRecoveryCandidate(
                                channel_id="C123",
                                rehydrate_record_ids=("1711.0001",),
                                delete_record_ids=(),
                            ),
                            SlackRecoveryCandidate(
                                channel_id="C124",
                                rehydrate_record_ids=("1711.0002",),
                                delete_record_ids=(),
                            ),
                        ),
                    )
                ),
            ),
            patch.object(
                service,
                "_get_service",
                AsyncMock(side_effect=RuntimeError("team init failed")),
            ),
        ):
            response = await service.recover()

        self.assertEqual(response.total_incremental_records_before_recovery, 2)
        self.assertEqual(response.succeeded_records, 0)
        self.assertEqual(response.failed_records, 2)

    async def test_recover_propagates_slack_rate_limit_error(self) -> None:
        service = SlackIncrementalRecoveryService()
        fake_slack_service = SimpleNamespace(
            repository=SimpleNamespace(delete_documents=AsyncMock()),
            retry_missing_records=AsyncMock(
                side_effect=SlackRateLimitError(
                    message="Slack API rate limited during recovery",
                    retry_after=3,
                )
            ),
        )

        with (
            patch.object(
                service,
                "_load_candidates",
                AsyncMock(
                    return_value=SlackRecoveryPlan(
                        team_id="T123",
                        candidates=(
                            SlackRecoveryCandidate(
                                channel_id="C123",
                                rehydrate_record_ids=("1711.0001",),
                                delete_record_ids=(),
                            ),
                        ),
                    )
                ),
            ),
            patch.object(
                service,
                "_get_service",
                AsyncMock(return_value=fake_slack_service),
            ),
        ):
            with self.assertRaises(SlackRateLimitError):
                await service.recover()

    async def test_recover_propagates_slack_rate_limit_error_during_service_init(self) -> None:
        service = SlackIncrementalRecoveryService()

        with (
            patch.object(
                service,
                "_load_candidates",
                AsyncMock(
                    return_value=SlackRecoveryPlan(
                        team_id="T123",
                        candidates=(
                            SlackRecoveryCandidate(
                                channel_id="C123",
                                rehydrate_record_ids=("1711.0001",),
                                delete_record_ids=(),
                            ),
                        ),
                    )
                ),
            ),
            patch.object(
                service,
                "_get_service",
                AsyncMock(
                    side_effect=SlackRateLimitError(
                        message="Slack API rate limited during init",
                        retry_after=3,
                    )
                ),
            ),
        ):
            with self.assertRaises(SlackRateLimitError):
                await service.recover()

    async def test_build_recovery_plan_deduplicates_same_record_id(self) -> None:
        service = SlackIncrementalRecoveryService()
        rows = [
            SimpleNamespace(
                scope_id="T123",
                parent_id="C123",
                record_id="1711.0001",
                event_kind="updated",
            ),
            SimpleNamespace(
                scope_id="T123",
                parent_id="C124",
                record_id="1711.0001",
                event_kind="deleted",
            ),
            SimpleNamespace(
                scope_id="T123",
                parent_id="C124",
                record_id="1711.0002",
                event_kind="deleted",
            ),
        ]

        plan = service._build_recovery_plan(rows)

        self.assertEqual(plan.team_id, "T123")
        self.assertEqual(
            plan.candidates,
            (
                SlackRecoveryCandidate(
                    channel_id="C123",
                    rehydrate_record_ids=("1711.0001",),
                    delete_record_ids=(),
                ),
                SlackRecoveryCandidate(
                    channel_id="C124",
                    rehydrate_record_ids=(),
                    delete_record_ids=("1711.0002",),
                ),
            ),
        )

    async def test_build_recovery_plan_keeps_latest_row_for_same_record_id(self) -> None:
        service = SlackIncrementalRecoveryService()
        rows = [
            SimpleNamespace(
                scope_id="T123",
                parent_id="C123",
                record_id="1711.0001",
                event_kind="deleted",
            ),
            SimpleNamespace(
                scope_id="T123",
                parent_id="C124",
                record_id="1711.0001",
                event_kind="updated",
            ),
        ]

        plan = service._build_recovery_plan(rows)

        self.assertEqual(
            plan.candidates,
            (
                SlackRecoveryCandidate(
                    channel_id="C123",
                    rehydrate_record_ids=(),
                    delete_record_ids=("1711.0001",),
                ),
            ),
        )

    async def test_build_recovery_plan_ignores_rows_from_other_teams(self) -> None:
        service = SlackIncrementalRecoveryService()
        rows = [
            SimpleNamespace(
                scope_id="T123",
                parent_id="C123",
                record_id="1711.0001",
                event_kind="updated",
            ),
            SimpleNamespace(
                scope_id="T999",
                parent_id="C999",
                record_id="1711.0002",
                event_kind="updated",
            ),
        ]

        plan = service._build_recovery_plan(rows)

        self.assertEqual(plan.team_id, "T123")
        self.assertEqual(
            plan.candidates,
            (
                SlackRecoveryCandidate(
                    channel_id="C123",
                    rehydrate_record_ids=("1711.0001",),
                    delete_record_ids=(),
                ),
            ),
        )

    async def test_chunk_record_ids_splits_large_batches(self) -> None:
        service = SlackIncrementalRecoveryService()
        record_ids = tuple(f"1711.{index:04d}" for index in range(201))

        batches = service._chunk_record_ids(
            record_ids,
            service._RECOVERY_BATCH_SIZE,
        )

        self.assertEqual(len(batches), 2)
        self.assertEqual(len(batches[0]), 200)
        self.assertEqual(len(batches[1]), 1)

    async def test_load_candidates_sync_builds_expected_query_filters(self) -> None:
        service = SlackIncrementalRecoveryService()
        captured: dict[str, object] = {}

        class _FakeResult:
            def all(self):
                return []

        class _FakeSession:
            def execute(self, stmt):
                captured["stmt"] = stmt
                return _FakeResult()

        class _FakeSessionFactory:
            def __enter__(self):
                return _FakeSession()

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch.object(recovery_module, "SessionLocal", return_value=_FakeSessionFactory()):
            plan = service._load_candidates_sync()

        sql = str(captured["stmt"])
        self.assertEqual(plan, SlackRecoveryPlan())
        self.assertIn("incremental_record_states.connector", sql)
        self.assertIn("incremental_record_states.record_type", sql)
        self.assertIn("incremental_record_states.status !=", sql)
        self.assertIn("ORDER BY incremental_record_states.updated_at DESC", sql)
        self.assertIn("incremental_record_states.last_event_at DESC", sql)

    async def test_build_record_keys_uses_incremental_record_key_format(self) -> None:
        record_keys = SlackIncrementalRecoveryService._build_record_keys(
            scope_id="T123",
            channel_id="C123",
            record_ids=["1711.0001", "1711.0002"],
        )

        self.assertEqual(
            record_keys,
            [
                "slack:T123:channel:C123:message:1711.0001",
                "slack:T123:channel:C123:message:1711.0002",
            ],
        )
