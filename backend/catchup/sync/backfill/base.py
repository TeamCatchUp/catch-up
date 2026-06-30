from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from itertools import batched
from typing import Any
from typing import Generic
from typing import NamedTuple
from typing import TypeVar

import structlog
from sqlalchemy.orm import Session

from catchup.configs.config import settings
from catchup.sync.backfill.concurrency import run_bounded_targets
from catchup.sync.backfill.state import BackfillCompletionDecision
from catchup.sync.backfill.state import build_failure_metadata
from catchup.sync.backfill.state import build_mark_finished_statement
from catchup.sync.backfill.state import build_mark_processing_statement
from catchup.sync.backfill.state import count_backfill_completion_failures
from catchup.sync.backfill.state import decide_backfill_completion
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.sync.ingestion.schemas import SyncExecutionResult
from catchup.sync.ingestion.schemas import SyncWindow

SessionFactory = Callable[[], AbstractContextManager[Session]]
AdapterT = TypeVar("AdapterT")
ExecutionT = TypeVar("ExecutionT")
CursorT = TypeVar("CursorT")
TargetContextT = TypeVar("TargetContextT")

SEED_INSERT_BATCH_SIZE = 100
HYDRATE_PIPELINE_BATCH_SIZE = 50


@dataclass(slots=True, frozen=True)
class BackfillSeed:
    langchain_id: str
    record_id: str
    content: str
    embedding: list[float]


@dataclass(slots=True, frozen=True)
class BackfillTarget:
    scope_id: str
    target_id: str
    expected_count: int
    pending_count: int
    target_name: str | None = None


@dataclass(slots=True, frozen=True)
class BackfillSeedCursor:
    record_id: str
    langchain_id: str


@dataclass(slots=True, frozen=True)
class BackfillResult:
    scanned: int
    succeeded: int
    skipped: int
    failed: int


class TargetBackfillResult(NamedTuple):
    succeeded: int
    skipped: int
    failed: int


class HydrateTargetResult(NamedTuple):
    backfill_count: int
    failed_ids: list[str]
    error_type: str | None
    error_message: str | None


class FinishResult(NamedTuple):
    decision: BackfillCompletionDecision
    persisted: bool


class BaseBackfillService(Generic[AdapterT, ExecutionT, CursorT, TargetContextT]):
    """Shared v2 backfill orchestration; connector SQL/payload details live in subclasses."""

    connector: str
    entity_type: str
    log_event_prefix: str
    target_failure_event_suffix = "target_finished"

    @property
    def _logger(self) -> Any:
        return structlog.get_logger(self.__class__.__module__)

    def __init__(
        self,
        *,
        adapter_factory: Callable[..., Awaitable[AdapterT]],
        session_factory: SessionFactory,
        collection_name: str,
    ) -> None:
        self._adapter_factory = adapter_factory
        self._session_factory = session_factory
        self._collection_name = collection_name

    async def backfill_batch(
        self,
        *,
        limit: int,
    ) -> BackfillResult:
        """Run one target batch."""
        targets = await asyncio.to_thread(self._fetch_candidate_targets_sync, limit)
        self._logger.info(
            f"{self.log_event_prefix}_candidate_targets_fetched",
            connector=self.connector,
            entity_type=self.entity_type,
            limit=limit,
            target_count=len(targets),
        )
        target_results = await run_bounded_targets(
            targets,
            concurrency=settings.VECTOR_STORE_V2_BACKFILL_TARGET_CONCURRENCY,
            process_target=self._process_target,
        )
        return BackfillResult(
            scanned=len(targets),
            succeeded=sum(result.succeeded for result in target_results),
            skipped=sum(result.skipped for result in target_results),
            failed=sum(result.failed for result in target_results),
        )

    async def _process_target(self, target: BackfillTarget) -> TargetBackfillResult:
        processing_started_at: datetime | None = None
        try:
            processing_started_at = await asyncio.to_thread(
                self._mark_processing_sync,
                target,
            )
            if processing_started_at is None:
                self._logger.info(
                    f"{self.log_event_prefix}_target_claim_skipped",
                    **self._target_log_context(target),
                    reason="already_processing",
                )
                return TargetBackfillResult(succeeded=0, skipped=1, failed=0)

            self._logger.info(
                f"{self.log_event_prefix}_target_claimed",
                **self._target_log_context(target),
            )

            target_context = await asyncio.to_thread(
                self._load_target_context_sync,
                target,
            )
            adapter = await self._create_adapter_for_target(target)
            hydrate_result = await self._hydrate_target_seed_pages(
                target,
                adapter,
                target_context,
            )

            finish_result = await asyncio.to_thread(
                self._mark_finished_sync,
                target,
                hydrate_result.backfill_count,
                hydrate_result.failed_ids,
                processing_started_at,
                error_type=hydrate_result.error_type,
                error_message=hydrate_result.error_message,
            )
            self._logger.info(
                f"{self.log_event_prefix}_target_finished",
                **self._target_log_context(target),
                state=finish_result.decision.state,
                backfill_count=hydrate_result.backfill_count,
                failed_count=len(hydrate_result.failed_ids),
                failed_ids=hydrate_result.failed_ids,
                error_type=finish_result.decision.error_type,
                error_message=finish_result.decision.error_message,
                finish_persisted=finish_result.persisted,
            )
            if not finish_result.persisted:
                return TargetBackfillResult(
                    succeeded=0,
                    skipped=0,
                    failed=target.pending_count,
                )
            return TargetBackfillResult(
                succeeded=hydrate_result.backfill_count,
                skipped=0,
                failed=count_backfill_completion_failures(
                    pending_count=target.pending_count,
                    backfill_count=hydrate_result.backfill_count,
                    failed_ids=hydrate_result.failed_ids,
                    state=finish_result.decision.state,
                ),
            )
        except Exception as exc:
            try:
                await asyncio.to_thread(
                    self._mark_finished_sync,
                    target,
                    0,
                    [],
                    processing_started_at,
                    force_failed=True,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            except Exception as state_exc:
                self._logger.warning(
                    f"{self.log_event_prefix}_target_state_update_failed",
                    **self._target_log_context(target),
                    original_error_type=type(exc).__name__,
                    original_error_message=str(exc),
                    state_error_type=type(state_exc).__name__,
                    state_error_message=str(state_exc),
                    exc_info=(type(state_exc), state_exc, state_exc.__traceback__),
                )
            self._logger.warning(
                f"{self.log_event_prefix}_{self.target_failure_event_suffix}",
                **self._target_log_context(target),
                state="failed",
                backfill_count=0,
                failed_count=target.pending_count,
                failed_ids=[],
                error_type=type(exc).__name__,
                error_message=str(exc),
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            return TargetBackfillResult(
                succeeded=0,
                skipped=0,
                failed=target.pending_count,
            )

    async def _hydrate_target_seed_pages(
        self,
        target: BackfillTarget,
        adapter: AdapterT,
        target_context: TargetContextT,
    ) -> HydrateTargetResult:
        failed_ids: list[str] = []
        error_types: list[str] = []
        error_messages: list[str] = []
        backfill_count = 0
        cursor: CursorT | None = None
        seed_page_index = 0
        chunk_index = 0

        while True:
            seed_page = await asyncio.to_thread(
                self._fetch_candidate_seed_page_for_target_sync,
                target,
                cursor,
                settings.VECTOR_STORE_V2_BACKFILL_SEED_PAGE_SIZE,
            )
            if not seed_page:
                break

            seed_page_index += 1
            self._logger.info(
                f"{self.log_event_prefix}_v1_seed_page_fetched",
                **self._target_log_context(target),
                seed_page_index=seed_page_index,
                seed_count=len(seed_page),
                seed_page_size=settings.VECTOR_STORE_V2_BACKFILL_SEED_PAGE_SIZE,
                **self._cursor_log_context(cursor),
                last_record_id=seed_page[-1].record_id,
                last_langchain_id=seed_page[-1].langchain_id,
            )

            upserted_seed_count = await asyncio.to_thread(
                self._upsert_seed_rows_sync,
                target,
                seed_page,
            )
            self._logger.info(
                f"{self.log_event_prefix}_seed_rows_upserted",
                **self._target_log_context(target),
                seed_page_index=seed_page_index,
                seed_count=len(seed_page),
                upserted_count=upserted_seed_count,
                seed_insert_batch_size=SEED_INSERT_BATCH_SIZE,
            )
            cursor = self._cursor_from_last_seed(seed_page[-1])

            for seed_chunk in chunked(seed_page, HYDRATE_PIPELINE_BATCH_SIZE):
                chunk_index += 1
                self._logger.info(
                    f"{self.log_event_prefix}_seeded_chunk_started",
                    **self._target_log_context(target),
                    seed_page_index=seed_page_index,
                    chunk_index=chunk_index,
                    seed_count=len(seed_chunk),
                    hydrate_batch_size=HYDRATE_PIPELINE_BATCH_SIZE,
                    last_record_id=seed_chunk[-1].record_id,
                    last_langchain_id=seed_chunk[-1].langchain_id,
                )
                now = datetime.now(timezone.utc)
                result = await run_sync_ingestion(
                    port=adapter,
                    execution=self._build_execution_request(
                        target,
                        seed_chunk,
                        target_context,
                    ),
                    sync_window=SyncWindow(window_start=now, window_end=now),
                )
                chunk_failed_ids = self._failed_ids_from_result(
                    result,
                    seed_chunk,
                )
                chunk_error_type = failure_error_type_from_result(result)
                if chunk_failed_ids and chunk_error_type:
                    error_types.append(chunk_error_type)
                chunk_error_message = failure_error_message_from_result(result)
                if chunk_failed_ids and chunk_error_message:
                    error_messages.append(chunk_error_message)
                failed_ids.extend(chunk_failed_ids)
                backfill_count += result.persisted_count
                self._logger.info(
                    f"{self.log_event_prefix}_seeded_chunk_completed",
                    **self._target_log_context(target),
                    seed_page_index=seed_page_index,
                    chunk_index=chunk_index,
                    seed_count=len(seed_chunk),
                    persisted_count=result.persisted_count,
                    failed_count=len(chunk_failed_ids),
                    failed_ids=chunk_failed_ids,
                    error_type=chunk_error_type,
                    error_message=chunk_error_message,
                )

        return HydrateTargetResult(
            backfill_count=backfill_count,
            failed_ids=failed_ids,
            error_type=combine_failure_error_types(error_types),
            error_message=combine_failure_error_messages(error_messages),
        )

    async def _create_adapter_for_target(self, target: BackfillTarget) -> AdapterT:
        return await self._adapter_factory(target.scope_id)

    def _load_target_context_sync(self, target: BackfillTarget) -> TargetContextT:
        del target
        return None  # type: ignore[return-value]

    def _mark_processing_sync(self, target: BackfillTarget) -> datetime | None:
        with self._session_factory() as db:
            result = db.execute(
                build_mark_processing_statement(),
                {
                    "connector": self.connector,
                    "entity_type": self.entity_type,
                    "scope_id": target.scope_id,
                    "target_id": target.target_id,
                    "expected_count": target.expected_count,
                },
            )
            row = result.first()
            db.commit()
            if row is None:
                return None
            return row[0]

    def _mark_finished_sync(
        self,
        target: BackfillTarget,
        backfill_count: int,
        failed_ids: list[str],
        processing_started_at: datetime | None = None,
        *,
        force_failed: bool = False,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> FinishResult:
        now = datetime.now(timezone.utc)
        decision = decide_backfill_completion(
            pending_count=target.pending_count,
            backfill_count=backfill_count,
            failed_ids=failed_ids,
            force_failed=force_failed,
            error_type=error_type,
            error_message=error_message,
        )
        state = decision.state
        is_failed = state == "failed"
        failure_metadata = build_failure_metadata(
            now,
            error_type=decision.error_type if is_failed else None,
            error_message=decision.error_message if is_failed else None,
        )
        with self._session_factory() as db:
            update_result = db.execute(
                build_mark_finished_statement(),
                {
                    "connector": self.connector,
                    "entity_type": self.entity_type,
                    "scope_id": target.scope_id,
                    "target_id": target.target_id,
                    "state": state,
                    "expected_count": target.expected_count,
                    "backfill_count": backfill_count,
                    "failed_ids": json.dumps(failed_ids),
                    "succeeded_at": now if state == "succeeded" else None,
                    "failed_at": now if is_failed else None,
                    "last_error_type": failure_metadata.last_error_type
                    if is_failed
                    else None,
                    "last_error_message": failure_metadata.last_error_message
                    if is_failed
                    else None,
                    "next_retry_at": failure_metadata.next_retry_at if is_failed else None,
                    "processing_started_at": processing_started_at,
                },
            )
            rowcount = update_result.rowcount
            db.commit()
        persisted = rowcount != 0
        if not persisted:
            self._logger.warning(
                f"{self.log_event_prefix}_target_finish_update_missed",
                **self._target_log_context(target),
                state=state,
                backfill_count=backfill_count,
                failed_count=len(failed_ids),
                processing_started_at=processing_started_at,
            )
        return FinishResult(decision=decision, persisted=persisted)

    def _cursor_from_last_seed(self, seed: BackfillSeed) -> CursorT:
        return BackfillSeedCursor(
            record_id=seed.record_id,
            langchain_id=seed.langchain_id,
        )  # type: ignore[return-value]

    def _cursor_log_context(self, cursor: CursorT | None) -> dict[str, object]:
        return {
            "after_record_id": None if cursor is None else cursor.record_id,  # type: ignore[union-attr]
            "after_langchain_id": None if cursor is None else cursor.langchain_id,  # type: ignore[union-attr]
        }

    def _target_log_context(self, target: BackfillTarget) -> dict[str, object]:
        context: dict[str, object] = {
            "connector": self.connector,
            "entity_type": self.entity_type,
            "scope_id": target.scope_id,
            "target_id": target.target_id,
            "expected_count": target.expected_count,
            "pending_count": target.pending_count,
        }
        if target.target_name is not None:
            context["target_name"] = target.target_name
        return context

    def _failed_ids_from_result(
        self,
        result: SyncExecutionResult,
        seeds: Sequence[BackfillSeed],
    ) -> list[str]:
        return failed_ids_from_result(result, seeds)

    def _fetch_candidate_targets_sync(self, limit: int) -> list[BackfillTarget]:
        """Return backfill targets for this connector."""
        raise NotImplementedError

    def _fetch_candidate_seed_page_for_target_sync(
        self,
        target: BackfillTarget,
        cursor: CursorT | None,
        limit: int,
    ) -> list[BackfillSeed]:
        """Return one cursor page of v1 seed rows for a target."""
        raise NotImplementedError

    def _upsert_seed_rows_sync(
        self,
        target: BackfillTarget,
        seeds: Sequence[BackfillSeed],
    ) -> int:
        """Persist seed rows before hydration."""
        raise NotImplementedError

    def _build_execution_request(
        self,
        target: BackfillTarget,
        seeds: Sequence[BackfillSeed],
        target_context: TargetContextT,
    ) -> ExecutionT:
        """Build connector-specific ingestion execution payload."""
        raise NotImplementedError


def failed_ids_from_result(
    result: SyncExecutionResult,
    seeds: Sequence[BackfillSeed],
) -> list[str]:
    """Return failed seed ids from explicit metadata or failed_count fallback."""
    failed_ids = result.metadata.get("failed_ids")
    if failed_ids is None:
        failed_ids = result.metadata.get("v2_failed_ids")
    if isinstance(failed_ids, list):
        return [str(failed_id) for failed_id in failed_ids]
    if result.failed_count <= 0:
        return []
    seed_ids = [seed.langchain_id for seed in seeds]
    return seed_ids[: result.failed_count]


def failure_error_type_from_result(result: SyncExecutionResult) -> str | None:
    """Return connector-owned failure code for backfill state, when provided."""
    error_type = result.metadata.get("error_type") or result.metadata.get("error_code")
    return str(error_type) if error_type else None


def failure_error_message_from_result(result: SyncExecutionResult) -> str | None:
    error_message = result.metadata.get("error_message")
    return str(error_message) if error_message else None


def combine_failure_error_types(error_types: Sequence[str]) -> str | None:
    distinct_error_types = list(dict.fromkeys(error_types))
    if not distinct_error_types:
        return None
    return ",".join(distinct_error_types)


def combine_failure_error_messages(error_messages: Sequence[str]) -> str | None:
    distinct_error_messages = list(dict.fromkeys(error_messages))
    if not distinct_error_messages:
        return None
    return " | ".join(distinct_error_messages)


def chunked(values: Sequence[Any], size: int) -> list[list[Any]]:
    return [list(batch) for batch in batched(values, size)]


def format_pgvector_embedding(embedding: Sequence[float]) -> str:
    """Format a float sequence for PostgreSQL pgvector input."""
    return f"[{','.join(format(float(value), '.12g') for value in embedding)}]"


def embedding_to_list(value: Any) -> list[float]:
    """Normalize a stored embedding value to list[float]."""
    if not value:
        return []
    if isinstance(value, str):
        return json.loads(value) if value.strip() else []
    return list(value)
