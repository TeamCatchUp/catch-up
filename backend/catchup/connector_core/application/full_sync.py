from __future__ import annotations

from typing import Generic

from catchup.connector_core.ports.full_sync import ExecutionRequestT
from catchup.connector_core.ports.full_sync import ExecutionResultT
from catchup.connector_core.ports.full_sync import FetchResultT
from catchup.connector_core.ports.full_sync import FullSyncPort
from catchup.connector_core.ports.full_sync import FullSyncWindow
from catchup.connector_core.ports.full_sync import PersistResultT
from catchup.connector_core.ports.full_sync import SummaryResultT
from catchup.connector_core.ports.full_sync import TransformResultT


class ConnectorFullSyncApplication(
    Generic[
        ExecutionRequestT,
        FetchResultT,
        TransformResultT,
        SummaryResultT,
        PersistResultT,
        ExecutionResultT,
    ]
):
    """Generic Full Sync Pipeline Orchestration"""

    def __init__(
        self,
        *,
        port: FullSyncPort[
            ExecutionRequestT,
            FetchResultT,
            TransformResultT,
            SummaryResultT,
            PersistResultT,
            ExecutionResultT,
        ],
    ) -> None:
        self.port = port

    async def run_full_sync(
        self,
        *,
        execution: ExecutionRequestT,
        sync_window: FullSyncWindow,
    ) -> ExecutionResultT:
        fetched = await self.port.fetch(
            execution=execution,
            sync_window=sync_window,
        )
        transformed = await self.port.transform(
            execution=execution,
            sync_window=sync_window,
            fetched=fetched,
        )
        summary = await self.port.summarize(
            execution=execution,
            sync_window=sync_window,
            transformed=transformed,
        )
        persisted = await self.port.persist(
            execution=execution,
            sync_window=sync_window,
            transformed=transformed,
            summary=summary,
        )
        return self.port.build_result(
            execution=execution,
            sync_window=sync_window,
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=persisted,
        )
