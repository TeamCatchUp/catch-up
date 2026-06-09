from __future__ import annotations

from catchup.sync.ingestion.logging import sync_ingestion_system_log
from catchup.sync.ingestion.protocols import ExecutionRequestT
from catchup.sync.ingestion.protocols import ExecutionResultT
from catchup.sync.ingestion.protocols import FetchResultT
from catchup.sync.ingestion.protocols import PersistResultT
from catchup.sync.ingestion.protocols import SummaryResultT
from catchup.sync.ingestion.protocols import SyncIngestionPort
from catchup.sync.ingestion.protocols import TransformResultT
from catchup.sync.ingestion.schemas import SyncWindow


@sync_ingestion_system_log
async def run_sync_ingestion(
    *,
    port: SyncIngestionPort[
        ExecutionRequestT,
        FetchResultT,
        TransformResultT,
        SummaryResultT,
        PersistResultT,
        ExecutionResultT,
    ],
    execution: ExecutionRequestT,
    sync_window: SyncWindow,
) -> ExecutionResultT:
    fetched = await port.fetch(
        execution=execution,
        sync_window=sync_window,
    )
    transformed = await port.transform(
        execution=execution,
        sync_window=sync_window,
        fetched=fetched,
    )
    summary = await port.summarize(
        execution=execution,
        sync_window=sync_window,
        transformed=transformed,
    )
    persisted = await port.persist(
        execution=execution,
        sync_window=sync_window,
        transformed=transformed,
        summary=summary,
    )
    return port.build_result(
        execution=execution,
        sync_window=sync_window,
        fetched=fetched,
        transformed=transformed,
        summary=summary,
        persisted=persisted,
    )


__all__ = ["run_sync_ingestion"]
