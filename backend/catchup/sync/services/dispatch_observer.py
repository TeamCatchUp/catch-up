from __future__ import annotations

from typing import Protocol, Sequence

from catchup.audit.enums import AuditEventStatus, AuditLevel
from catchup.db.models import SyncConnector, SyncType
from catchup.events.enums import SyncTriggerEventAction
from catchup.sync.audit import SyncAuditContext, emit_sync_trigger_audit
from catchup.sync.common.schemas import SyncEventSeed
from catchup.sync.dispatch.types import DispatchContext


class SyncDispatchObserver(Protocol):
    def on_dispatch_requested(
        self,
        *,
        context: DispatchContext,
        trigger: str,
        event_seeds: Sequence[SyncEventSeed],
    ) -> None: ...

    def on_db_persisted(
        self,
        *,
        context: DispatchContext,
        trigger: str,
        event_seeds: Sequence[SyncEventSeed],
    ) -> None: ...

    def on_db_persist_failed(
        self,
        *,
        context: DispatchContext,
        trigger: str,
        event_seeds: Sequence[SyncEventSeed],
        error: Exception,
    ) -> None: ...

    def on_stream_published(
        self,
        *,
        context: DispatchContext,
        trigger: str,
        target_count: int,
        published_count: int,
    ) -> None: ...

    def on_stream_publish_failed(
        self,
        *,
        context: DispatchContext,
        trigger: str,
        target_count: int,
        error: Exception | None = None,
        requested_count: int | None = None,
        published_count: int | None = None,
    ) -> None: ...


class NullSyncDispatchObserver:
    def on_dispatch_requested(
        self,
        *,
        context: DispatchContext,
        trigger: str,
        event_seeds: Sequence[SyncEventSeed],
    ) -> None:
        return None

    def on_db_persisted(
        self,
        *,
        context: DispatchContext,
        trigger: str,
        event_seeds: Sequence[SyncEventSeed],
    ) -> None:
        return None

    def on_db_persist_failed(
        self,
        *,
        context: DispatchContext,
        trigger: str,
        event_seeds: Sequence[SyncEventSeed],
        error: Exception,
    ) -> None:
        return None

    def on_stream_published(
        self,
        *,
        context: DispatchContext,
        trigger: str,
        target_count: int,
        published_count: int,
    ) -> None:
        return None

    def on_stream_publish_failed(
        self,
        *,
        context: DispatchContext,
        trigger: str,
        target_count: int,
        error: Exception | None = None,
        requested_count: int | None = None,
        published_count: int | None = None,
    ) -> None:
        return None


class FullSyncDispatchObserver(NullSyncDispatchObserver):
    def on_dispatch_requested(
        self,
        *,
        context: DispatchContext,
        trigger: str,
        event_seeds: Sequence[SyncEventSeed],
    ) -> None:
        self._emit(
            status=AuditEventStatus.ATTEMPT,
            context=context,
            context_text=f"stage=dispatch_requested,trigger={trigger},target_count={len(event_seeds)}",
        )

    def on_db_persisted(
        self,
        *,
        context: DispatchContext,
        trigger: str,
        event_seeds: Sequence[SyncEventSeed],
    ) -> None:
        self._emit(
            status=AuditEventStatus.SUCCESS,
            context=context,
            context_text=f"stage=db_persisted,trigger={trigger},target_count={len(event_seeds)}",
        )

    def on_db_persist_failed(
        self,
        *,
        context: DispatchContext,
        trigger: str,
        event_seeds: Sequence[SyncEventSeed],
        error: Exception,
    ) -> None:
        self._emit(
            status=AuditEventStatus.FAIL,
            context=context,
            context_text=(
                f"stage=db_persist_failed,trigger={trigger},"
                f"target_count={len(event_seeds)},error={_truncate_error(error)}"
            ),
            level=AuditLevel.ERROR,
        )

    def on_stream_published(
        self,
        *,
        context: DispatchContext,
        trigger: str,
        target_count: int,
        published_count: int,
    ) -> None:
        self._emit(
            status=AuditEventStatus.SUCCESS,
            context=context,
            context_text=(
                f"stage=stream_published,trigger={trigger},"
                f"target_count={target_count},published_count={published_count}"
            ),
        )

    def on_stream_publish_failed(
        self,
        *,
        context: DispatchContext,
        trigger: str,
        target_count: int,
        error: Exception | None = None,
        requested_count: int | None = None,
        published_count: int | None = None,
    ) -> None:
        parts = [f"stage=stream_publish_failed", f"trigger={trigger}", f"target_count={target_count}"]
        if requested_count is not None:
            parts.append(f"requested_count={requested_count}")
        if published_count is not None:
            parts.append(f"published_count={published_count}")
        if error is not None:
            parts.append(f"error={_truncate_error(error)}")
        self._emit(
            status=AuditEventStatus.FAIL,
            context=context,
            context_text=",".join(parts),
            level=AuditLevel.ERROR,
        )

    def _emit(
        self,
        *,
        status: AuditEventStatus,
        context: DispatchContext,
        context_text: str,
        level: AuditLevel = AuditLevel.INFO,
    ) -> None:
        emit_sync_trigger_audit(
            action=SyncTriggerEventAction.FULL_SYNC_REQUESTED,
            status=status,
            audit_context=SyncAuditContext(
                connector=context.connector,
                scope_id=context.scope_id,
                job_id=context.job_id,
            ),
            context=context_text,
            level=level,
        )


def resolve_sync_dispatch_observer(
    *,
    connector: SyncConnector,
    sync_type: SyncType,
) -> SyncDispatchObserver:
    if sync_type == SyncType.FULL:
        return FullSyncDispatchObserver()
    return NullSyncDispatchObserver()


def _truncate_error(error: Exception) -> str:
    return str(error).strip()[:200] or error.__class__.__name__
