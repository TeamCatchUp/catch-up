from __future__ import annotations

from catchup.db.models import SyncConnector
from catchup.sync.common.exceptions import SyncRequestError
from catchup.sync.common.protocols import FullSyncTargetResolverProtocol
from catchup.sync.services import (
    get_confluence_full_sync_target_resolver,
    get_github_full_sync_target_resolver,
    get_jira_full_sync_target_resolver,
    get_slack_full_sync_target_resolver,
)

_FULL_SYNC_TARGET_RESOLVERS: dict[SyncConnector, FullSyncTargetResolverProtocol] = {
    SyncConnector.SLACK: get_slack_full_sync_target_resolver(),
    SyncConnector.GITHUB: get_github_full_sync_target_resolver(),
    SyncConnector.CONFLUENCE: get_confluence_full_sync_target_resolver(),
    SyncConnector.JIRA: get_jira_full_sync_target_resolver(),
}


def get_full_sync_target_resolver(
    connector: SyncConnector,
) -> FullSyncTargetResolverProtocol:
    """
    connector 타입에 해당하는 Full Sync target resolver 반환
    """
    resolver = _FULL_SYNC_TARGET_RESOLVERS.get(connector)
    if resolver is None:
        raise SyncRequestError(f"unsupported sync connector: {connector}")
    return resolver


def list_registered_sync_connectors() -> list[SyncConnector]:
    """
    현재 registry에 등록된 connector 목록을 반환
    """
    return list(_FULL_SYNC_TARGET_RESOLVERS.keys())
