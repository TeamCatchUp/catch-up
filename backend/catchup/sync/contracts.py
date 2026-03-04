from __future__ import annotations

from catchup.sync.common.protocols import ConnectorSyncServiceProtocol
from catchup.sync.common.schemas import (
    FullSyncDispatchCommand,
    IncrementalSyncDispatchCommand,
    SyncDispatchResult,
    SyncDispatchStatus,
)

# contracts는 공통 schema/protocol을 재노출하는 호환 계층으로 유지한다.
ConnectorSyncService = ConnectorSyncServiceProtocol
