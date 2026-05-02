from __future__ import annotations

from datetime import datetime
from datetime import timezone

from fastapi.concurrency import run_in_threadpool

from catchup.audit.actions import FullSyncAction
from catchup.audit.metadata import FullSyncEventAuditMetadata
from catchup.audit.utils import audit_log
from catchup.connector_core.adapters.channel_talk.article_full_sync import (
    ChannelTalkArticleFullSyncAdapter,
)
from catchup.connector_core.adapters.channel_talk.user_chat_full_sync import (
    ChannelTalkUserChatFullSyncAdapter,
)
from catchup.connector_core.application.full_sync import ConnectorFullSyncApplication
from catchup.connector_core.ports.full_sync import FullSyncWindow
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncExecutionRequest,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleFullSyncExecutionRequest,
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
    CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET,
)
from catchup.connectors.channel_talk.full_sync_target_contract import (
    CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord,
)
from catchup.sync.audit import SyncAuditContext
from catchup.sync.common.schemas import FullSyncContext
from catchup.sync.common.schemas import SyncTargetType
from catchup.sync.common.schemas import TargetSyncResult
from catchup.worker.handlers.base_full_sync_handler import BaseFullSyncHandler


class ChannelTalkFullSyncHandler(BaseFullSyncHandler):
    connector = "channel_talk"

    def __init__(self) -> None:
        self._applications = {
            CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET: ConnectorFullSyncApplication(
                port=ChannelTalkUserChatFullSyncAdapter(),
            ),
            CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET: (
                ConnectorFullSyncApplication(
                    port=ChannelTalkArticleFullSyncAdapter(),
                )
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

        # Event에는 listing/full request에서 확정된 target_type이 들어 있다.
        # handler는 metadata stage가 아니라 target_type으로 실행 application을 고른다.
        runtime_target = self._resolve_runtime_target(context)
        application = self._applications.get(runtime_target)
        if application is None:
            raise ValueError(
                "channel_talk target_type must resolve to one of: "
                f"{', '.join(sorted(self._applications))}"
            )

        connection = await run_in_threadpool(
            load_channel_talk_connection,
            channel_id,
        )
        if connection is None:
            raise ValueError("channel_talk is not connected for the requested channel")
        if connection.channel_id != channel_id:
            raise ValueError(
                "Stored Channel Talk credentials do not match the requested channel"
            )
        if (
            runtime_target == CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET
            and context.target_id.strip() != channel_id
        ):
            # UserChat full sync는 channel target이므로 event target_id도 channel_id여야 한다.
            raise ValueError(
                "Stored Channel Talk credentials do not match the requested channel target"
            )

        # sync_from_ts는 API에서 sync_days로 계산된 epoch seconds다.
        # worker는 이 값을 application layer의 FullSyncWindow로 변환한다.
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
        # UserChat은 channel connection만 필요하고, Article은 요청 space_id와
        # 일치하는 verified Documents connection을 추가로 확인한다.
        execution = (
            ChannelTalkUserChatFullSyncExecutionRequest(
                tenant_id=channel_id,
                audit_context=audit_context,
            )
            if runtime_target == CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET
            else ChannelTalkArticleFullSyncExecutionRequest(
                tenant_id=channel_id,
                channel_connection=connection,
                document_connection=await self._load_verified_document_connection(
                    channel_id,
                    requested_space_id=context.target_id,
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
        *,
        requested_space_id: str,
    ) -> ChannelTalkDocumentCredentialsRecord:
        # space target은 실제 Channel Talk Documents 연결의 space_id와 일치해야 한다.
        # 이 검증이 있어 target_type=space + 잘못된 target_id event가 실행되지 않는다.
        normalized_requested_space_id = requested_space_id.strip()
        document_connection = await run_in_threadpool(
            load_channel_talk_document_connection,
            channel_id,
            normalized_requested_space_id,
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
        if document_connection.space_id != normalized_requested_space_id:
            raise ValueError(
                "Stored Channel Talk Documents credentials do not match the requested space"
            )
        return document_connection

    @staticmethod
    def _resolve_runtime_target(context: FullSyncContext) -> str:
        # runtime target literal은 adapter 내부 계약일 뿐, API/listing target_id가 아니다.
        if context.target_type == SyncTargetType.CHANNEL:
            return CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET
        if context.target_type == SyncTargetType.SPACE:
            return CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET
        raise ValueError("channel_talk target_type must be one of: channel, space")
