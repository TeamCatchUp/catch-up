from __future__ import annotations

from fastapi.concurrency import run_in_threadpool

from catchup.components.summarizer import SummarizerService
from catchup.connector_core.adapters.channel_talk.user_chat_full_sync import (
    ChannelTalkUserChatFullSyncAdapter,
)
from catchup.connector_core.ports.full_sync import FullSyncWindow
from catchup.connectors.channel_talk.core.user_chat_full_sync_fetcher import (
    ChannelTalkUserChatFullSyncFetcher,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncConnection,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncExecutionRequest,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncFetchResult,
)
from catchup.connectors.channel_talk.core.user_chat_full_sync_models import (
    ChannelTalkUserChatFullSyncPersistResult,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    load_channel_talk_connection,
)


class ChannelTalkUserChatIncrementalAdapter:
    """Exact-refresh adapter for Channel Talk UserChat incremental records."""

    def __init__(
        self,
        *,
        fetcher: ChannelTalkUserChatFullSyncFetcher | None = None,
        connection_loader=load_channel_talk_connection,
        repository_factory=None,
        enable_summarization: bool = True,
        summarizer: SummarizerService | None = None,
        pipeline_adapter: ChannelTalkUserChatFullSyncAdapter | None = None,
    ) -> None:
        self._connection_loader = connection_loader
        self._pipeline_adapter = pipeline_adapter or ChannelTalkUserChatFullSyncAdapter(
            fetcher=fetcher,
            connection_loader=connection_loader,
            repository_factory=repository_factory,
            enable_summarization=enable_summarization,
            summarizer=summarizer,
        )
        self.fetcher = self._pipeline_adapter.fetcher

    async def sync_user_chat_by_id(
        self,
        *,
        execution: ChannelTalkUserChatFullSyncExecutionRequest,
        user_chat_id: str,
        sync_window: FullSyncWindow,
    ) -> ChannelTalkUserChatFullSyncPersistResult:
        connection = await self._load_connection(execution=execution)
        managers_by_id = await self.fetcher.fetch_managers_by_id(
            connection=connection,
        )
        bundle = await self.fetcher.fetch_user_chat_bundle_by_id(
            connection=connection,
            user_chat_id=user_chat_id,
        )
        transformed = await self._pipeline_adapter.transform(
            execution=execution,
            sync_window=sync_window,
            fetched=ChannelTalkUserChatFullSyncFetchResult(
                states=(bundle.state,),
                sync_window=sync_window,
                bundles=(bundle,),
                managers_by_id=managers_by_id,
                fetched_record_ids=(bundle.detail.user_chat_id,),
            ),
        )
        summary = await self._pipeline_adapter.summarize(
            execution=execution,
            sync_window=sync_window,
            transformed=transformed,
        )
        return await self._pipeline_adapter.persist(
            execution=execution,
            sync_window=sync_window,
            transformed=transformed,
            summary=summary,
        )

    async def _load_connection(
        self,
        *,
        execution: ChannelTalkUserChatFullSyncExecutionRequest,
    ) -> ChannelTalkUserChatFullSyncConnection:
        connection = await run_in_threadpool(
            self._connection_loader,
            execution.channel_id,
        )
        if connection is None:
            raise ValueError("channel_talk is not connected")
        if connection.channel_id != execution.channel_id:
            raise ValueError(
                "Stored Channel Talk credentials do not match the requested channel"
            )
        return ChannelTalkUserChatFullSyncConnection.from_credentials_record(connection)
