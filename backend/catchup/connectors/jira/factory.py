"""
Jira Connector Factory

JiraIngestionService 인스턴스를 생성하는 팩토리.
OAuth Token을 조회하여 서비스 인스턴스를 생성.
"""

import logging

from fastapi.concurrency import run_in_threadpool

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.factory import get_pgvector_repository
from catchup.connectors.atlassian.exceptions import (
    AtlassianTokenExpiredError,
    AtlassianTokenNotFoundError,
)
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.connectors.atlassian.token_manager import (
    AtlassianTokenManager,
    AtlassianTokenProvider,
)
from catchup.connectors.jira.service import JiraIngestionService
from catchup.db.atlassian import oauth_repository
from catchup.db.engine import SessionLocal
from catchup.sync.common.exceptions import SyncConnectorError, SyncInternalError

logger = logging.getLogger(__name__)


def _load_site_url_db(cloud_id: str) -> str:
    with SessionLocal() as db:
        token_record = oauth_repository.get_token_by_cloud_id(
            db,
            cloud_id,
        )
        if token_record is None:
            raise AtlassianTokenNotFoundError(cloud_id)
        return token_record.site_url or ""


async def create_jira_ingestion_service(
    cloud_id: str,
) -> JiraIngestionService:
    token_manager = AtlassianTokenManager(
        oauth_client=AtlassianOAuthClient(),
        oauth_repository=oauth_repository,
    )

    try:
        token_provider = AtlassianTokenProvider(token_manager)
        site_url = await run_in_threadpool(_load_site_url_db, cloud_id)
    except AtlassianTokenNotFoundError as exc:
        raise SyncConnectorError(
            f"Jira 연결을 찾을 수 없습니다: {cloud_id}",
            metadata={"cloud_id": cloud_id},
        ) from exc
    except AtlassianTokenExpiredError as exc:
        raise SyncConnectorError(
            f"Jira 인증이 만료되었습니다. 재연결이 필요합니다: {cloud_id}",
            metadata={"cloud_id": cloud_id},
        ) from exc
    except Exception as exc:
        logger.error(
            "[JIRA][FACTORY] Failed to resolve access token: cloud_id=%s, error=%s",
            cloud_id,
            exc,
            exc_info=True,
        )
        raise SyncInternalError(
            "Jira access token 획득 중 오류가 발생했습니다",
            metadata={"cloud_id": cloud_id},
        ) from exc

    try:
        repository = get_pgvector_repository(
            embeddings=get_embedding_service(
                EmbeddingProvider.AWS_BEDROCK
            ).get_embedder()
        )
        service = JiraIngestionService(
            repository=repository,
            cloud_id=cloud_id,
            token_provider=token_provider,
            site_url=site_url or "",
        )
        await service.initialize()
        return service
    except Exception as exc:
        logger.error(
            "[JIRA][FACTORY] Failed to initialize ingestion service: cloud_id=%s, error=%s",
            cloud_id,
            exc,
            exc_info=True,
        )
        raise SyncInternalError(
            "Jira ingestion service 초기화에 실패했습니다",
            metadata={"cloud_id": cloud_id},
        ) from exc
