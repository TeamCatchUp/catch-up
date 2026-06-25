from __future__ import annotations

from functools import lru_cache

from catchup.db.models import SyncConnector
from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.repair.channel_talk_record_repair_service import (
    get_channel_talk_record_repair_service,
)
from catchup.sync.repair.confluence_record_repair_service import (
    get_confluence_record_repair_service,
)
from catchup.sync.repair.github_record_repair_service import (
    get_github_record_repair_service,
)
from catchup.sync.repair.jira_record_repair_service import (
    get_jira_record_repair_service,
)
from catchup.sync.repair.protocols import RecordRepairHandler
from catchup.sync.repair.slack_record_repair_service import (
    get_slack_record_repair_service,
)


class RecordRepairHandlerRegistry:
    """Registry for connector-specific repair handlers."""

    def __init__(
        self,
        *,
        handlers: dict[SyncConnector, RecordRepairHandler],
    ) -> None:
        self._handlers = dict(handlers)

    def handler_for(
        self,
        connector: SyncConnector,
    ) -> RecordRepairHandler:
        try:
            return self._handlers[connector]
        except KeyError as exc:
            raise SyncRequestException(
                "record repair not supported for this connector",
                code="unsupported_connector",
                metadata={"connector": connector.value},
            ) from exc


@lru_cache(maxsize=1)
def get_record_repair_handler_registry() -> RecordRepairHandlerRegistry:
    return RecordRepairHandlerRegistry(
        handlers={
            SyncConnector.CHANNEL_TALK: get_channel_talk_record_repair_service(),
            SyncConnector.CONFLUENCE: get_confluence_record_repair_service(),
            SyncConnector.GITHUB: get_github_record_repair_service(),
            SyncConnector.JIRA: get_jira_record_repair_service(),
            SyncConnector.SLACK: get_slack_record_repair_service(),
        }
    )
