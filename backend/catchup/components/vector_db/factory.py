from enum import StrEnum
from functools import lru_cache

from langchain_openai import OpenAIEmbeddings

from catchup.components.vector_db.base import BaseVectorDbService
from catchup.components.vector_db.meilisearch.meili import LangChainMeiliRepository
from catchup.components.vector_db.pgvector.pgvector import PGVectorService
from catchup.components.vector_db.pgvector.repository import PGVectorRepository
from catchup.db.engine import engine
from catchup.configs.config import settings

class VectorDbProvider(StrEnum):
    MEILISEARCH = "meilisearch"
    PGVECTOR = "pgvector"


@lru_cache(maxsize=1)
def get_vector_db_service(provider: str) -> BaseVectorDbService:
    if (provider == VectorDbProvider.MEILISEARCH):
        return LangChainMeiliRepository()
    
    if (provider == VectorDbProvider.PGVECTOR):
        repo = PGVectorRepository()
        return PGVectorService(
            collection_name=settings.PGVECTOR_COLLECTION_NAME,
            postgresql_engine=engine,
            embeddings=OpenAIEmbeddings(model=settings.OPENAI_EMBEDDING_MODEL, api_key=settings.OPENAI_API_KEY)
        )
