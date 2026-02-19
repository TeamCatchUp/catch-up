from functools import lru_cache
from typing import Optional

from langchain.embeddings import Embeddings

from catchup.components.vector_db.base import BaseVectorDbService
from catchup.components.vector_db.meilisearch.meili import LangChainMeiliRepository
from catchup.components.vector_db.pgvector.constants import VectorDbProvider
from catchup.components.vector_db.pgvector.pgvector import PGVectorService
from catchup.db.engine import engine
from catchup.configs.config import settings


def get_vector_db_service(
    provider: VectorDbProvider,
    embeddings: Optional[Embeddings] = None  # TODO: Meilisearch 관련 코드 제거 이후 Optional 해제
)-> BaseVectorDbService:
    
    if provider == VectorDbProvider.MEILISEARCH:
        return LangChainMeiliRepository()
    
    if provider == VectorDbProvider.PGVECTOR:        
        return PGVectorService(
            collection_name=settings.PGVECTOR_COLLECTION_NAME,
            postgresql_engine=engine,
            embeddings=embeddings
        )
    
    raise ValueError(f"Unknown provider: {provider}")