from __future__ import annotations

from datetime import datetime
from datetime import timezone

from fastapi.concurrency import run_in_threadpool

from catchup.audit.actions import FullSyncAction
from catchup.audit.metadata import FullSyncEventAuditMetadata
from catchup.audit.utils import audit_log
from catchup.connector_core.adapters.channel_talk.article_full_sync import (
    ChannelTalkArticleFullSyncIngestionAdapter,
)
from catchup.connector_core.adapters.channel_talk.user_chat_full_sync import (
    ChannelTalkUserChatFullSyncIngestionAdapter,
)
from catchup.connector_core.application.sync_ingestion import run_sync_ingestion
from catchup.connector_core.ports.sync_ingestion import SyncWindow
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncCheckpoint,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatSyncExecutionRequest,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleSyncExecutionRequest,
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

CHANNEL_TALK_USER_CHAT_FULL_SYNC_BATCH_SIZE = 2
CHANNEL_TALK_USER_CHAT_FULL_SYNC_MAX_PAGES_PER_BATCH = 1


class ChannelTalkFullSyncHandler(BaseFullSyncHandler):
    connector = "channel_talk"

    def __init__(self) -> None:
        self._user_chat_adapter = ChannelTalkUserChatFullSyncIngestionAdapter(
            max_user_chat_pages_per_run=(
                CHANNEL_TALK_USER_CHAT_FULL_SYNC_MAX_PAGES_PER_BATCH
            ),
            user_chat_list_limit=CHANNEL_TALK_USER_CHAT_FULL_SYNC_BATCH_SIZE,
        )
        self._article_adapter = ChannelTalkArticleFullSyncIngestionAdapter()
        self._ingestion_ports = {
            CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET: self._user_chat_adapter,
            CHANNEL_TALK_DOCUMENT_ARTICLE_RUNTIME_TARGET: self._article_adapter,
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
        # handler는 metadata stage가 아니라 target_type으로 실행 adapter를 고른다.
        runtime_target = self._resolve_runtime_target(context)
        ingestion_port = self._ingestion_ports.get(runtime_target)
        if ingestion_port is None:
            raise ValueError(
                "channel_talk target_type must resolve to one of: "
                f"{', '.join(sorted(self._ingestion_ports))}"
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
        # worker는 이 값을 application layer의 SyncWindow로 변환한다.
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
        sync_window = SyncWindow(
            window_start=window_start,
            window_end=window_end,
        )

        # UserChat은 channel connection만 필요하고, Article은 요청 space_id와
        # 일치하는 verified Documents connection을 추가로 확인한다.
        if runtime_target == CHANNEL_TALK_USER_CHAT_RUNTIME_TARGET:
            return await self._handle_user_chat_batches(
                channel_id=channel_id,
                ingestion_port=self._user_chat_adapter,
                sync_window=sync_window,
                audit_context=audit_context,
            )

        execution = ChannelTalkArticleSyncExecutionRequest(
            tenant_id=channel_id,
            channel_connection=connection,
            document_connection=await self._load_verified_document_connection(
                channel_id,
                requested_space_id=context.target_id,
            ),
            audit_context=audit_context,
        )
        result = await run_sync_ingestion(
            port=ingestion_port,
            execution=execution,
            sync_window=sync_window,
        )
        return self._result(
            synced_count=result.persisted.persisted_count,
            error_count=0,
            skipped=False,
        )

    async def _handle_user_chat_batches(
        self,
        *,
        channel_id: str,
        ingestion_port: ChannelTalkUserChatFullSyncIngestionAdapter,
        sync_window: SyncWindow,
        audit_context: SyncAuditContext,
    ) -> TargetSyncResult:
        synced_count = 0
        checkpoint: ChannelTalkUserChatFullSyncCheckpoint | None = None
        seen_checkpoints: set[tuple[str, str | None]] = set()

        while True:
            execution = ChannelTalkUserChatSyncExecutionRequest(
                tenant_id=channel_id,
                checkpoint=checkpoint,
                audit_context=audit_context,
            )
            result = await run_sync_ingestion(
                port=ingestion_port,
                execution=execution,
                sync_window=sync_window,
            )
            synced_count += result.persisted.persisted_count

            checkpoint = result.fetched.next_checkpoint
            if checkpoint is None:
                break

            checkpoint_key = (checkpoint.state.value, checkpoint.next_cursor)
            if checkpoint_key in seen_checkpoints:
                raise ValueError(
                    "channel_talk user_chat full sync checkpoint repeated: "
                    f"state={checkpoint.state.value}, "
                    f"next_cursor={checkpoint.next_cursor}"
                )
            seen_checkpoints.add(checkpoint_key)

        return self._result(
            synced_count=synced_count,
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
