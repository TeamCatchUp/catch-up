from __future__ import annotations

from datetime import datetime
from typing import Protocol
from typing import TypeVar

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import ValidationInfo
from pydantic import field_validator
from pydantic import model_validator

from catchup.connector_core.domain.structure import ConnectorKey
from catchup.utils.validation import require_text


class FullSyncWindow(BaseModel):
    """
    Full Sync Request가 요청한 데이터 수집 범위
    - 기존 sync_from_ts -> FullSyncWindow으로 점진적 마이그레이션 필요
    """

    model_config = ConfigDict(extra="forbid")

    window_start: datetime
    window_end: datetime

    @model_validator(mode="after")
    def _validate_window_bounds(self) -> "FullSyncWindow":
        if self.window_start > self.window_end:
            raise ValueError("window_start must be less than or equal to window_end")
        return self


class FullSyncExecutionRequest(BaseModel):
    """
    Generic Full Sync execution request.
    - HTTP Request가 아닌, 내부 execution에서 사용하는 request
    """

    model_config = ConfigDict(extra="forbid")

    connector: ConnectorKey
    tenant_id: str
    target: str

    @field_validator("tenant_id", "target")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)


class FullSyncExecutionResult(BaseModel):
    """
    Generic Full Sync execution result.
    - HTTP Response가 아닌, 내부 execution 결과
    """

    model_config = ConfigDict(extra="forbid")

    connector: ConnectorKey
    tenant_id: str
    target: str

    @field_validator("tenant_id", "target")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)


ExecutionRequestT = TypeVar("ExecutionRequestT", bound=FullSyncExecutionRequest)
FetchResultT = TypeVar("FetchResultT")
TransformResultT = TypeVar("TransformResultT")
SummaryResultT = TypeVar("SummaryResultT")
PersistResultT = TypeVar("PersistResultT")
ExecutionResultT = TypeVar("ExecutionResultT", bound=FullSyncExecutionResult)


class FullSyncPort(
    Protocol[
        ExecutionRequestT,
        FetchResultT,
        TransformResultT,
        SummaryResultT,
        PersistResultT,
        ExecutionResultT,
    ]
):
    """Fetch -> transform -> summarize(no-op 가능) -> persist -> result 순서를 adapter 뒤로 감춘다."""

    async def fetch(
        self,
        *,
        execution: ExecutionRequestT,
        sync_window: FullSyncWindow,
    ) -> FetchResultT: ...

    async def transform(
        self,
        *,
        execution: ExecutionRequestT,
        sync_window: FullSyncWindow,
        fetched: FetchResultT,
    ) -> TransformResultT: ...

    async def summarize(
        self,
        *,
        execution: ExecutionRequestT,
        sync_window: FullSyncWindow,
        transformed: TransformResultT,
    ) -> SummaryResultT: ...

    async def persist(
        self,
        *,
        execution: ExecutionRequestT,
        sync_window: FullSyncWindow,
        transformed: TransformResultT,
        summary: SummaryResultT,
    ) -> PersistResultT: ...

    def build_result(
        self,
        *,
        execution: ExecutionRequestT,
        sync_window: FullSyncWindow,
        fetched: FetchResultT,
        transformed: TransformResultT,
        summary: SummaryResultT,
        persisted: PersistResultT,
    ) -> ExecutionResultT: ...
