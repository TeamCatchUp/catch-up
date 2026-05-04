"""
Metadata Sync Contract
- core는 각 Connector Metadata Sync에는 여러 Step이 존재하고 Step 단위로 실행한다만 알고 있다.
"""
from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from typing import Protocol

from pydantic import BaseModel
from pydantic import Field

from catchup.connector_core.domain.structure import ConnectorKey


class MetadataSyncRequest(BaseModel):
    """메타데이터 동기화에 필요한 최소 입력을 고정한다."""
    connector: ConnectorKey
    tenant_id: str
    target_id: str | None = None


class MetadataSyncStepResult(BaseModel):
    """각 step이 남기는 공통 결과 envelope."""
    synced_count: int = 0
    # 다음 step에 넘겨야 할 임시 결과물
    artifacts: dict[str, Any] = Field(default_factory=dict)


# Awaitable:
# - "await 할 수 있는 값"을 뜻한다.
# - async def 함수 호출 결과는 보통 Awaitable 이다.
#
# Callable:
# - "호출 가능한 객체(함수)"를 뜻한다.
#
# StepRunner:
# - Mapping[str, MetadataSyncStepResult]: 앞서 끝난 step 결과들 
# - Awaitable[MetadataSyncStepResult]: await 가능한 현재 step 결과 
# "이전 step 결과들을 입력으로 받아, 비동기로 실행되고, 현재 step 결과를 돌려주는 함수"
StepRunner = Callable[
    [Mapping[str, MetadataSyncStepResult]],
    Awaitable[MetadataSyncStepResult],
]


@dataclass(frozen=True)
class MetadataSyncStep:
    """Core가 이해하는 최소 실행 단위."""
    name: str
    run: StepRunner
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class MetadataSyncPlan:
    request: MetadataSyncRequest
    steps: tuple[MetadataSyncStep, ...]


class MetadataSyncResult(BaseModel):
    connector: ConnectorKey
    tenant_id: str
    target_id: str | None = None
    # Map of step_name + StepResult
    steps: dict[str, MetadataSyncStepResult] = Field(default_factory=dict)

    def step_result(self, name: str) -> MetadataSyncStepResult | None:
        return self.steps.get(name)


class MetadataSyncPort(Protocol):
    """
    Adapter에서 Step을 조립하여 core에게 넘김
    """
    async def build_plan(
        self,
        request: MetadataSyncRequest,
    ) -> MetadataSyncPlan: ...
