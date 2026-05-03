from __future__ import annotations

from catchup.connector_core.ports.sync_ingestion import ExecutionRequestT
from catchup.connector_core.ports.sync_ingestion import ExecutionResultT
from catchup.connector_core.ports.sync_ingestion import FetchResultT
from catchup.connector_core.ports.sync_ingestion import PersistResultT
from catchup.connector_core.ports.sync_ingestion import SummaryResultT
from catchup.connector_core.ports.sync_ingestion import SyncIngestionPort
from catchup.connector_core.ports.sync_ingestion import SyncWindow
from catchup.connector_core.ports.sync_ingestion import TransformResultT


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
