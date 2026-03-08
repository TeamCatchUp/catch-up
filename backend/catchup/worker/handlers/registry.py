from __future__ import annotations

from catchup.sync.common.protocols import IngestionHandlerProtocol
from catchup.worker.handlers.confluence_full_sync_handler import (
    ConfluenceFullSyncHandler,
)
from catchup.worker.handlers.github_full_sync_handler import GithubFullSyncHandler
from catchup.worker.handlers.jira_full_sync_handler import JiraFullSyncHandler
from catchup.worker.handlers.slack_full_sync_handler import SlackFullSyncHandler

_HANDLERS: dict[tuple[str, str], IngestionHandlerProtocol] = {
    ("slack", "full"): SlackFullSyncHandler(),
    ("github", "full"): GithubFullSyncHandler(),
    ("jira", "full"): JiraFullSyncHandler(),
    ("confluence", "full"): ConfluenceFullSyncHandler(),
}


def get_ingestion_handler(
    *,
    connector: str,
    sync_type: str,
) -> IngestionHandlerProtocol | None:
    return _HANDLERS.get((connector, sync_type))
