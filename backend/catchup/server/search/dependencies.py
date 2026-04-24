from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.factory import get_vector_db_service
from catchup.components.vector_db.pgvector.constants import VectorDbProvider
from catchup.components.vector_db.pgvector.pgvector import PGVectorService


def get_search_service() -> PGVectorService:
    embedding_service = get_embedding_service(EmbeddingProvider.AWS_BEDROCK)
    return get_vector_db_service(
        provider=VectorDbProvider.PGVECTOR, embeddings=embedding_service.get_embedder()
    )
