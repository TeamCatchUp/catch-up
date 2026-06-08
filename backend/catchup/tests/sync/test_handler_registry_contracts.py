from __future__ import annotations

from catchup.db.models import SyncConnector
from catchup.db.models import SyncType
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import SyncTargetType
from catchup.sync.handlers.channel_talk import ChannelTalkIncrementalHandler
from catchup.sync.handlers.confluence import ConfluenceIncrementalHandler
from catchup.sync.handlers.github import GithubIncrementalHandler
from catchup.sync.handlers.jira import JiraIncrementalHandler
from catchup.sync.handlers.registry import get_ingestion_handler
from catchup.sync.handlers.registry import select_handler
from catchup.sync.handlers.slack import SlackIncrementalHandler


def test_handler_registry_includes_full_and_incremental_handlers() -> None:
    for connector in SyncConnector:
        assert get_ingestion_handler(
            connector=connector,
            sync_type=SyncType.FULL,
        ) is not None
        assert get_ingestion_handler(
            connector=connector,
            sync_type=SyncType.INCREMENTAL,
        ) is not None


def test_select_handler_resolves_from_sync_context() -> None:
    context = FullSyncContext(
        event_id="event-123",
        job_id="job-123",
        connector=SyncConnector.SLACK,
        scope_id="team-123",
        target_type=SyncTargetType.CHANNEL,
        target_id="channel-123",
        target_name="general",
        sync_from_ts="2026-05-08T05:00:00+00:00",
        attempt=0,
        max_attempts=3,
    )

    handler = select_handler(context)

    assert handler is get_ingestion_handler(
        connector=SyncConnector.SLACK,
        sync_type=SyncType.FULL,
    )


def test_incremental_handlers_resolve_to_canonical_sync_handlers() -> None:
    expected_types = {
        SyncConnector.SLACK: SlackIncrementalHandler,
        SyncConnector.GITHUB: GithubIncrementalHandler,
        SyncConnector.JIRA: JiraIncrementalHandler,
        SyncConnector.CONFLUENCE: ConfluenceIncrementalHandler,
        SyncConnector.CHANNEL_TALK: ChannelTalkIncrementalHandler,
    }

    for connector, expected_type in expected_types.items():
        handler = get_ingestion_handler(
            connector=connector,
            sync_type=SyncType.INCREMENTAL,
        )

        assert isinstance(handler, expected_type)
