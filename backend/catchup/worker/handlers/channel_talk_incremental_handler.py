from __future__ import annotations

from datetime import datetime
from datetime import timezone

from fastapi.concurrency import run_in_threadpool

from catchup.audit.actions import IncrementalSyncAction
from catchup.audit.metadata import IncrementalRecordAuditMetadata
from catchup.audit.utils import audit_log
from catchup.connector_core.adapters.channel_talk.article_incremental import (
    ChannelTalkArticleIncrementalIngestionAdapter,
)
from catchup.connector_core.adapters.channel_talk.user_chat_incremental import (
    ChannelTalkUserChatIncrementalIngestionAdapter,
)
from catchup.connector_core.application.sync_ingestion import run_sync_ingestion
from catchup.connector_core.ports.sync_ingestion import SyncWindow
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatIncrementalExecutionRequest,
)
from catchup.connectors.channel_talk.credential_loader import (
    load_channel_talk_connection,
)
from catchup.connectors.channel_talk.credential_loader import (
    load_channel_talk_document_connection,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleIncrementalExecutionRequest,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    is_verified_channel_talk_document_connection,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    require_channel_talk_channel_id,
)
from catchup.sync.audit import SyncAuditContext
from catchup.sync.common.schemas import IncrementalSyncContext
from catchup.sync.common.schemas import TargetSyncResult
from catchup.worker.handlers.base_incremental_handler import BaseIncrementalHandler


class ChannelTalkIncrementalHandler(BaseIncrementalHandler):
    connector = "channel_talk"

    def __init__(self) -> None:
        self._user_chat_adapter = ChannelTalkUserChatIncrementalIngestionAdapter()
        self._article_adapter = ChannelTalkArticleIncrementalIngestionAdapter()

    @audit_log(
        IncrementalSyncAction.RECORD,
        metadata_factory=IncrementalRecordAuditMetadata.from_audit,
        emit_attempt=True,
    )
    async def handle(
        self,
        *,
        context: IncrementalSyncContext,
        service_cache: dict[str, object],
    ) -> TargetSyncResult:
        _ = service_cache
        channel_id = require_channel_talk_channel_id(context.scope_id)
        record_type = (context.record_type or "").strip()
        record_id = (context.record_id or "").strip()
        if not record_id:
            raise ValueError("channel_talk incremental record_id is empty")

        sync_window = SyncWindow(
            window_start=self._resolve_since(context),
            window_end=datetime.now(timezone.utc),
        )
        audit_context = SyncAuditContext(
            connector=context.connector,
            scope_id=context.scope_id,
            target_id=context.target_id,
            job_id=context.job_id,
            task_id=context.event_id,
        )

        if record_type == "user_chat":
            persisted_count = await self._sync_user_chat(
                channel_id=channel_id,
                user_chat_id=record_id,
                sync_window=sync_window,
                audit_context=audit_context,
            )
        elif record_type == "document_article":
            persisted_count = await self._sync_document_article(
                channel_id=channel_id,
                space_id=(context.parent_id or context.target_id or "").strip(),
                article_id=record_id,
                sync_window=sync_window,
                audit_context=audit_context,
            )
        else:
            raise ValueError(f"unsupported channel_talk record_type: {record_type}")

        return self._result(
            synced_count=persisted_count,
            error_count=0,
            skipped=False,
        )

    async def _sync_user_chat(
        self,
        *,
        channel_id: str,
        user_chat_id: str,
        sync_window: SyncWindow,
        audit_context: SyncAuditContext,
    ) -> int:
        result = await run_sync_ingestion(
            port=self._user_chat_adapter,
            execution=ChannelTalkUserChatIncrementalExecutionRequest(
                tenant_id=channel_id,
                audit_context=audit_context,
                user_chat_id=user_chat_id,
            ),
            sync_window=sync_window,
        )
        return result.persisted.persisted_count

    async def _sync_document_article(
        self,
        *,
        channel_id: str,
        space_id: str,
        article_id: str,
        sync_window: SyncWindow,
        audit_context: SyncAuditContext,
    ) -> int:
        if not space_id:
            raise ValueError("channel_talk document space_id is empty")

        channel_connection = await run_in_threadpool(
            load_channel_talk_connection,
            channel_id,
        )
        if channel_connection is None or channel_connection.channel_id != channel_id:
            raise ValueError("channel_talk is not connected for the requested channel")

        document_connection = await run_in_threadpool(
            load_channel_talk_document_connection,
            channel_id,
            space_id,
        )
        if document_connection is None:
            raise ValueError("channel_talk documents credentials are missing")
        if not is_verified_channel_talk_document_connection(
            document_connection,
            channel_id=channel_id,
        ):
            raise ValueError(
                "channel_talk documents credentials are not API verified for the requested channel"
            )

        result = await run_sync_ingestion(
            port=self._article_adapter,
            execution=ChannelTalkArticleIncrementalExecutionRequest(
                tenant_id=channel_id,
                channel_connection=channel_connection,
                document_connection=document_connection,
                audit_context=audit_context,
                article_id=article_id,
            ),
            sync_window=sync_window,
        )
        return result.persisted.persisted_count
