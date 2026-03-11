from __future__ import annotations

from catchup.sync.common.protocols import IngestionHandlerProtocol
from catchup.worker.handlers.confluence_full_sync_handler import (
    ConfluenceFullSyncHandler,
)
from catchup.worker.handlers.confluence_incremental_handler import (
    ConfluenceIncrementalHandler,
)
from catchup.worker.handlers.github_full_sync_handler import GithubFullSyncHandler
from catchup.worker.handlers.github_incremental_handler import GithubIncrementalHandler
from catchup.worker.handlers.jira_full_sync_handler import JiraFullSyncHandler
from catchup.worker.handlers.jira_incremental_handler import JiraIncrementalHandler
from catchup.worker.handlers.slack_full_sync_handler import SlackFullSyncHandler
from catchup.worker.handlers.slack_incremental_handler import SlackIncrementalHandler

_HANDLERS: dict[tuple[str, str], IngestionHandlerProtocol] = {
    ("slack", "full"): SlackFullSyncHandler(),
    ("slack", "incremental"): SlackIncrementalHandler(),
    ("github", "full"): GithubFullSyncHandler(),
    ("github", "incremental"): GithubIncrementalHandler(),
    ("jira", "full"): JiraFullSyncHandler(),
    ("jira", "incremental"): JiraIncrementalHandler(),
    ("confluence", "full"): ConfluenceFullSyncHandler(),
    ("confluence", "incremental"): ConfluenceIncrementalHandler(),
}


def get_ingestion_handler(
    *,
    connector: str,
    sync_type: str,
) -> IngestionHandlerProtocol | None:
    return _HANDLERS.get((connector, sync_type))
