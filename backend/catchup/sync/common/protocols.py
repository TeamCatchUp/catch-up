from __future__ import annotations

import asyncio
from typing import Protocol

from catchup.db.models import SyncConnector
from catchup.db.models import SyncType
from catchup.sync.common.context import FullSyncContext
from catchup.sync.common.context import IncrementalSyncContext
from catchup.sync.common.context import PageIngestionRequest
from catchup.sync.common.context import RecordIngestionRequest
from catchup.sync.common.context import SyncContext
from catchup.sync.common.results import EventSyncResult
from catchup.sync.common.results import PageSyncResult
from catchup.sync.common.results import TargetSyncResult
from catchup.sync.common.schemas import FullSyncDispatchRequest
from catchup.sync.common.schemas import FullSyncResolvedTargets
from catchup.sync.common.schemas import PublishTasksResult
from catchup.sync.common.schemas import SyncStreamMessage
from catchup.sync.common.schemas import SyncStreamTask


class EventPublisherProtocol(Protocol):
    async def publish(self, *, tasks: list[SyncStreamTask]) -> PublishTasksResult:
        """이벤트 목록을 Stream에 publish 하고 publish 결과를 반환."""
        ...


class WorkerProtocol(Protocol):
    async def run_forever(self, stop_event: asyncio.Event) -> None:
        ...

    async def process(self, message: SyncStreamMessage) -> None:
        ...


class FullSyncTargetResolver(Protocol):
    async def resolve(self, request: FullSyncDispatchRequest) -> FullSyncResolvedTargets:
        ...


class FullSyncHandler(Protocol):
    connector: SyncConnector | str

    async def handle(self, context: FullSyncContext) -> EventSyncResult:
        ...


class IncrementalSyncHandler(Protocol):
    connector: SyncConnector | str

    async def handle(self, context: IncrementalSyncContext) -> EventSyncResult:
        ...


class SyncIngestionPipeline(Protocol):
    async def ingest_page(self, request: PageIngestionRequest) -> PageSyncResult:
        ...

    async def ingest_record(self, request: RecordIngestionRequest) -> PageSyncResult:
        ...


class IngestionHandlerProtocol(Protocol):
    connector: SyncConnector | str
    sync_type: SyncType | str

    async def handle(
        self,
        *,
        context: SyncContext,
        service_cache: dict[str, object],
    ) -> TargetSyncResult:
        ...

    async def on_job_started(
        self,
        *,
        context: SyncContext,
        total_targets: int,
    ) -> None:
        ...

    async def on_target_started(
        self,
        *,
        context: SyncContext,
    ) -> None:
        ...

    async def on_target_requeued(
        self,
        *,
        context: SyncContext,
        next_attempt: int,
        error_summary: str,
    ) -> None:
        ...

    async def on_target_failed(
        self,
        *,
        context: SyncContext,
        next_attempt: int,
        error_summary: str,
        retryable: bool,
    ) -> None:
        ...

    async def on_target_completed(
        self,
        *,
        context: SyncContext,
        result: TargetSyncResult,
    ) -> None:
        ...

    async def on_job_completed(
        self,
        *,
        context: FullSyncContext,
        total_targets: int,
        completed_targets: int,
        failed_targets: int,
        requeued_targets: int,
    ) -> None:
        ...

    async def on_job_failed(
        self,
        *,
        context: FullSyncContext,
        total_targets: int,
        failed_targets: int,
    ) -> None:
        ...


class FullSyncTargetResolverProtocol(Protocol):
    async def resolve_full_sync_targets(
        self,
        *,
        request: FullSyncDispatchRequest,
    ) -> FullSyncResolvedTargets:
        ...
