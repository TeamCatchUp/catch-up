"""
Jira Connector Factory

JiraIngestionService 인스턴스를 생성하는 팩토리.
OAuth Token을 조회하여 서비스 인스턴스를 생성.
"""

import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.connectors.atlassian.exceptions import (
    AtlassianTokenExpiredError,
    AtlassianTokenNotFoundError,
)
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.connectors.atlassian.token_manager import AtlassianTokenManager
from catchup.connectors.jira.service import JiraIngestionService
from catchup.db.atlassian import oauth_repository

logger = logging.getLogger(__name__)


async def create_jira_ingestion_service(
    db: Session,
    cloud_id: str,
) -> JiraIngestionService:
    """
    JiraIngestionService 인스턴스 생성

    Args:
        db: SQLAlchemy Session
        cloud_id: Jira Cloud ID

    Returns:
        초기화된 JiraIngestionService

    Raises:
        HTTPException: Token을 찾을 수 없거나 유효하지 않은 경우
    """
    token_manager = AtlassianTokenManager(
        oauth_client=AtlassianOAuthClient(),
        oauth_repository=oauth_repository,
    )

    try:
        access_token = await token_manager.resolve_access_token_by_cloud_id(db, cloud_id)
    except AtlassianTokenNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Jira 연결을 찾을 수 없습니다: {cloud_id}",
        )
    except AtlassianTokenExpiredError:
        raise HTTPException(
            status_code=401,
            detail=f"Jira 인증이 만료되었습니다. 재연결이 필요합니다: {cloud_id}",
        )
    except Exception as e:
        logger.error(f"Failed to get valid access token for cloud_id={cloud_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Token 획득 중 오류가 발생했습니다: {str(e)}",
        )

    token_record = oauth_repository.get_token_by_cloud_id(db, cloud_id)
    site_url = token_record.site_url if token_record else ""
    repository = PGVectorRepository(
        embeddings=get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()
    )
    service = JiraIngestionService(
        repository=repository,
        cloud_id=cloud_id,
        access_token=access_token,
        site_url=site_url or ""
    )
    await service.initialize()
    return service
