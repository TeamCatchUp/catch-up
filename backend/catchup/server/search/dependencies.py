from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.factory import get_vector_db_service
from catchup.components.vector_db.pgvector.constants import VectorDbProvider
from catchup.components.vector_db.pgvector.pgvector import PGVectorService
from catchup.db.models import SourceType
from catchup.search.original.registry import OriginalResolverRegistry
from catchup.search.original.resolvers.channel_talk import ChannelTalkOriginalResolver
from catchup.search.original.service import OriginalSearchService
from catchup.search.service import ManualSearchService

_manual_search_service: ManualSearchService | None = None
_original_resolver_registry: OriginalResolverRegistry | None = None
_original_search_service: OriginalSearchService | None = None


def get_search_service() -> PGVectorService:
    embedding_service = get_embedding_service(EmbeddingProvider.AWS_BEDROCK)
    return get_vector_db_service(
        provider=VectorDbProvider.PGVECTOR, embeddings=embedding_service.get_embedder()
    )


def get_manual_search_service() -> ManualSearchService:
    global _manual_search_service
    if _manual_search_service is None:
        _manual_search_service = ManualSearchService()
    return _manual_search_service


def get_original_resolver_registry() -> OriginalResolverRegistry:
    global _original_resolver_registry
    if _original_resolver_registry is None:
        registry = OriginalResolverRegistry()
        registry.register(
            connector=SourceType.CHANNEL_TALK,
            entity_type="user_chat",
            resolver=ChannelTalkOriginalResolver(),
        )
        _original_resolver_registry = registry
    return _original_resolver_registry


def get_original_search_service() -> OriginalSearchService:
    global _original_search_service
    if _original_search_service is None:
        _original_search_service = OriginalSearchService(
            registry=get_original_resolver_registry(),
        )
    return _original_search_service
