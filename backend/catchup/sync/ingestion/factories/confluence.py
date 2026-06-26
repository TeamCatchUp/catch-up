"""
Confluence Connector Factory

ConfluenceIngestionService 인스턴스를 생성하는 팩토리.
AtlassianTokenManager로 OAuth Token을 조회하여 서비스 인스턴스를 생성.
"""

import logging

from fastapi.concurrency import run_in_threadpool

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.vector_db.factory import get_pgvector_repository
from catchup.components.vector_db.factory import get_v2_knowledge_repository
from catchup.components.vector_db.factory import get_v2_vector_store
from catchup.connectors.atlassian.exceptions import AtlassianTokenExpiredError
from catchup.connectors.atlassian.exceptions import AtlassianTokenNotFoundError
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.connectors.atlassian.token_manager import AtlassianTokenManager
from catchup.connectors.atlassian.token_manager import AtlassianTokenProvider
from catchup.db.atlassian import oauth_repository
from catchup.db.engine import SessionLocal
from catchup.sync.common.exceptions import SyncConnectorException
from catchup.sync.common.exceptions import SyncInternalException
from catchup.sync.ingestion.adapters.confluence import ConfluenceV2BackfillAdapter
from catchup.sync.ingestion.services.confluence import ConfluenceIngestionService

logger = logging.getLogger(__name__)


def _load_token_record_db(cloud_id: str):
    with SessionLocal() as db:
        token_record = oauth_repository.get_token_by_cloud_id(db, cloud_id)
        if token_record is None:
            raise AtlassianTokenNotFoundError(cloud_id)
        return token_record


async def create_confluence_ingestion_service(
    cloud_id: str,
) -> ConfluenceIngestionService:
    token_manager = AtlassianTokenManager(
        oauth_client=AtlassianOAuthClient(),
        oauth_repository=oauth_repository,
    )

    try:
        token_provider = AtlassianTokenProvider(token_manager)
        token_record = await run_in_threadpool(_load_token_record_db, cloud_id)
    except AtlassianTokenNotFoundError as exc:
        raise SyncConnectorException(
            f"Confluence 연결을 찾을 수 없습니다: {cloud_id}",
            metadata={"cloud_id": cloud_id},
        ) from exc
    except AtlassianTokenExpiredError as exc:
        raise SyncConnectorException(
            f"Confluence 인증이 만료되었습니다. 재연결이 필요합니다: {cloud_id}",
            metadata={"cloud_id": cloud_id},
        ) from exc
    except Exception as exc:
        logger.error(
            "[CONFLUENCE][FACTORY] Failed to resolve access token: cloud_id=%s, error=%s",
            cloud_id,
            exc,
            exc_info=True,
        )
        raise SyncInternalException(
            "Confluence access token 획득 중 오류가 발생했습니다",
            metadata={"cloud_id": cloud_id},
        ) from exc

    try:
        site_url = token_record.site_url if token_record else ""
        embedding_service = get_embedding_service(EmbeddingProvider.AWS_BEDROCK)
        repository = get_pgvector_repository(
            embeddings=embedding_service.get_embedder()
        )
        service = ConfluenceIngestionService(
            cloud_id=cloud_id,
            token_provider=token_provider,
            site_url=site_url or "",
            repository=repository,
            embedding_service=embedding_service,
        )
        await service.initialize()
        return service
    except Exception as exc:
        logger.error(
            "[CONFLUENCE][FACTORY] Failed to initialize ingestion service: cloud_id=%s, error=%s",
            cloud_id,
            exc,
            exc_info=True,
        )
        raise SyncInternalException(
            "Confluence ingestion service 초기화에 실패했습니다",
            metadata={"cloud_id": cloud_id},
        ) from exc


async def create_confluence_v2_backfill_adapter(
    cloud_id: str,
) -> ConfluenceV2BackfillAdapter:
    service = await create_confluence_ingestion_service(cloud_id=cloud_id)
    embeddings = get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()
    vector_store = get_v2_vector_store(embeddings)
    await vector_store.initialize()
    return ConfluenceV2BackfillAdapter(
        service=service,
        vector_store=vector_store,
        v2_knowledge_repository=get_v2_knowledge_repository(),
    )
