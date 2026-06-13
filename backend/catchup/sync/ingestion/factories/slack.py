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
from catchup.components.summarizer import get_summarizer_service
from catchup.components.vector_db.factory import get_pgvector_repository
from catchup.connectors.slack.auth import get_slack_oauth_service
from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.connectors.slack.client import SlackConnectorApiError
from catchup.connectors.slack.client import SlackRateLimitError
from catchup.db.engine import SessionLocal
from catchup.db.slack import oauth_repository as slack_crud
from catchup.sync.common.exceptions import SyncConnectorException
from catchup.sync.common.exceptions import SyncInternalException
from catchup.sync.ingestion.adapters.slack import SlackMessageFullSyncAdapter
from catchup.sync.ingestion.adapters.slack import SlackMessageIncrementalSyncAdapter
from catchup.sync.ingestion.services.slack import SlackIngestionService

logger = logging.getLogger(__name__)


def _load_token_db(team_id: str):
    with SessionLocal() as db:
        return slack_crud.get_slack_token_by_team_id(db, team_id)


async def _resolve_access_token(
    team_id: str,
    token_record=None,
) -> str:
    if token_record is None:
        token_record = await run_in_threadpool(_load_token_db, team_id)
    if not token_record:
        raise SyncConnectorException(
            f"Slack 연결을 찾을 수 없습니다: {team_id}",
            metadata={"team_id": team_id},
        )

    slack_service = get_slack_oauth_service()
    try:
        return await slack_service.get_valid_access_token(token_record)
    except SlackRateLimitError:
        raise
    except SlackConnectorApiError as exc:
        error_cls = (
            SyncInternalException
            if exc.status_code is not None and exc.status_code >= 500
            else SyncConnectorException
        )
        raise error_cls(
            exc.message,
            metadata={"team_id": team_id, **exc.metadata},
        ) from exc
    except HTTPException as exc:
        message = (
            exc.detail
            if isinstance(exc.detail, str)
            else "Slack 인증 정보를 확인할 수 없습니다"
        )
        error_cls = SyncInternalException if exc.status_code >= 500 else SyncConnectorException
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
        raise SyncInternalException(
            "Slack access token 획득 중 오류가 발생했습니다",
            metadata={"team_id": team_id},
        ) from exc

def _build_repository():
    repository = get_pgvector_repository(
        embeddings=get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()
    )
    repository.ensure_initialized()
    return repository


async def _load_token_or_raise(team_id: str):
    token_record = await run_in_threadpool(_load_token_db, team_id)
    if not token_record:
        raise SyncConnectorException(
            f"Slack 연결을 찾을 수 없습니다: {team_id}",
            metadata={"team_id": team_id},
        )
    return token_record


async def _create_slack_message_adapter(
    team_id: str,
    adapter_cls,
):
    token_record = await _load_token_or_raise(team_id)
    access_token = await _resolve_access_token(team_id, token_record=token_record)

    try:
        adapter = adapter_cls(
            team_id=team_id,
            client=SlackApiClientWrapper(access_token, team_id),
            repository=_build_repository(),
            bot_user_id=token_record.bot_user_id,
            summarizer=get_summarizer_service(),
        )
        await run_in_threadpool(adapter._load_ingestion_context)
        return adapter
    except Exception as exc:
        logger.error(
            "[SLACK][FACTORY] Failed to initialize message adapter: team_id=%s, adapter=%s, error=%s",
            team_id,
            getattr(adapter_cls, "__name__", str(adapter_cls)),
            exc,
            exc_info=True,
        )
        raise SyncInternalException(
            "Slack message adapter 초기화에 실패했습니다",
            metadata={"team_id": team_id},
        ) from exc


async def create_slack_message_full_sync_adapter(
    team_id: str,
) -> SlackMessageFullSyncAdapter:
    return await _create_slack_message_adapter(
        team_id,
        SlackMessageFullSyncAdapter,
    )


async def create_slack_message_incremental_sync_adapter(
    team_id: str,
) -> SlackMessageIncrementalSyncAdapter:
    return await _create_slack_message_adapter(
        team_id,
        SlackMessageIncrementalSyncAdapter,
    )


async def create_slack_ingestion_service(
    team_id: str,
) -> SlackIngestionService:
    token_record = await _load_token_or_raise(team_id)
    access_token = await _resolve_access_token(team_id, token_record=token_record)

    try:
        service = SlackIngestionService(
            repository=_build_repository(),
            team_id=team_id,
            access_token=access_token,
            bot_user_id=token_record.bot_user_id,
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
        raise SyncInternalException(
            "Slack ingestion service 초기화에 실패했습니다",
            metadata={"team_id": team_id},
        ) from exc
