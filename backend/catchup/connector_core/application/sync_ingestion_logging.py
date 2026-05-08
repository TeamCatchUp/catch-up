from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import Sized
from enum import Enum
from functools import wraps
from time import perf_counter
from typing import Any
from typing import TypeVar

import structlog

from catchup.connector_core.ports.sync_ingestion import ConnectorLogSummaryProvider
from catchup.connector_core.ports.sync_ingestion import SyncExecutionRequest
from catchup.connector_core.ports.sync_ingestion import SyncWindow

logger = structlog.get_logger(__name__)

ExecutionResultT = TypeVar("ExecutionResultT")

_PIPELINE_STARTED_EVENT = "sync_ingestion_pipeline_started"
_PIPELINE_COMPLETED_EVENT = "sync_ingestion_pipeline_completed"
_PIPELINE_FAILED_EVENT = "sync_ingestion_pipeline_failed"
_STAGE_COMPLETED_EVENT = "sync_ingestion_stage_completed"
_INITIAL_STAGE = "start"

_SCALAR_STAGE_RESULT_FIELDS = (
    "fetched_count",
    "collected_count",
    "document_count",
    "persisted_count",
    "error_count",
    "summary_applied",
    "included_message_count",
    "excluded_message_count",
)
_SIZED_STAGE_RESULT_FIELDS = {
    "bundles": "bundles_count",
    "documents": "documents_count",
    "persisted_ids": "persisted_ids_count",
    "fetched_record_ids": "fetched_record_ids_count",
    "fetched_article_ids": "fetched_article_ids_count",
    "prepared_document_ids": "prepared_document_ids_count",
    "deleted_prefixes": "deleted_prefixes_count",
    "managers_by_id": "managers_count",
}


def sync_ingestion_system_log(
    run_sync_ingestion: Callable[..., Awaitable[ExecutionResultT]],
) -> Callable[..., Awaitable[ExecutionResultT]]:
    """Decorate sync ingestion with shared pipeline and stage logs."""

    @wraps(run_sync_ingestion)
    async def wrapped(*args: Any, **kwargs: Any) -> ExecutionResultT:
        execution = kwargs["execution"]
        sync_window = kwargs["sync_window"]
        context = _build_pipeline_log_context(
            execution=execution,
            sync_window=sync_window,
        )
        state = _PipelineStageLogState()
        pipeline_started_at = perf_counter()

        logger.info(_PIPELINE_STARTED_EVENT, **context)
        kwargs["port"] = _SyncIngestionStageLoggingProxy(
            port=kwargs["port"],
            context=context,
            state=state,
        )

        try:
            result = await run_sync_ingestion(*args, **kwargs)
        except Exception as exc:
            logger.warning(
                _PIPELINE_FAILED_EVENT,
                **context,
                stage=state.stage,
                duration_ms=_duration_ms(pipeline_started_at),
                error_type=type(exc).__name__,
                error_message=str(exc),
                exc_info=True,
            )
            raise

        logger.info(
            _PIPELINE_COMPLETED_EVENT,
            **context,
            duration_ms=_duration_ms(pipeline_started_at),
            **_build_stage_result_log_fields(result),
        )
        return result

    return wrapped


class _PipelineStageLogState:
    def __init__(self) -> None:
        self.stage = _INITIAL_STAGE


class _SyncIngestionStageLoggingProxy:
    """Proxy that adds logs around each Sync Ingestion pipeline stage."""

    def __init__(
        self,
        *,
        port: Any,
        context: dict[str, object],
        state: _PipelineStageLogState,
    ) -> None:
        self._port = port
        self._context = context
        self._state = state

    async def fetch(self, **kwargs: Any) -> Any:
        return await self._run_async_stage(
            "fetch",
            self._port.fetch,
            **kwargs,
        )

    async def transform(self, **kwargs: Any) -> Any:
        return await self._run_async_stage(
            "transform",
            self._port.transform,
            **kwargs,
        )

    async def summarize(self, **kwargs: Any) -> Any:
        return await self._run_async_stage(
            "summarize",
            self._port.summarize,
            **kwargs,
        )

    async def persist(self, **kwargs: Any) -> Any:
        return await self._run_async_stage(
            "persist",
            self._port.persist,
            **kwargs,
        )

    def build_result(self, **kwargs: Any) -> Any:
        self._state.stage = "build_result"
        stage_started_at = perf_counter()
        result = self._port.build_result(**kwargs)
        self._log_stage_completed(
            stage="build_result",
            stage_started_at=stage_started_at,
            result=result,
        )
        return result

    async def _run_async_stage(
        self,
        stage: str,
        stage_call: Callable[..., Awaitable[Any]],
        **kwargs: Any,
    ) -> Any:
        self._state.stage = stage
        stage_started_at = perf_counter()
        result = await stage_call(**kwargs)
        self._log_stage_completed(
            stage=stage,
            stage_started_at=stage_started_at,
            result=result,
        )
        return result

    def _log_stage_completed(
        self,
        *,
        stage: str,
        stage_started_at: float,
        result: object,
    ) -> None:
        logger.info(
            _STAGE_COMPLETED_EVENT,
            **self._context,
            stage=stage,
            duration_ms=_duration_ms(stage_started_at),
            **_build_stage_result_log_fields(result),
        )


def _log_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    return value


def _duration_ms(started_at: float) -> int:
    return max(0, int((perf_counter() - started_at) * 1000))


def _build_pipeline_log_context(
    *,
    execution: SyncExecutionRequest,
    sync_window: SyncWindow,
) -> dict[str, object]:
    context: dict[str, object] = {
        "connector_type": _log_value(execution.connector),
        "tenant_id": execution.tenant_id,
        "target": execution.target,
        "sync_window_start": sync_window.window_start.isoformat(),
        "sync_window_end": sync_window.window_end.isoformat(),
    }

    for key, value in execution.log_context().items():
        context[key] = _log_value(value)

    audit_context = getattr(execution, "audit_context", None)
    if audit_context is not None:
        for field_name in ("scope_id", "target_id", "job_id", "task_id"):
            value = getattr(audit_context, field_name, None)
            if value is not None:
                context[field_name] = _log_value(value)

    return context


def _build_stage_result_log_fields(result: object) -> dict[str, object]:
    summary: dict[str, object] = {}

    if isinstance(result, ConnectorLogSummaryProvider):
        _add_scalar_log_fields(summary, result.connector_log_summary())

    for field_name in _SCALAR_STAGE_RESULT_FIELDS:
        value = getattr(result, field_name, None)
        if isinstance(value, (str, int, float, bool)):
            summary[field_name] = value

    for source_field, target_field in _SIZED_STAGE_RESULT_FIELDS.items():
        value = getattr(result, source_field, None)
        if not isinstance(value, Sized) or isinstance(value, (str, bytes, bytearray)):
            continue
        summary[target_field] = len(value)

    return summary


def _add_scalar_log_fields(
    target: dict[str, object],
    fields: object,
) -> None:
    if not isinstance(fields, Mapping):
        return

    for key, value in fields.items():
        if isinstance(value, (str, int, float, bool)):
            target[key] = value
