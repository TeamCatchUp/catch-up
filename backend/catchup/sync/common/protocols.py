from __future__ import annotations

import asyncio
from typing import Protocol
from typing import runtime_checkable

from catchup.db.models import SyncConnector
from catchup.db.models import SyncType
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import FullSyncDispatchRequest
from catchup.sync.common.schemas import FullSyncResolvedTargets
from catchup.sync.common.schemas import FullSyncRepairResult
from catchup.sync.common.schemas import FullSyncValidationResult
from catchup.sync.common.schemas import PublishTasksResult
from catchup.sync.common.schemas import SyncContext
from catchup.sync.common.schemas import SyncStreamMessage
from catchup.sync.common.schemas import SyncStreamTask
from catchup.sync.common.schemas import TargetSyncResult


class EventPublisherProtocol(Protocol):
    async def publish(self, *, tasks: list[SyncStreamTask]) -> PublishTasksResult:
        """이벤트 목록을 Stream에 publish 하고 publish 결과를 반환."""
        ...


class WorkerProtocol(Protocol):
    async def run_forever(self, stop_event: asyncio.Event) -> None:
        ...

    async def process(self, message: SyncStreamMessage) -> None:
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

@runtime_checkable
class FullSyncCollectingHandlerProtocol(Protocol):
    async def collect_identifiers(
        self,
        *,
        context: FullSyncContext,
        service_cache: dict[str, object],
    ) -> list[str]:
        """Full Sync chunk event 범위의 canonical identifier 목록을 수집."""
        ...


@runtime_checkable
class FullSyncValidatingHandlerProtocol(Protocol):
    async def validate_sync_result(
        self,
        *,
        context: FullSyncContext,
        expected_ids: list[str],
        service_cache: dict[str, object],
    ) -> FullSyncValidationResult:
        """Full Sync chunk 실행 후 stored/missing 상태를 검증."""
        ...

    async def repair_missing_records(
        self,
        *,
        context: FullSyncContext,
        validation_result: FullSyncValidationResult,
        service_cache: dict[str, object],
    ) -> FullSyncRepairResult:
        """Validation 결과가 threshold 이내일 때 by-id repair를 수행."""
        ...

class FullSyncTargetResolverProtocol(Protocol):
    async def resolve_full_sync_targets(
        self,
        *,
        request: FullSyncDispatchRequest,
    ) -> FullSyncResolvedTargets:
        ...
