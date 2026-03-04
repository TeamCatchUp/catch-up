from __future__ import annotations

from catchup.sync.common.protocols import IngestionHandlerProtocol
from catchup.worker.handlers.slack_full_sync_handler import SlackSyncHandler

_HANDLERS: dict[tuple[str, str], IngestionHandlerProtocol] = {
    ("slack", "full"): SlackSyncHandler(),
}


def get_ingestion_handler(
    *,
    connector: str,
    sync_type: str,
) -> IngestionHandlerProtocol | None:
    return _HANDLERS.get((connector, sync_type))
