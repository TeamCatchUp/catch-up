"""
Github Connector Factory

GithubIngestionService 인스턴스 생성을 위한 팩토리 함수.
"""

import logging

from sqlalchemy.orm import Session

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.connectors.github.service import GithubIngestionService
from catchup.db.github.installation_repository import get_installation_by_installation_id
from catchup.connectors.github.auth import get_github_app_service
from catchup.sync.common.exceptions import SyncConnectorError, SyncInternalError

logger = logging.getLogger(__name__)


async def create_github_ingestion_service(
    db: Session,
    installation_id: int,
) -> GithubIngestionService:
    installation = get_installation_by_installation_id(db, installation_id)
    if not installation:
        raise SyncConnectorError(
            f"Github Installation not found: {installation_id}",
            metadata={"installation_id": installation_id},
        )

    try:
        github_app_service = get_github_app_service()
        access_token = await github_app_service.get_installation_access_token(
            installation_id
        )

        repository = PGVectorRepository(
            embeddings=get_embedding_service(
                EmbeddingProvider.AWS_BEDROCK
            ).get_embedder()
        )
        service = GithubIngestionService(
            repository=repository,
            installation_id=installation_id,
            access_token=access_token,
        )
        await service.initialize()
        return service
    except Exception as exc:
        logger.error(
            "[GITHUB][FACTORY] Failed to initialize ingestion service: installation_id=%s, error=%s",
            installation_id,
            exc,
            exc_info=True,
        )
        raise SyncInternalError(
            "Github ingestion service initialization failed",
            metadata={"installation_id": installation_id},
        ) from exc
