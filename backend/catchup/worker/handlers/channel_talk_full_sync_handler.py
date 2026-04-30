from __future__ import annotations

from datetime import datetime
from datetime import timezone

from fastapi.concurrency import run_in_threadpool

from catchup.audit.actions import FullSyncAction
from catchup.audit.metadata import FullSyncEventAuditMetadata
from catchup.audit.utils import audit_log
from catchup.connector_core.adapters.channel_talk.document_article_full_sync_adapter import (
    ChannelTalkDocumentArticleFullSyncAdapter,
)
from catchup.connector_core.adapters.channel_talk.document_article_full_sync_adapter import (
    ChannelTalkDocumentArticleFullSyncExecutionRequest,
)
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
    is_verified_channel_talk_document_connection,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    load_channel_talk_connection,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    load_channel_talk_document_connection,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    require_channel_talk_channel_id,
)
from catchup.connectors.channel_talk.full_sync_target_contract import (
    CHANNEL_TALK_DOCUMENT_ARTICLE_TARGET_ID,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord,
)
from catchup.sync.audit import SyncAuditContext
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import TargetSyncResult
from catchup.worker.handlers.base_full_sync_handler import BaseFullSyncHandler


class ChannelTalkFullSyncHandler(BaseFullSyncHandler):
    connector = "channel_talk"

    def __init__(self) -> None:
        self._applications = {
            CHANNEL_TALK_FULL_SYNC_TARGET_ID: ConnectorFullSyncApplication(
                port=ChannelTalkFullSyncAdapter(),
            ),
            CHANNEL_TALK_DOCUMENT_ARTICLE_TARGET_ID: ConnectorFullSyncApplication(
                port=ChannelTalkDocumentArticleFullSyncAdapter(),
            ),
        }

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
        application = self._applications.get(target_id)
        if application is None:
            raise ValueError(
                "channel_talk target_id must be one of: "
                f"{', '.join(sorted(self._applications))}"
            )

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
        audit_context = SyncAuditContext(
            connector=context.connector,
            scope_id=context.scope_id,
            target_id=context.target_id,
            job_id=context.job_id,
            task_id=context.event_id,
        )
        execution = (
            ChannelTalkFullSyncExecutionRequest(
                tenant_id=channel_id,
                audit_context=audit_context,
            )
            if target_id == CHANNEL_TALK_FULL_SYNC_TARGET_ID
            else ChannelTalkDocumentArticleFullSyncExecutionRequest(
                tenant_id=channel_id,
                channel_connection=connection,
                document_connection=await self._load_verified_document_connection(
                    channel_id
                ),
                audit_context=audit_context,
            )
        )
        result = await application.run_full_sync(
            execution=execution,
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

    async def _load_verified_document_connection(
        self,
        channel_id: str,
    ) -> ChannelTalkDocumentCredentialsRecord:
        document_connection = await run_in_threadpool(
            load_channel_talk_document_connection,
            channel_id,
        )
        if document_connection is None:
            raise ValueError(
                "channel_talk documents is not connected for the requested channel"
            )
        if document_connection.channel_id != channel_id:
            raise ValueError(
                "Stored Channel Talk Documents credentials do not match the requested channel"
            )
        if not is_verified_channel_talk_document_connection(
            document_connection,
            channel_id=channel_id,
        ):
            raise ValueError(
                "channel_talk documents credentials are not API verified for the requested channel"
            )
        return document_connection
