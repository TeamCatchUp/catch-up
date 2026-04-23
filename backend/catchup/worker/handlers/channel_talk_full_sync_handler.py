from __future__ import annotations

from datetime import datetime
from datetime import timezone

from fastapi.concurrency import run_in_threadpool

from catchup.audit.actions import FullSyncAction
from catchup.audit.metadata import FullSyncEventAuditMetadata
from catchup.audit.utils import audit_log
from catchup.connector_core.adapters.channel_talk.full_sync_adapter import (
    ChannelTalkFullSyncAdapter,
)
from catchup.connector_core.adapters.channel_talk.full_sync_adapter import (
    ChannelTalkFullSyncExecutionRequest,
)
from catchup.connector_core.application.full_sync import ConnectorFullSyncApplication
from catchup.connector_core.ports.full_sync import FullSyncWindow
from catchup.connectors.channel_talk.full_sync_helper import (
    CHANNEL_TALK_FULL_SYNC_TARGET_ID,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    load_channel_talk_connection,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    require_channel_talk_channel_id,
)
from catchup.sync.audit import SyncAuditContext
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import TargetSyncResult
from catchup.worker.handlers.base_full_sync_handler import BaseFullSyncHandler


class ChannelTalkFullSyncHandler(BaseFullSyncHandler):
    connector = "channel_talk"

    def __init__(self) -> None:
        self._application = ConnectorFullSyncApplication(
            port=ChannelTalkFullSyncAdapter(),
        )

    @audit_log(
        FullSyncAction.EVENT,
        metadata_factory=FullSyncEventAuditMetadata.from_audit,
        emit_attempt=True,
    )
    async def handle(
        self,
        *,
        context: FullSyncContext,
        service_cache: dict[str, object],
    ) -> TargetSyncResult:
        _ = service_cache
        channel_id = require_channel_talk_channel_id(context.scope_id)

        target_id = context.target_id.strip()
        if target_id != CHANNEL_TALK_FULL_SYNC_TARGET_ID:
            raise ValueError("channel_talk target_id must be user_chat")

        connection = await run_in_threadpool(load_channel_talk_connection)
        if connection is None:
            raise ValueError("channel_talk is not connected")
        if connection.channel_id != channel_id:
            raise ValueError(
                "Stored Channel Talk credentials do not match the requested channel"
            )

        window_end = datetime.now(timezone.utc)
        window_start = (
            datetime.fromtimestamp(float(context.sync_from_ts), tz=timezone.utc)
            if context.sync_from_ts is not None
            else window_end
        )
        result = await self._application.run_full_sync(
            execution=ChannelTalkFullSyncExecutionRequest(
                tenant_id=channel_id,
                audit_context=SyncAuditContext(
                    connector=context.connector,
                    scope_id=context.scope_id,
                    target_id=context.target_id,
                    job_id=context.job_id,
                    task_id=context.event_id,
                ),
            ),
            sync_window=FullSyncWindow(
                window_start=window_start,
                window_end=window_end,
            ),
        )
        return self._result(
            synced_count=result.persisted.persisted_count,
            error_count=0,
            skipped=False,
        )
