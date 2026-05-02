from __future__ import annotations

from catchup.connector_core.adapters.channel_talk.article_full_sync import (
    ChannelTalkArticleFullSyncAdapter,
)
from catchup.connector_core.ports.full_sync import FullSyncWindow
from catchup.connectors.channel_talk.document_space.article_full_sync_fetcher import (
    ChannelTalkArticleFullSyncFetcher,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleFullSyncConnection,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleFullSyncExecutionRequest,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleFullSyncFetchResult,
)
from catchup.connectors.channel_talk.document_space.article_full_sync_models import (
    ChannelTalkArticleFullSyncPersistResult,
)
from catchup.utils.validation import require_text


class ChannelTalkArticleIncrementalAdapter:
    """Exact-refresh adapter for Channel Talk Documents article records."""

    def __init__(
        self,
        *,
        fetcher: ChannelTalkArticleFullSyncFetcher | None = None,
        language: str = "ko",
        repository_factory=None,
        pipeline_adapter: ChannelTalkArticleFullSyncAdapter | None = None,
    ) -> None:
        self.language = require_text(language, "language")
        self._pipeline_adapter = pipeline_adapter or ChannelTalkArticleFullSyncAdapter(
            fetcher=fetcher,
            language=self.language,
            repository_factory=repository_factory,
        )
        self.fetcher = self._pipeline_adapter.fetcher

    async def sync_article_by_id(
        self,
        *,
        execution: ChannelTalkArticleFullSyncExecutionRequest,
        article_id: str,
        sync_window: FullSyncWindow,
    ) -> ChannelTalkArticleFullSyncPersistResult:
        bundle = await self.fetcher.fetch_article_bundle_by_id(
            connection=ChannelTalkArticleFullSyncConnection.from_credentials_record(
                execution.document_connection,
            ),
            article_id=article_id,
            language=self.language,
        )
        fetched = ChannelTalkArticleFullSyncFetchResult(
            channel_id=execution.channel_id,
            space_id=execution.space_id,
            language=self.language,
            bundles=(bundle,),
            fetched_count=1,
            fetched_article_ids=(bundle.article_id,),
        )
        transformed = await self._pipeline_adapter.transform(
            execution=execution,
            sync_window=sync_window,
            fetched=fetched,
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
