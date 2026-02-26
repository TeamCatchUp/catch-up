"""
Github Connector Factory

GithubIngestionService 인스턴스 생성을 위한 팩토리 함수.
"""

from functools import lru_cache

from sqlalchemy.orm import Session

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.connectors.github.service import GithubService, GithubIngestionService
from catchup.db.github.installation_repository import get_installation_by_installation_id
from catchup.connectors.github.auth import get_github_app_service


@lru_cache(maxsize=1)
def get_github_service() -> GithubService:
    """
    Legacy GithubService 인스턴스 반환 (PR 컨텍스트 조회용)

    Note: 새로운 코드에서는 create_github_ingestion_service 사용 권장
    """
    return GithubService()


async def create_github_ingestion_service(
    db: Session,
    installation_id: int,
) -> GithubIngestionService:
    """
    GithubIngestionService 인스턴스 생성

    Args:
        db: SQLAlchemy Session
        installation_id: Github App Installation ID

    Returns:
        초기화된 GithubIngestionService 인스턴스

    Raises:
        ValueError: Installation을 찾을 수 없는 경우
    """
    # Installation 정보 확인
    installation = get_installation_by_installation_id(db, installation_id)
    if not installation:
        raise ValueError(f"Github Installation not found: {installation_id}")

    # Installation Access Token 발급
    github_app_service = get_github_app_service()
    access_token = await github_app_service.get_installation_access_token(installation_id)

    # Service 인스턴스 생성 및 초기화
    repository = PGVectorRepository(
        embeddings=get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()
    )
    
    service = GithubIngestionService(
        repository=repository,
        installation_id=installation_id,
        access_token=access_token,
    )
    await service.initialize()

    return service
