from __future__ import annotations

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from catchup.db.models import SyncConnector
from catchup.sync.query_service import SyncQueryService


class SyncQueryServiceDispatchTests(IsolatedAsyncioTestCase):
    async def test_list_targets_realtime_keeps_existing_connector_dispatch_and_adds_channel_talk(self) -> None:
        service = SyncQueryService()

        expectations = {
            SyncConnector.GITHUB: "_list_github_targets",
            SyncConnector.JIRA: "_list_jira_targets",
            SyncConnector.CONFLUENCE: "_list_confluence_targets",
            SyncConnector.SLACK: "_list_slack_targets",
            SyncConnector.CHANNEL_TALK: "_list_channel_talk_targets",
        }

        for connector, method_name in expectations.items():
            sentinel = object()
            for candidate_name in expectations.values():
                setattr(service, candidate_name, AsyncMock(side_effect=AssertionError(candidate_name)))
            selected = AsyncMock(return_value=sentinel)
            setattr(service, method_name, selected)

            result = await service._list_targets_realtime(
                connector=connector,
                scope_id="scope-123",
            )

            self.assertIs(result, sentinel)
            selected.assert_awaited_once_with(scope_id="scope-123")
