"""
Slack Connector Factory

Slack 서비스 인스턴스를 생성하는 팩토리.
OAuth Token을 조회하여 서비스 인스턴스를 생성.
"""

import logging

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.factory import get_pgvector_repository
from catchup.connectors.slack.auth import get_slack_oauth_service
from catchup.connectors.slack.ingestion_service import SlackIngestionService
from catchup.connectors.slack.metadata_service import SlackMetadataService
from catchup.db.engine import SessionLocal
from catchup.db.slack import oauth_repository as slack_crud
from catchup.sync.common.exceptions import SyncConnectorError, SyncInternalError

logger = logging.getLogger(__name__)


def _load_token_db(team_id: str):
    with SessionLocal() as session:
        return slack_crud.get_slack_token_by_team_id(session, team_id)


async def _resolve_access_token(
    team_id: str,
) -> str:
    token_record = await run_in_threadpool(_load_token_db, team_id)
    if not token_record:
        raise SyncConnectorError(
            f"Slack 연결을 찾을 수 없습니다: {team_id}",
            metadata={"team_id": team_id},
        )

    slack_service = get_slack_oauth_service()
    try:
        return await slack_service.get_valid_access_token(token_record)
    except HTTPException as exc:
        message = (
            exc.detail
            if isinstance(exc.detail, str)
            else "Slack 인증 정보를 확인할 수 없습니다"
        )
        error_cls = SyncInternalError if exc.status_code >= 500 else SyncConnectorError
        raise error_cls(
            message,
            metadata={"team_id": team_id},
        ) from exc
    except Exception as exc:
        logger.error(
            "[SLACK][FACTORY] Failed to resolve access token: team_id=%s, error=%s",
            team_id,
            exc,
            exc_info=True,
        )
        raise SyncInternalError(
            "Slack access token 획득 중 오류가 발생했습니다",
            metadata={"team_id": team_id},
        ) from exc


async def create_slack_ingestion_service(
    team_id: str,
) -> SlackIngestionService:
    access_token = await _resolve_access_token(team_id)

    try:
        repository = get_pgvector_repository(
            embeddings=get_embedding_service(
                EmbeddingProvider.AWS_BEDROCK
            ).get_embedder()
        )
        service = SlackIngestionService(
            repository=repository,
            team_id=team_id,
            access_token=access_token,
        )
        await service.initialize()
        return service
    except Exception as exc:
        logger.error(
            "[SLACK][FACTORY] Failed to initialize ingestion service: team_id=%s, error=%s",
            team_id,
            exc,
            exc_info=True,
        )
        raise SyncInternalError(
            "Slack ingestion service 초기화에 실패했습니다",
            metadata={"team_id": team_id},
        ) from exc


async def create_slack_metadata_service(
    team_id: str,
) -> SlackMetadataService:
    access_token = await _resolve_access_token(team_id)

    try:
        service = SlackMetadataService(
            team_id=team_id,
            access_token=access_token,
        )
        await service.initialize()
        return service
    except Exception as exc:
        logger.error(
            "[SLACK][FACTORY] Failed to initialize metadata service: team_id=%s, error=%s",
            team_id,
            exc,
            exc_info=True,
        )
        raise SyncInternalError(
            "Slack metadata service 초기화에 실패했습니다",
            metadata={"team_id": team_id},
        ) from exc
