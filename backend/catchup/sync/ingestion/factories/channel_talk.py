from __future__ import annotations

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.factory import get_v2_vector_store
from catchup.sync.ingestion.adapters.channel_talk.article_v2_backfill import (
    ChannelTalkArticleV2BackfillAdapter,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_v2_backfill import (
    ChannelTalkUserChatV2BackfillAdapter,
)


async def create_channel_talk_user_chat_v2_backfill_adapter(
    channel_id: str,
) -> ChannelTalkUserChatV2BackfillAdapter:
    _ = channel_id
    embeddings = get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()
    vector_store = get_v2_vector_store(embeddings)
    await vector_store.initialize()
    return ChannelTalkUserChatV2BackfillAdapter(vector_store=vector_store)


async def create_channel_talk_article_v2_backfill_adapter(
    channel_id: str,
    space_id: str,
) -> ChannelTalkArticleV2BackfillAdapter:
    _ = channel_id
    _ = space_id
    embeddings = get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()
    vector_store = get_v2_vector_store(embeddings)
    await vector_store.initialize()
    return ChannelTalkArticleV2BackfillAdapter(vector_store=vector_store)
