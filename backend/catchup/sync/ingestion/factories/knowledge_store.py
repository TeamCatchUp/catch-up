from __future__ import annotations

from dataclasses import dataclass

from langchain.embeddings import Embeddings

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.factory import get_pgvector_repository
from catchup.components.vector_db.factory import get_v2_knowledge_repository
from catchup.components.vector_db.factory import get_v2_vector_store
from catchup.components.vector_db.pgvector.repository import PGVectorRepository
from catchup.components.vector_db.v2 import V2KnowledgeRepository
from catchup.components.vector_db.v2 import VectorStore
from catchup.configs.config import settings


@dataclass(slots=True)
class KnowledgeStoreDependencies:
    '''
    Dependencies required for knowledge_store Ingestion
    '''
    # TODO : Delete After migrate pg_langchain_embeddings to knowledge_store
    repository: PGVectorRepository
    vector_store: VectorStore | None
    v2_knowledge_repository: V2KnowledgeRepository | None


def get_default_knowledge_store_embeddings() -> Embeddings:
    return get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()


async def create_knowledge_store_dependencies(
    *,
    embeddings: Embeddings | None = None,
    require_vector_store: bool = False,
) -> KnowledgeStoreDependencies:
    embeddings = embeddings or get_default_knowledge_store_embeddings()

    repository = get_pgvector_repository(embeddings=embeddings)
    await _ensure_repository_initialized(repository)

    vector_store = None
    v2_knowledge_repository = None
    if settings.VECTOR_STORE_V2_DUAL_WRITE_ENABLED or require_vector_store:
        vector_store = get_v2_vector_store(embeddings)
        await vector_store.initialize()
        v2_knowledge_repository = get_v2_knowledge_repository()

    return KnowledgeStoreDependencies(
        repository=repository,
        vector_store=vector_store,
        v2_knowledge_repository=v2_knowledge_repository,
    )


async def _ensure_repository_initialized(repository: PGVectorRepository) -> None:
    try:
        repository.ensure_initialized()
    except RuntimeError:
        await repository.initialize(None)
