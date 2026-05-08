from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Sized
from enum import Enum
from functools import wraps
from time import perf_counter
from typing import Any
from typing import TypeVar

import structlog

from catchup.connector_core.ports.sync_ingestion import SyncExecutionRequest
from catchup.connector_core.ports.sync_ingestion import SyncWindow

logger = structlog.get_logger(__name__)

ExecutionResultT = TypeVar("ExecutionResultT")

_SCALAR_STAGE_FIELDS = (
    "fetched_count",
    "collected_count",
    "document_count",
    "persisted_count",
    "error_count",
    "summary_applied",
    "included_message_count",
    "excluded_message_count",
)
_SIZED_STAGE_FIELDS = {
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

    @wraps(run_sync_ingestion)
    async def wrapped(*args: Any, **kwargs: Any) -> ExecutionResultT:
        execution = kwargs["execution"]
        sync_window = kwargs["sync_window"]
        context = _build_log_context(
            execution=execution,
            sync_window=sync_window,
        )
        state = _PipelineLogState()
        pipeline_started_at = perf_counter()

        logger.info("sync_ingestion_pipeline_started", **context)
        # SyncIngestionPort를 _SyncIngestionLoggingPort으로 교체
        kwargs["port"] = _SyncIngestionLoggingPort(
            port=kwargs["port"],
            context=context,
            state=state,
        )

        try:
            result = await run_sync_ingestion(*args, **kwargs)
        except Exception as exc:
            # proxy가 실제 port 메서드를 호출하기 직전에 `state.stage`를 갱신한다.
            # 덕분에 실패가 어느 단계에서 발생했는지 pipeline 실패 로그에 담을 수 있다.
            logger.warning(
                "sync_ingestion_pipeline_failed",
                **context,
                stage=state.stage,
                duration_ms=_duration_ms(pipeline_started_at),
                error_type=type(exc).__name__,
                error_message=str(exc),
                exc_info=True,
            )
            raise

        logger.info(
            "sync_ingestion_pipeline_completed",
            **context,
            duration_ms=_duration_ms(pipeline_started_at),
            **_summarize_stage_result(result),
        )
        return result

    return wrapped


class _PipelineLogState:
    def __init__(self) -> None:
        self.stage = "start"


class _SyncIngestionLoggingPort:
    """Stage 단위의 로그만 추가하는 Logging Proxy"""

    def __init__(
        self,
        *,
        port: Any,
        context: dict[str, object],
        state: _PipelineLogState,
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
            "sync_ingestion_stage_completed",
            **self._context,
            stage=stage,
            duration_ms=_duration_ms(stage_started_at),
            **_summarize_stage_result(result),
        )


def _log_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    return value


def _duration_ms(started_at: float) -> int:
    return max(0, int((perf_counter() - started_at) * 1000))


def _build_log_context(
    *,
    execution: SyncExecutionRequest,
    sync_window: SyncWindow,
) -> dict[str, object]:
    context: dict[str, object] = {
        "connector": _log_value(execution.connector),
        "tenant_id": execution.tenant_id,
        "target": execution.target,
        "sync_window_start": sync_window.window_start.isoformat(),
        "sync_window_end": sync_window.window_end.isoformat(),
    }

    audit_context = getattr(execution, "audit_context", None)
    if audit_context is not None:
        for field_name in ("scope_id", "target_id", "job_id", "task_id"):
            value = getattr(audit_context, field_name, None)
            if value is not None:
                context[field_name] = _log_value(value)

    return context


def _summarize_stage_result(result: object) -> dict[str, object]:
    summary: dict[str, object] = {}

    for field_name in _SCALAR_STAGE_FIELDS:
        value = getattr(result, field_name, None)
        if isinstance(value, (str, int, float, bool)):
            summary[field_name] = value

    for source_field, target_field in _SIZED_STAGE_FIELDS.items():
        value = getattr(result, source_field, None)
        if not isinstance(value, Sized) or isinstance(value, (str, bytes, bytearray)):
            continue
        summary[target_field] = len(value)

    return summary
