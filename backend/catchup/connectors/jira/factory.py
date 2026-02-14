"""
Jira Connector Factory

JiraIngestionService 인스턴스를 생성하는 팩토리.
OAuth Token을 조회하여 서비스 인스턴스를 생성.
"""

import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from catchup.connectors.jira.auth import get_jira_oauth_service
from catchup.connectors.jira.service import JiraIngestionService
from catchup.db.jira import oauth_repository

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
    token_record = oauth_repository.get_jira_token_by_cloud_id(db, cloud_id)
    if not token_record:
        raise HTTPException(
            status_code=404,
            detail=f"Jira 연결을 찾을 수 없습니다: {cloud_id}",
        )

    jira_service = get_jira_oauth_service()
    try:
        access_token = await jira_service.get_valid_access_token(db, token_record)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get valid access token for cloud_id={cloud_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Token 획득 중 오류가 발생했습니다: {str(e)}",
        )

    site_url = token_record.site_url or ""
    service = JiraIngestionService(cloud_id, access_token, site_url)
    await service.initialize()
    return service
