from functools import lru_cache
from typing import Optional

from langchain.embeddings import Embeddings

from catchup.components.vector_db.base import BaseVectorDbService
from catchup.components.vector_db.pgvector.constants import VectorDbProvider
from catchup.components.vector_db.pgvector.pgvector import PGVectorService
from catchup.db.engine import engine
from catchup.configs.config import settings


def get_vector_db_service(
    provider: VectorDbProvider,
    embeddings: Embeddings = None
)-> BaseVectorDbService:

    if provider == VectorDbProvider.PGVECTOR:        
        return PGVectorService(
            collection_name=settings.PGVECTOR_COLLECTION_NAME,
            postgresql_engine=engine,
            embeddings=embeddings
        )
    
    raise ValueError(f"Unknown provider: {provider}")