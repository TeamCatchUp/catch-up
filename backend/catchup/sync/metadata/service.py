from __future__ import annotations

from catchup.sync.metadata.result_store import MetadataSyncResultStore
from catchup.sync.metadata.result_store import NoopMetadataSyncResultStore
from catchup.sync.metadata.schemas import MetadataSyncPlan
from catchup.sync.metadata.schemas import MetadataSyncPort
from catchup.sync.metadata.schemas import MetadataSyncRequest
from catchup.sync.metadata.schemas import MetadataSyncResult
from catchup.sync.metadata.schemas import MetadataSyncStepResult


class MetadataSyncService:
    """Metadata handler가 만든 step plan을 sync 소유 runner로 실행한다."""

    def __init__(
        self,
        *,
        port: MetadataSyncPort,
        result_store: MetadataSyncResultStore | None = None,
    ) -> None:
        self.port = port
        self.result_store = result_store or NoopMetadataSyncResultStore()

    async def sync_metadata(
        self,
        request: MetadataSyncRequest,
    ) -> MetadataSyncResult:
        await self.result_store.record_started(request)
        try:
            plan = await self.port.build_plan(request)
            step_results = await self._run_plan(plan)
            result = MetadataSyncResult(
                connector=request.connector,
                tenant_id=request.tenant_id,
                target_id=request.target_id,
                steps=step_results,
            )
        except Exception as exc:
            await self.result_store.record_failed(request, exc)
            raise

        await self.result_store.record_succeeded(result)
        return result

    async def _run_plan(
        self,
        plan: MetadataSyncPlan,
    ) -> dict[str, MetadataSyncStepResult]:
        # 아직 실행되지 않은 step
        pending = {step.name: step for step in plan.steps}

        # 이미 끝난 step
        completed: dict[str, MetadataSyncStepResult] = {}

        while pending:
            progressed = False
            for step_name, step in list(pending.items()):
                # depends_on 안의 step이 아직 끝나지 않았다면 지금 step은 건너뛴다.
                if any(dependency not in completed for dependency in step.depends_on):
                    continue

                # step.run 은 "이전 step 결과들을 받아 비동기로 현재 step을 실행하는 함수"다.
                completed[step_name] = await step.run(completed)
                del pending[step_name]
                progressed = True

            if progressed:
                continue

            # Dependency 구조가 잘못되어서 모두 pending에 남아있게 될 경우
            unresolved = ", ".join(sorted(pending))
            raise RuntimeError(
                f"Metadata sync plan is blocked by unresolved dependencies: {unresolved}"
            )

        return completed
