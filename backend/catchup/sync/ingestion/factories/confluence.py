"""
Confluence Connector Factory

Confluence ingestion dependencies and legacy service instances are assembled here.
AtlassianTokenManager로 OAuth Token을 조회하여 서비스 인스턴스를 생성.
"""

import structlog
from fastapi.concurrency import run_in_threadpool
from langchain.embeddings import Embeddings

from catchup.connectors.atlassian.exceptions import AtlassianTokenExpiredError
from catchup.connectors.atlassian.exceptions import AtlassianTokenNotFoundError
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.connectors.atlassian.token_manager import AtlassianTokenManager
from catchup.connectors.atlassian.token_manager import AtlassianTokenProvider
from catchup.connectors.confluence.client import ConfluenceApiClient
from catchup.db.atlassian import oauth_repository
from catchup.db.engine import SessionLocal
from catchup.sync.common.exceptions import SyncConnectorException
from catchup.sync.common.exceptions import SyncInternalException
from catchup.sync.ingestion.adapters.confluence import ConfluenceSpaceSyncDependencies
from catchup.sync.ingestion.adapters.confluence import ConfluenceV2BackfillAdapter
from catchup.sync.ingestion.document_builders.confluence import ConfluenceTransformer
from catchup.sync.ingestion.factories.knowledge_store import (
    create_knowledge_store_dependencies,
)
from catchup.sync.ingestion.services.confluence import ConfluenceIngestionService

logger = structlog.get_logger(__name__)


def _load_token_record_db(cloud_id: str):
    with SessionLocal() as db:
        token_record = oauth_repository.get_token_by_cloud_id(db, cloud_id)
        if token_record is None:
            raise AtlassianTokenNotFoundError(cloud_id)
        return token_record


async def _resolve_token_provider_and_site_url(
    cloud_id: str,
) -> tuple[AtlassianTokenProvider, str]:
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
            "confluence_factory_token_resolve_failed",
            connector="confluence",
            scope_id=cloud_id,
            exception_type=type(exc).__name__,
            error=str(exc),
            exc_info=True,
        )
        raise SyncInternalException(
            "Confluence access token 획득 중 오류가 발생했습니다",
            metadata={"cloud_id": cloud_id},
        ) from exc

    site_url = token_record.site_url if token_record else ""
    return token_provider, site_url or ""


async def create_confluence_space_sync_dependencies(
    cloud_id: str,
    *,
    embeddings: Embeddings | None = None,
    require_vector_store: bool = False,
) -> ConfluenceSpaceSyncDependencies:
    token_provider, site_url = await _resolve_token_provider_and_site_url(cloud_id)

    try:
        knowledge_store = await create_knowledge_store_dependencies(
            embeddings=embeddings,
            require_vector_store=require_vector_store,
        )
        return ConfluenceSpaceSyncDependencies(
            cloud_id=cloud_id,
            site_url=site_url,
            client=ConfluenceApiClient(cloud_id, token_provider),
            repository=knowledge_store.repository,
            transformer=ConfluenceTransformer(),
            vector_store=knowledge_store.vector_store,
            v2_knowledge_repository=knowledge_store.v2_knowledge_repository,
        )
    except Exception as exc:
        logger.error(
            "confluence_factory_space_sync_dependencies_init_failed",
            connector="confluence",
            scope_id=cloud_id,
            exception_type=type(exc).__name__,
            error=str(exc),
            exc_info=True,
        )
        raise SyncInternalException(
            "Confluence sync dependency 초기화에 실패했습니다",
            metadata={"cloud_id": cloud_id},
        ) from exc


async def create_confluence_ingestion_service(
    cloud_id: str,
) -> ConfluenceIngestionService:
    token_provider, site_url = await _resolve_token_provider_and_site_url(cloud_id)
    try:
        knowledge_store = await create_knowledge_store_dependencies()
        service = ConfluenceIngestionService(
            cloud_id=cloud_id,
            token_provider=token_provider,
            site_url=site_url,
            repository=knowledge_store.repository,
        )
        await service.initialize()
        return service
    except Exception as exc:
        logger.error(
            "confluence_factory_ingestion_service_init_failed",
            connector="confluence",
            scope_id=cloud_id,
            exception_type=type(exc).__name__,
            error=str(exc),
            exc_info=True,
        )
        raise SyncInternalException(
            "Confluence ingestion service 초기화에 실패했습니다",
            metadata={"cloud_id": cloud_id},
        ) from exc


async def create_confluence_v2_backfill_adapter(
    cloud_id: str,
) -> ConfluenceV2BackfillAdapter:
    dependencies = await create_confluence_space_sync_dependencies(
        cloud_id=cloud_id,
        require_vector_store=True,
    )
    return ConfluenceV2BackfillAdapter(
        dependencies=dependencies,
        vector_store=dependencies.vector_store,
        v2_knowledge_repository=dependencies.v2_knowledge_repository,
    )
