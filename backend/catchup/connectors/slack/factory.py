"""
Slack Connector Factory

Slack 서비스 인스턴스를 생성하는 팩토리.
OAuth Token을 조회하여 서비스 인스턴스를 생성.
"""

import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.connectors.slack.auth import get_slack_oauth_service
from catchup.connectors.slack.ingestion_service import SlackIngestionService
from catchup.connectors.slack.metadata_service import SlackMetadataService
from catchup.db.slack import oauth_repository as slack_crud

logger = logging.getLogger(__name__)


async def _resolve_access_token(
    db: Session,
    team_id: str,
) -> str:
    """
    Team ID 기준으로 유효한 Slack Bot Access Token을 반환한다.

    Args:
        db: SQLAlchemy Session
        team_id: Slack Team/Workspace ID

    Returns:
        유효한 Access Token

    Raises:
        HTTPException: Token을 찾을 수 없거나 유효하지 않은 경우
    """
    # Token 조회
    token_record = slack_crud.get_slack_token_by_team_id(db, team_id)
    if not token_record:
        raise HTTPException(
            status_code=404,
            detail=f"Slack 연결을 찾을 수 없습니다: {team_id}",
        )

    # 유효한 Access Token 획득
    slack_service = get_slack_oauth_service()
    try:
        access_token = await slack_service.get_valid_access_token(db, token_record)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get valid access token for team_id={team_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Token 획득 중 오류가 발생했습니다: {str(e)}",
        )

    return access_token


async def create_slack_ingestion_service(
    db: Session,
    team_id: str,
) -> SlackIngestionService:
    """
    Event 단위 SlackIngestionService 인스턴스 생성.
    """
    access_token = await _resolve_access_token(db, team_id)

    repository = PGVectorRepository(
        embeddings=get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()
    )

    service = SlackIngestionService(
        repository=repository,
        team_id=team_id,
        access_token=access_token,
    )
    await service.initialize()

    return service


async def create_slack_metadata_service(
    db: Session,
    team_id: str,
) -> SlackMetadataService:
    """
    설치 직후 메타데이터 수집용 SlackMetadataService 인스턴스 생성.
    """
    access_token = await _resolve_access_token(db, team_id)

    service = SlackMetadataService(
        team_id=team_id,
        access_token=access_token,
    )
    await service.initialize()
    return service
