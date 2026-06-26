from langchain.embeddings import Embeddings

from catchup.components.vector_db.base import BaseVectorDbService
from catchup.components.vector_db.pgvector.constants import VectorDbProvider
from catchup.components.vector_db.pgvector.pgvector import PGVectorService
from catchup.components.vector_db.pgvector.repository import PGVectorRepository
from catchup.components.vector_db.v2 import V2KnowledgeRepository
from catchup.components.vector_db.v2 import VectorStore
from catchup.configs.config import settings
from catchup.db.engine import engine

# TODO: Embedding 모델을 다변화 하고 싶은 경우 dict로 싱글톤 관리하기 및 Repository & Service 통합
_pgvector_repository : PGVectorRepository | None = None  #Ingestion
_v2_vector_store: VectorStore | None = None
_v2_knowledge_repository: V2KnowledgeRepository | None = None
_pgvector_service: PGVectorService | None = None  # Retrieval


# Ingestion
def get_pgvector_repository(
        embeddings: Embeddings
) -> PGVectorRepository:
    global _pgvector_repository
    if _pgvector_repository is None:
        _pgvector_repository = PGVectorRepository(
            embeddings=embeddings,
            collection_name=settings.PGVECTOR_COLLECTION_NAME
        )
    return _pgvector_repository


def get_v2_vector_store(embeddings: Embeddings) -> VectorStore:
    global _v2_vector_store
    if _v2_vector_store is None:
        _v2_vector_store = VectorStore(embeddings=embeddings)
    return _v2_vector_store


def get_v2_knowledge_repository() -> V2KnowledgeRepository:
    global _v2_knowledge_repository
    if _v2_knowledge_repository is None:
        _v2_knowledge_repository = V2KnowledgeRepository()
    return _v2_knowledge_repository


# Retrieval
def get_vector_db_service(
    provider: VectorDbProvider,
    embeddings: Embeddings = None
)-> BaseVectorDbService:
    if provider == VectorDbProvider.PGVECTOR:
        global _pgvector_service
        if _pgvector_service is None:
            _pgvector_service = PGVectorService(
                collection_name=settings.PGVECTOR_COLLECTION_NAME,
                postgresql_engine=engine,
                embeddings=embeddings
            )
        return _pgvector_service
    raise ValueError(f"Unknown provider: {provider}")
