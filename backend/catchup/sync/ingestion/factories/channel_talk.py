from __future__ import annotations

from catchup.sync.ingestion.adapters.channel_talk.article_v2_backfill import (
    ChannelTalkArticleV2BackfillAdapter,
)
from catchup.sync.ingestion.adapters.channel_talk.user_chat_v2_backfill import (
    ChannelTalkUserChatV2BackfillAdapter,
)
from catchup.sync.ingestion.factories.knowledge_store import (
    create_knowledge_store_dependencies,
)


async def create_channel_talk_user_chat_v2_backfill_adapter(
    channel_id: str,
) -> ChannelTalkUserChatV2BackfillAdapter:
    _ = channel_id
    knowledge_store = await create_knowledge_store_dependencies(
        require_vector_store=True,
    )
    return ChannelTalkUserChatV2BackfillAdapter(
        vector_store=knowledge_store.vector_store,
        v2_knowledge_repository=knowledge_store.v2_knowledge_repository,
    )


async def create_channel_talk_article_v2_backfill_adapter(
    channel_id: str,
    space_id: str,
) -> ChannelTalkArticleV2BackfillAdapter:
    _ = channel_id
    _ = space_id
    knowledge_store = await create_knowledge_store_dependencies(
        require_vector_store=True,
    )
    return ChannelTalkArticleV2BackfillAdapter(
        vector_store=knowledge_store.vector_store,
        v2_knowledge_repository=knowledge_store.v2_knowledge_repository,
    )
