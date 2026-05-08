from __future__ import annotations

import logging

from fastapi.concurrency import run_in_threadpool

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.summarizer import get_summarizer_service
from catchup.components.vector_db.factory import get_pgvector_repository
from catchup.connector_core.adapters.jira.issue_dependencies import (
    JiraIssueIngestionDependencies,
)
from catchup.connectors.atlassian.exceptions import AtlassianTokenExpiredError
from catchup.connectors.atlassian.exceptions import AtlassianTokenNotFoundError
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.connectors.atlassian.token_manager import AtlassianTokenManager
from catchup.connectors.atlassian.token_manager import AtlassianTokenProvider
from catchup.connectors.jira.client import JiraApiClient
from catchup.connectors.jira.field_mapper import JiraFieldMapper
from catchup.connectors.jira.transformers import JiraTransformer
from catchup.db.atlassian import oauth_repository
from catchup.db.engine import SessionLocal
from catchup.sync.common.exceptions import SyncConnectorException
from catchup.sync.common.exceptions import SyncInternalException

logger = logging.getLogger(__name__)


def _load_site_url_db(cloud_id: str) -> str:
    with SessionLocal() as db:
        token_record = oauth_repository.get_token_by_cloud_id(db, cloud_id)
        if token_record is None:
            raise AtlassianTokenNotFoundError(cloud_id)
        return token_record.site_url or ""


async def create_jira_issue_ingestion_dependencies(
    *,
    cloud_id: str,
    enable_summarization: bool = True,
) -> JiraIssueIngestionDependencies:
    token_manager = AtlassianTokenManager(
        oauth_client=AtlassianOAuthClient(),
        oauth_repository=oauth_repository,
    )

    try:
        token_provider = AtlassianTokenProvider(token_manager)
        site_url = await run_in_threadpool(_load_site_url_db, cloud_id)
    except AtlassianTokenNotFoundError as exc:
        raise SyncConnectorException(
            f"Jira 연결을 찾을 수 없습니다: {cloud_id}",
            metadata={"cloud_id": cloud_id},
        ) from exc
    except AtlassianTokenExpiredError as exc:
        raise SyncConnectorException(
            f"Jira 인증이 만료되었습니다. 재연결이 필요합니다: {cloud_id}",
            metadata={"cloud_id": cloud_id},
        ) from exc
    except Exception as exc:
        logger.error(
            "jira_issue_dependencies_token_resolution_failed",
            extra={"cloud_id": cloud_id},
            exc_info=True,
        )
        raise SyncInternalException(
            "Jira access token 획득 중 오류가 발생했습니다",
            metadata={"cloud_id": cloud_id},
        ) from exc

    try:
        client = JiraApiClient(cloud_id, token_provider)
        field_mapper = JiraFieldMapper(client)
        await field_mapper.initialize()
        repository = get_pgvector_repository(
            embeddings=get_embedding_service(
                EmbeddingProvider.AWS_BEDROCK
            ).get_embedder()
        )
        repository.ensure_initialized()
        summarizer = get_summarizer_service() if enable_summarization else None
        return JiraIssueIngestionDependencies(
            cloud_id=cloud_id,
            site_url=(site_url or "").rstrip("/"),
            client=client,
            field_mapper=field_mapper,
            transformer=JiraTransformer(field_mapper),
            repository=repository,
            summarizer=summarizer,
        )
    except Exception as exc:
        logger.error(
            "jira_issue_dependencies_initialization_failed",
            extra={"cloud_id": cloud_id},
            exc_info=True,
        )
        raise SyncInternalException(
            "Jira issue ingestion dependencies 초기화에 실패했습니다",
            metadata={"cloud_id": cloud_id},
        ) from exc
