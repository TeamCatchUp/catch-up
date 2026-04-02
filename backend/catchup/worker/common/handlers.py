from __future__ import annotations

from catchup.sync.common.protocols import IngestionHandlerProtocol
from catchup.sync.common.schemas import SyncContext
from catchup.worker.handlers import get_ingestion_handler


def select_handler(context: SyncContext) -> IngestionHandlerProtocol | None:
    return get_ingestion_handler(
        connector=context.connector,
        sync_type=context.sync_type,
    )