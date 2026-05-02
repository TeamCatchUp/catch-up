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


class SyncWindow(BaseModel):
    """Data Collection Window : Shared By Full Sync & Incremental Sync"""

    model_config = ConfigDict(extra="forbid")

    window_start: datetime
    window_end: datetime

    @model_validator(mode="after")
    def _validate_window_bounds(self) -> "SyncWindow":
        if self.window_start > self.window_end:
            raise ValueError("window_start must be less than or equal to window_end")
        return self


class SyncExecutionRequest(BaseModel):
    """Internal Execution Request passed from Handlers to Ingestion Adapters."""

    model_config = ConfigDict(extra="forbid")

    connector: ConnectorKey
    tenant_id: str
    target: str

    @field_validator("tenant_id", "target")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")


class SyncExecutionResult(BaseModel):
    """Internal result returned by ingestion adapters."""

    model_config = ConfigDict(extra="forbid")

    connector: ConnectorKey
    tenant_id: str
    target: str

    @field_validator("tenant_id", "target")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name or "field")


ExecutionRequestT = TypeVar("ExecutionRequestT", bound=SyncExecutionRequest)
FetchResultT = TypeVar("FetchResultT")
TransformResultT = TypeVar("TransformResultT")
SummaryResultT = TypeVar("SummaryResultT")
PersistResultT = TypeVar("PersistResultT")
ExecutionResultT = TypeVar("ExecutionResultT", bound=SyncExecutionResult)


class SyncIngestionPort(
    Protocol[
        ExecutionRequestT,
        FetchResultT,
        TransformResultT,
        SummaryResultT,
        PersistResultT,
        ExecutionResultT,
    ]
):
    """Fetch -> transform -> summarize(no-op possible) -> persist -> result."""

    async def fetch(
        self,
        *,
        execution: ExecutionRequestT,
        sync_window: SyncWindow,
    ) -> FetchResultT: ...

    async def transform(
        self,
        *,
        execution: ExecutionRequestT,
        sync_window: SyncWindow,
        fetched: FetchResultT,
    ) -> TransformResultT: ...

    async def summarize(
        self,
        *,
        execution: ExecutionRequestT,
        sync_window: SyncWindow,
        transformed: TransformResultT,
    ) -> SummaryResultT: ...

    async def persist(
        self,
        *,
        execution: ExecutionRequestT,
        sync_window: SyncWindow,
        transformed: TransformResultT,
        summary: SummaryResultT,
    ) -> PersistResultT: ...

    def build_result(
        self,
        *,
        execution: ExecutionRequestT,
        sync_window: SyncWindow,
        fetched: FetchResultT,
        transformed: TransformResultT,
        summary: SummaryResultT,
        persisted: PersistResultT,
    ) -> ExecutionResultT: ...
