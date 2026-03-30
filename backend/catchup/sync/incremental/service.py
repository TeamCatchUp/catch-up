from __future__ import annotations

from functools import lru_cache

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.audit.enums import AuditEventStatus
from catchup.audit.enums import AuditLevel
from catchup.db.models import SyncConnector
from catchup.events.enums import SyncTriggerEventAction
from catchup.sync.audit import SyncAuditContext
from catchup.sync.audit import emit_sync_trigger_audit
from catchup.sync.incremental.persist import persist_incremental_changes
from catchup.sync.incremental.promoter import promote_incremental_records
from catchup.sync.incremental.publisher import publish_incremental_outbox
from catchup.sync.incremental.schemas import IncrementalIngestResult
from catchup.sync.incremental.schemas import RecordChange

logger = structlog.get_logger(__name__)


class IncrementalService:
    def _dispatch_changes_sync(
        self,
        *,
        changes: list[RecordChange],
        event_name: str,
        context_name: str = "event_name",
        action: SyncTriggerEventAction = SyncTriggerEventAction.WEBHOOK_EVENT_RECEIVED,
    ) -> IncrementalIngestResult:
        try:
            result = persist_incremental_changes(changes)
        except Exception as exc:
            if changes:
                first_change = changes[0]
                audit_context = SyncAuditContext(
                    connector=first_change.connector,
                    scope_id=first_change.scope_id,
                    target_id=first_change.parent_id,
                )
                emit_sync_trigger_audit(
                    action=action,
                    status=AuditEventStatus.FAIL,
                    audit_context=audit_context,
                    context=(
                        f"stage=incremental_dispatch_failed,{context_name}={event_name},"
                        f"event_kind={first_change.event_kind},error={str(exc).strip()[:200]}"
                    ),
                    level=AuditLevel.ERROR,
                )
            raise

        if result.first_allowed_change is not None:
            first_change = result.first_allowed_change
            audit_context = SyncAuditContext(
                connector=first_change.connector,
                scope_id=first_change.scope_id,
                target_id=first_change.parent_id,
            )
            emit_sync_trigger_audit(
                action=action,
                status=AuditEventStatus.ATTEMPT,
                audit_context=audit_context,
                context=(
                    f"stage=incremental_dispatch,{context_name}={event_name},"
                    f"event_kind={first_change.event_kind},change_count={len(result.record_keys)}"
                ),
            )
            emit_sync_trigger_audit(
                action=action,
                status=AuditEventStatus.SUCCESS,
                audit_context=audit_context,
                context=(
                    f"stage=incremental_dispatched,{context_name}={event_name},"
                    f"record_key_count={len(result.record_keys)},blocked_count={result.blocked_count}"
                ),
            )
        return result

    async def dispatch_changes(
        self,
        *,
        changes: list[RecordChange],
        event_name: str,
        context_name: str = "event_name",
        action: SyncTriggerEventAction = SyncTriggerEventAction.WEBHOOK_EVENT_RECEIVED,
    ) -> IncrementalIngestResult:
        return await run_in_threadpool(
            self._dispatch_changes_sync,
            changes=changes,
            event_name=event_name,
            context_name=context_name,
            action=action,
        )

    def promote_records(
        self,
        *,
        connector: SyncConnector | None = None,
        limit: int | None = None,
    ) -> dict[str, int]:
        return promote_incremental_records(
            connector=connector,
            limit=limit,
        )

    async def publish_outbox(
        self,
        *,
        connector: SyncConnector | None = None,
        limit: int | None = None,
    ) -> dict[str, int]:
        return await publish_incremental_outbox(
            connector=connector,
            limit=limit,
        )

    async def poll_confluence_changes(self) -> dict[str, int]:
        from catchup.sync.incremental.poll.confluence import (
            poll_confluence_incremental_changes,
        )

        return await poll_confluence_incremental_changes()


def create_incremental_service() -> IncrementalService:
    return IncrementalService()


@lru_cache(maxsize=1)
def get_incremental_service() -> IncrementalService:
    try:
        return create_incremental_service()
    except Exception as exc:
        logger.error(
            "incremental_service_init_failed",
            error=str(exc),
            exc_info=True,
        )
        raise
