from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.factory import get_vector_db_service
from catchup.components.vector_db.pgvector.constants import VectorDbProvider
from catchup.components.vector_db.pgvector.pgvector import PGVectorService
from catchup.search.service import ManualSearchService

_manual_search_service: ManualSearchService | None = None


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
