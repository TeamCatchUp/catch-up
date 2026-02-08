"""
Slack Connector Factory

SlackIngestionService 인스턴스를 생성하는 팩토리.
OAuth Token을 조회하여 서비스 인스턴스를 생성.

사용법:
    service = await create_slack_ingestion_service(db, team_id)
    await service.full_sync(db)
"""

import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from catchup.auth.slack.app import get_slack_oauth_service
from catchup.connectors.slack.service import SlackIngestionService
from catchup.db import slack_oauth as slack_crud

logger = logging.getLogger(__name__)


async def create_slack_ingestion_service(
    db: Session,
    team_id: str,
) -> SlackIngestionService:
    """
    SlackIngestionService 인스턴스 생성

    Args:
        db: SQLAlchemy Session
        team_id: Slack Team/Workspace ID

    Returns:
        초기화된 SlackIngestionService

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

    # Service 인스턴스 생성 및 초기화
    service = SlackIngestionService(team_id, access_token)
    await service.initialize()

    return service
