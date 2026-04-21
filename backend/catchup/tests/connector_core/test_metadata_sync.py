from __future__ import annotations

from collections.abc import Mapping
from unittest import IsolatedAsyncioTestCase

from catchup.connector_core.application.metadata_sync import (
    ConnectorMetadataSyncApplication,
)
from catchup.connector_core.domain.structure import ConnectorKey
from catchup.connector_core.ports.metadata_sync import MetadataSyncPlan
from catchup.connector_core.ports.metadata_sync import MetadataSyncRequest
from catchup.connector_core.ports.metadata_sync import MetadataSyncResult
from catchup.connector_core.ports.metadata_sync import MetadataSyncStep
from catchup.connector_core.ports.metadata_sync import MetadataSyncStepResult


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


class ConnectorMetadataSyncApplicationTests(IsolatedAsyncioTestCase):
    async def test_sync_runs_connector_defined_plan_without_knowing_step_names(self) -> None:
        port = _RecordingMetadataPort()
        application = ConnectorMetadataSyncApplication(port=port)

        result = await application.sync_metadata(
            MetadataSyncRequest(
                connector=ConnectorKey.CHANNEL_TALK,
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
        self.assertEqual(result.connector, ConnectorKey.CHANNEL_TALK)
        self.assertEqual(result.tenant_id, "channel-123")
        self.assertIsInstance(result, MetadataSyncResult)
        self.assertEqual(sorted(result.steps), ["alpha", "beta", "gamma"])
        self.assertEqual(result.steps["alpha"].synced_count, 1)
        self.assertEqual(result.steps["beta"].synced_count, 2)
        self.assertEqual(result.steps["gamma"].synced_count, 3)
