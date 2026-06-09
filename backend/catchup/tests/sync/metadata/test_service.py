from __future__ import annotations

from collections.abc import Mapping
from unittest import IsolatedAsyncioTestCase

from catchup.db.models import SyncConnector
from catchup.sync.metadata.schemas import MetadataSyncPlan
from catchup.sync.metadata.schemas import MetadataSyncRequest
from catchup.sync.metadata.schemas import MetadataSyncResult
from catchup.sync.metadata.schemas import MetadataSyncStep
from catchup.sync.metadata.schemas import MetadataSyncStepResult
from catchup.sync.metadata.service import MetadataSyncService


class _RecordingMetadataPort:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.request: MetadataSyncRequest | None = None

    async def build_plan(
        self,
        request: MetadataSyncRequest,
    ) -> MetadataSyncPlan:
        self.request = request
        return MetadataSyncPlan(
            request=request,
            steps=(
                MetadataSyncStep(name="alpha", run=self._run_alpha),
                MetadataSyncStep(name="beta", run=self._run_beta),
                MetadataSyncStep(
                    name="gamma",
                    depends_on=("alpha", "beta"),
                    run=self._run_gamma,
                ),
            ),
        )

    async def _run_alpha(
        self,
        _completed: Mapping[str, MetadataSyncStepResult],
    ) -> MetadataSyncStepResult:
        assert self.request is not None
        self.calls.append(f"alpha:{self.request.tenant_id}")
        return MetadataSyncStepResult(synced_count=1)

    async def _run_beta(
        self,
        _completed: Mapping[str, MetadataSyncStepResult],
    ) -> MetadataSyncStepResult:
        assert self.request is not None
        self.calls.append(f"beta:{self.request.tenant_id}")
        return MetadataSyncStepResult(
            synced_count=2,
            artifacts={
                "memberships": (
                    {
                        "channel_id": self.request.tenant_id,
                        "group_id": "group-1",
                        "manager_id": "manager-1",
                    },
                )
            },
        )

    async def _run_gamma(
        self,
        completed: Mapping[str, MetadataSyncStepResult],
    ) -> MetadataSyncStepResult:
        assert self.request is not None
        beta_step = completed["beta"]
        self.calls.append(
            f"gamma:{self.request.tenant_id}:{len(beta_step.artifacts['memberships'])}"
        )
        return MetadataSyncStepResult(synced_count=3)


class _FailingMetadataPort:
    async def build_plan(
        self,
        request: MetadataSyncRequest,
    ) -> MetadataSyncPlan:
        return MetadataSyncPlan(
            request=request,
            steps=(
                MetadataSyncStep(name="boom", run=self._run_boom),
            ),
        )

    async def _run_boom(
        self,
        _completed: Mapping[str, MetadataSyncStepResult],
    ) -> MetadataSyncStepResult:
        raise RuntimeError("metadata sync failed")


class _RecordingResultStore:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def record_started(self, request: MetadataSyncRequest) -> None:
        self.calls.append(f"started:{request.tenant_id}")

    async def record_succeeded(self, result: MetadataSyncResult) -> None:
        self.calls.append(f"succeeded:{result.tenant_id}:{len(result.steps)}")

    async def record_failed(
        self,
        request: MetadataSyncRequest,
        error: BaseException,
    ) -> None:
        self.calls.append(f"failed:{request.tenant_id}:{type(error).__name__}")


class MetadataSyncServiceTests(IsolatedAsyncioTestCase):
    async def test_sync_runs_connector_defined_plan_without_knowing_step_names(self) -> None:
        port = _RecordingMetadataPort()
        service = MetadataSyncService(port=port)

        result = await service.sync_metadata(
            MetadataSyncRequest(
                connector=SyncConnector.CHANNEL_TALK,
                tenant_id="channel-123",
            )
        )

        self.assertEqual(
            port.calls,
            [
                "alpha:channel-123",
                "beta:channel-123",
                "gamma:channel-123:1",
            ],
        )
        self.assertEqual(result.connector, SyncConnector.CHANNEL_TALK)
        self.assertEqual(result.tenant_id, "channel-123")
        self.assertIsInstance(result, MetadataSyncResult)
        self.assertEqual(sorted(result.steps), ["alpha", "beta", "gamma"])
        self.assertEqual(result.steps["alpha"].synced_count, 1)
        self.assertEqual(result.steps["beta"].synced_count, 2)
        self.assertEqual(result.steps["gamma"].synced_count, 3)

    async def test_sync_records_success_boundary(self) -> None:
        store = _RecordingResultStore()
        service = MetadataSyncService(
            port=_RecordingMetadataPort(),
            result_store=store,
        )

        await service.sync_metadata(
            MetadataSyncRequest(
                connector=SyncConnector.CHANNEL_TALK,
                tenant_id="channel-123",
            )
        )

        self.assertEqual(
            store.calls,
            [
                "started:channel-123",
                "succeeded:channel-123:3",
            ],
        )

    async def test_sync_records_failure_boundary(self) -> None:
        store = _RecordingResultStore()
        service = MetadataSyncService(
            port=_FailingMetadataPort(),
            result_store=store,
        )

        with self.assertRaisesRegex(RuntimeError, "metadata sync failed"):
            await service.sync_metadata(
                MetadataSyncRequest(
                    connector=SyncConnector.CHANNEL_TALK,
                    tenant_id="channel-123",
                )
            )

        self.assertEqual(
            store.calls,
            [
                "started:channel-123",
                "failed:channel-123:RuntimeError",
            ],
        )
