from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import structlog

logger = structlog.get_logger(__name__)


class BackfillBatchResult(Protocol):
    @property
    def scanned(self) -> int: ...

    @property
    def succeeded(self) -> int: ...

    @property
    def skipped(self) -> int: ...

    @property
    def failed(self) -> int: ...


class BackfillService(Protocol):
    def backfill_batch(
        self,
        *,
        limit: int,
        locked_by: str | None = None,
    ) -> Awaitable[BackfillBatchResult]: ...


@dataclass(slots=True, frozen=True)
class SequentialBackfillSpec:
    key: str
    connector: str
    entity_type: str
    service_factory: Callable[[], BackfillService]


@dataclass(slots=True, frozen=True)
class SequentialBackfillEntitySummary:
    key: str
    connector: str
    entity_type: str
    batches: int
    scanned: int
    succeeded: int
    skipped: int
    failed: int
    status: str
    stop_reason: str | None = None

    def to_log_fields(self) -> dict[str, object]:
        return {
            "key": self.key,
            "connector": self.connector,
            "entity_type": self.entity_type,
            "batches": self.batches,
            "scanned": self.scanned,
            "succeeded": self.succeeded,
            "skipped": self.skipped,
            "failed": self.failed,
            "status": self.status,
            "stop_reason": self.stop_reason,
        }


@dataclass(slots=True, frozen=True)
class SequentialBackfillRunSummary:
    entities: tuple[SequentialBackfillEntitySummary, ...]
    status: str
    stop_reason: str | None = None

    @property
    def scanned(self) -> int:
        return sum(entity.scanned for entity in self.entities)

    @property
    def succeeded(self) -> int:
        return sum(entity.succeeded for entity in self.entities)

    @property
    def skipped(self) -> int:
        return sum(entity.skipped for entity in self.entities)

    @property
    def failed(self) -> int:
        return sum(entity.failed for entity in self.entities)

    @property
    def completed_entities(self) -> int:
        return sum(
            1
            for entity in self.entities
            if entity.status in {"completed", "completed_with_failures"}
        )

    def to_log_fields(self) -> dict[str, object]:
        return {
            "status": self.status,
            "stop_reason": self.stop_reason,
            "entity_count": len(self.entities),
            "completed_entities": self.completed_entities,
            "scanned": self.scanned,
            "succeeded": self.succeeded,
            "skipped": self.skipped,
            "failed": self.failed,
        }


async def run_sequential_v2_backfill(
    specs: Sequence[SequentialBackfillSpec],
    *,
    batch_size: int,
    locked_by: str | None = None,
) -> SequentialBackfillRunSummary:
    summaries: list[SequentialBackfillEntitySummary] = []
    logger.info(
        "vector_store_v2_sequential_backfill_started",
        entity_count=len(specs),
        batch_size=batch_size,
        locked_by=locked_by,
    )

    for spec in specs:
        summary = await _run_entity_until_done(
            spec,
            batch_size=batch_size,
            locked_by=locked_by,
        )
        summaries.append(summary)

        if summary.status in {"failed", "blocked"}:
            run_summary = SequentialBackfillRunSummary(
                entities=tuple(summaries),
                status="stopped",
                stop_reason=summary.stop_reason,
            )
            logger.info(
                "vector_store_v2_sequential_backfill_stopped",
                **run_summary.to_log_fields(),
            )
            return run_summary

    run_status = "completed_with_failures" if any(
        summary.failed > 0 for summary in summaries
    ) else "completed"
    run_summary = SequentialBackfillRunSummary(
        entities=tuple(summaries),
        status=run_status,
    )
    logger.info(
        "vector_store_v2_sequential_backfill_completed",
        **run_summary.to_log_fields(),
    )
    return run_summary


async def _run_entity_until_done(
    spec: SequentialBackfillSpec,
    *,
    batch_size: int,
    locked_by: str | None,
) -> SequentialBackfillEntitySummary:
    service = spec.service_factory()
    batches = 0
    scanned = 0
    succeeded = 0
    skipped = 0
    failed = 0
    no_progress_batches = 0

    logger.info(
        "vector_store_v2_sequential_backfill_entity_started",
        key=spec.key,
        connector=spec.connector,
        entity_type=spec.entity_type,
        batch_size=batch_size,
    )

    while True:
        try:
            result = await service.backfill_batch(
                limit=batch_size,
                locked_by=locked_by,
            )
        except Exception as exc:
            summary = SequentialBackfillEntitySummary(
                key=spec.key,
                connector=spec.connector,
                entity_type=spec.entity_type,
                batches=batches,
                scanned=scanned,
                succeeded=succeeded,
                skipped=skipped,
                failed=failed,
                status="failed",
                stop_reason="exception",
            )
            logger.warning(
                "vector_store_v2_sequential_backfill_entity_failed",
                **summary.to_log_fields(),
                error_type=type(exc).__name__,
                error_message=str(exc),
                exc_info=True,
            )
            return summary

        batches += 1
        scanned += result.scanned
        succeeded += result.succeeded
        skipped += result.skipped
        failed += result.failed

        logger.info(
            "vector_store_v2_sequential_backfill_batch_completed",
            key=spec.key,
            connector=spec.connector,
            entity_type=spec.entity_type,
            batch_index=batches,
            scanned=result.scanned,
            succeeded=result.succeeded,
            skipped=result.skipped,
            failed=result.failed,
        )

        if result.scanned == 0:
            summary = SequentialBackfillEntitySummary(
                key=spec.key,
                connector=spec.connector,
                entity_type=spec.entity_type,
                batches=batches,
                scanned=scanned,
                succeeded=succeeded,
                skipped=skipped,
                failed=failed,
                status="completed_with_failures" if failed > 0 else "completed",
            )
            logger.info(
                "vector_store_v2_sequential_backfill_entity_completed",
                **summary.to_log_fields(),
            )
            return summary

        if result.succeeded == 0 and result.failed == 0 and result.skipped > 0:
            no_progress_batches += 1
            if no_progress_batches <= 1:
                logger.info(
                    "vector_store_v2_sequential_backfill_batch_retried_after_no_progress",
                    key=spec.key,
                    connector=spec.connector,
                    entity_type=spec.entity_type,
                    batch_index=batches,
                    no_progress_batches=no_progress_batches,
                )
                continue

            summary = SequentialBackfillEntitySummary(
                key=spec.key,
                connector=spec.connector,
                entity_type=spec.entity_type,
                batches=batches,
                scanned=scanned,
                succeeded=succeeded,
                skipped=skipped,
                failed=failed,
                status="blocked",
                stop_reason="no_progress",
            )
            logger.info(
                "vector_store_v2_sequential_backfill_entity_stopped",
                **summary.to_log_fields(),
            )
            return summary

        no_progress_batches = 0
