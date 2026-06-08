from __future__ import annotations

from catchup.db.models import SyncConnector
from catchup.db.models import SyncType
from catchup.sync.common.protocols import IngestionHandlerProtocol
from catchup.sync.common.schemas import HandlerKey
from catchup.sync.common.schemas import SyncContext
from catchup.sync.handlers.channel_talk import ChannelTalkFullSyncHandler
from catchup.sync.handlers.confluence import ConfluenceFullSyncHandler
from catchup.sync.handlers.github import GithubFullSyncHandler
from catchup.sync.handlers.jira import JiraFullSyncHandler
from catchup.sync.handlers.slack import SlackFullSyncHandler
from catchup.sync.handlers.slack import SlackIncrementalHandler
from catchup.worker.handlers.channel_talk_incremental_handler import (
    ChannelTalkIncrementalHandler,
)
from catchup.worker.handlers.confluence_incremental_handler import (
    ConfluenceIncrementalHandler,
)
from catchup.worker.handlers.github_incremental_handler import GithubIncrementalHandler
from catchup.worker.handlers.jira_incremental_handler import JiraIncrementalHandler

_HANDLERS: dict[HandlerKey, IngestionHandlerProtocol] | None = None


def get_ingestion_handler(
    *,
    connector: SyncConnector | str,
    sync_type: SyncType | str,
) -> IngestionHandlerProtocol | None:
    return _handler_registry().get(
        HandlerKey.of(
            connector=connector,
            sync_type=sync_type,
        )
    )


def select_handler(context: SyncContext) -> IngestionHandlerProtocol | None:
    return get_ingestion_handler(
        connector=context.connector,
        sync_type=context.sync_type,
    )


def _handler_registry() -> dict[HandlerKey, IngestionHandlerProtocol]:
    global _HANDLERS
    if _HANDLERS is None:
        _HANDLERS = _build_handler_registry()
    return _HANDLERS


def _build_handler_registry() -> dict[HandlerKey, IngestionHandlerProtocol]:
    return {
        HandlerKey.of(
            connector=SyncConnector.SLACK,
            sync_type=SyncType.FULL,
        ): SlackFullSyncHandler(),
        HandlerKey.of(
            connector=SyncConnector.SLACK,
            sync_type=SyncType.INCREMENTAL,
        ): SlackIncrementalHandler(),
        HandlerKey.of(
            connector=SyncConnector.GITHUB,
            sync_type=SyncType.FULL,
        ): GithubFullSyncHandler(),
        HandlerKey.of(
            connector=SyncConnector.GITHUB,
            sync_type=SyncType.INCREMENTAL,
        ): GithubIncrementalHandler(),
        HandlerKey.of(
            connector=SyncConnector.JIRA,
            sync_type=SyncType.FULL,
        ): JiraFullSyncHandler(),
        HandlerKey.of(
            connector=SyncConnector.JIRA,
            sync_type=SyncType.INCREMENTAL,
        ): JiraIncrementalHandler(),
        HandlerKey.of(
            connector=SyncConnector.CONFLUENCE,
            sync_type=SyncType.FULL,
        ): ConfluenceFullSyncHandler(),
        HandlerKey.of(
            connector=SyncConnector.CONFLUENCE,
            sync_type=SyncType.INCREMENTAL,
        ): ConfluenceIncrementalHandler(),
        HandlerKey.of(
            connector=SyncConnector.CHANNEL_TALK,
            sync_type=SyncType.FULL,
        ): ChannelTalkFullSyncHandler(),
        HandlerKey.of(
            connector=SyncConnector.CHANNEL_TALK,
            sync_type=SyncType.INCREMENTAL,
        ): ChannelTalkIncrementalHandler(),
    }


__all__ = [
    "get_ingestion_handler",
    "select_handler",
]
