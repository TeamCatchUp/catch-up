from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from catchup.db.models import SyncConnector
from catchup.sync.contracts import (
    FullSyncDispatchCommand,
    IncrementalSyncDispatchCommand,
    SyncDispatchResult,
)
from catchup.sync.registry import get_connector_sync_service

logger = logging.getLogger(__name__)


class SyncDispatchService:
    async def dispatch_full_sync(
        self,
        *,
        db: Session,
        connector: SyncConnector,
        command: FullSyncDispatchCommand,
        base_url: str | None,
    ) -> SyncDispatchResult:
        """
        공통 Full Sync 디스패치
        """
        service = get_connector_sync_service(connector)

        logger.info(
            "[SYNC][FULL SYNC][DISPATCH] Dispatching request: connector=%s, scope_id=%s, target_count=%s, sync_days=%s",
            connector,
            command.scope_id,
            len(command.target_ids) if command.target_ids else 0,
            command.sync_days,
        )

        return await service.dispatch_full_sync(
            db=db,
            command=command,
            base_url=base_url,
        )

    async def dispatch_incremental_sync(
        self,
        *,
        db: Session,
        connector: SyncConnector,
        command: IncrementalSyncDispatchCommand,
        base_url: str | None,
    ) -> SyncDispatchResult:
        """
        공통 Incremental Sync 디스패치
        """
        service = get_connector_sync_service(connector)

        logger.info(
            "[SYNC][INCREMENTAL SYNC][DISPATCH] Dispatching request: connector=%s, scope_id=%s, target_count=%s",
            connector,
            command.scope_id,
            len(command.target_ids) if command.target_ids else 0,
        )

        return await service.dispatch_incremental_sync(
            db=db,
            command=command,
            base_url=base_url,
        )


_sync_dispatch_service = SyncDispatchService()


def get_sync_dispatch_service() -> SyncDispatchService:
    return _sync_dispatch_service
