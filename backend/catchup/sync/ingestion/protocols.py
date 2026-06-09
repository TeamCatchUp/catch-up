from __future__ import annotations

from typing import Protocol
from typing import TypeVar

from catchup.sync.ingestion.schemas import SyncExecutionRequest
from catchup.sync.ingestion.schemas import SyncExecutionResult
from catchup.sync.ingestion.schemas import SyncWindow

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


__all__ = [
    "ExecutionRequestT",
    "ExecutionResultT",
    "FetchResultT",
    "PersistResultT",
    "SummaryResultT",
    "SyncIngestionPort",
    "TransformResultT",
]
