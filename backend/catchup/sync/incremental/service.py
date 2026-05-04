from __future__ import annotations

from functools import lru_cache

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.audit.actions import SyncTriggerAction
from catchup.audit.metadata import IncrementalSyncTriggerMetadata
from catchup.audit.utils import audit_log
from catchup.db.models import SyncConnector
from catchup.sync.incremental.persist import persist_incremental_changes
from catchup.sync.incremental.promoter import promote_incremental_records
from catchup.sync.incremental.publisher import publish_incremental_outbox
from catchup.sync.incremental.schemas import IncrementalIngestResult
from catchup.sync.incremental.schemas import RecordChange

logger = structlog.get_logger(__name__)


class IncrementalService:
    
    @audit_log(
        SyncTriggerAction.INCREMENTAL,
        metadata_factory=IncrementalSyncTriggerMetadata.from_audit,
        emit_attempt=True,
    )
    async def dispatch_changes(
        self,
        *,
        changes: list[RecordChange],
    ) -> IncrementalIngestResult:
        result = await run_in_threadpool(
            persist_incremental_changes,
            changes,
        )
        return result

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

    async def poll_channel_talk_document_changes(self) -> dict[str, int]:
        from catchup.sync.incremental.poll.channel_talk import (
            poll_channel_talk_document_incremental_changes,
        )

        return await poll_channel_talk_document_incremental_changes()


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
