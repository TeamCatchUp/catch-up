from __future__ import annotations

from catchup.db.models import SyncConnector
from catchup.sync.contracts import ConnectorSyncService
from catchup.sync.services import get_slack_connector_sync_service


_CONNECTOR_SYNC_SERVICES: dict[SyncConnector, ConnectorSyncService] = {
    SyncConnector.SLACK: get_slack_connector_sync_service(),
}


def get_connector_sync_service(connector: SyncConnector) -> ConnectorSyncService:
    """
    connector 타입에 해당하는 Sync 서비스 구현체를 반환
    """
    service = _CONNECTOR_SYNC_SERVICES.get(connector)
    if service is None:
        raise ValueError(f"unsupported sync connector: {connector}")
    return service


def list_registered_sync_connectors() -> list[SyncConnector]:
    """
    현재 registry에 등록된 connector 목록을 반환
    """
    return list(_CONNECTOR_SYNC_SERVICES.keys())
