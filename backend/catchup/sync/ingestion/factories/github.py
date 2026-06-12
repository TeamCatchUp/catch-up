"""
Github Connector Factory

Github sync ingestion adapter 생성을 위한 팩토리 함수.
"""

import logging
from typing import TypeVar

from fastapi.concurrency import run_in_threadpool
from httpx import HTTPStatusError
from httpx import RequestError

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.summarizer import get_summarizer_service
from catchup.components.vector_db.factory import get_pgvector_repository
from catchup.components.vector_db.factory import get_v2_vector_store
from catchup.configs.config import settings
from catchup.connectors.github.auth import get_github_app_service
from catchup.connectors.github.client import GitHubApiClient
from catchup.db.engine import SessionLocal
from catchup.db.github.installation_repository import (
    get_installation_by_installation_id,
)
from catchup.sync.common.exceptions import SyncConnectorException
from catchup.sync.common.exceptions import SyncInternalException
from catchup.sync.ingestion.adapters.github import GithubPrV2BackfillAdapter
from catchup.sync.ingestion.adapters.github import GithubRepositoryFullSyncAdapter
from catchup.sync.ingestion.adapters.github import (
    GithubRepositoryIncrementalSyncAdapter,
)
from catchup.sync.ingestion.adapters.github import GithubRepositoryRepairAdapter
from catchup.sync.ingestion.adapters.github.repository_base import (
    GithubRepositoryAdapterBase,
)

logger = logging.getLogger(__name__)

GithubRepositoryAdapterT = TypeVar(
    "GithubRepositoryAdapterT",
    bound=GithubRepositoryAdapterBase,
)


def _extract_http_error_message(exc: HTTPStatusError) -> str:
    response = exc.response

    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

    text = response.text.strip()
    if text:
        return text

    return str(exc)


def _load_installation_sync(installation_id: int):
    with SessionLocal() as db:
        return get_installation_by_installation_id(db, installation_id)


async def _create_github_repository_adapter(
    installation_id: int,
    adapter_cls: type[GithubRepositoryAdapterT],
    *,
    force_v2_vector_store: bool = False,
) -> GithubRepositoryAdapterT:
    installation = await run_in_threadpool(_load_installation_sync, installation_id)

    if not installation:
        raise SyncConnectorException(
            f"Github Installation not found: {installation_id}",
            metadata={"installation_id": installation_id},
        )

    try:
        github_app_service = get_github_app_service()
        access_token = await github_app_service.get_installation_access_token(
            installation_id
        )

        embeddings = get_embedding_service(EmbeddingProvider.AWS_BEDROCK).get_embedder()
        repository = get_pgvector_repository(embeddings=embeddings)
        repository.ensure_initialized()
        v2_vector_store = None
        if settings.VECTOR_STORE_V2_DUAL_WRITE_ENABLED or force_v2_vector_store:
            v2_vector_store = get_v2_vector_store(embeddings)
            await v2_vector_store.initialize()

        return adapter_cls(
            installation_id=installation_id,
            client=GitHubApiClient(
                access_token,
                refresh_access_token=lambda: github_app_service.get_installation_access_token(
                    installation_id,
                    force_refresh=True,
                ),
            ),
            repository=repository,
            summarizer=get_summarizer_service(),
            pr_v2_vector_store=v2_vector_store,
        )
    except HTTPStatusError as exc:
        status_code = exc.response.status_code
        detail = _extract_http_error_message(exc)
        metadata = {
            "installation_id": installation_id,
            "status_code": status_code,
            "detail": detail,
        }

        if status_code == 401:
            raise SyncConnectorException(
                "GitHub App 인증에 실패했습니다. GITHUB_APP_ID와 GITHUB_APP_PRIVATE_KEY 조합, 앱 키 재발급 여부를 확인하세요.",
                metadata=metadata,
                code="github_auth_failed",
            ) from exc

        if 400 <= status_code < 500:
            raise SyncConnectorException(
                "GitHub installation access token 발급에 실패했습니다.",
                metadata=metadata,
                code="github_installation_token_failed",
            ) from exc

        logger.error(
            "[GITHUB][FACTORY] GitHub API request failed: installation_id=%s, status_code=%s, detail=%s",
            installation_id,
            status_code,
            detail,
            exc_info=True,
        )
        raise SyncInternalException(
            "GitHub API 요청 중 오류가 발생했습니다",
            metadata=metadata,
            code="github_api_failed",
        ) from exc
    except RequestError as exc:
        logger.error(
            "[GITHUB][FACTORY] GitHub API network request failed: installation_id=%s, error=%s",
            installation_id,
            exc,
            exc_info=True,
        )
        raise SyncInternalException(
            "GitHub API 네트워크 요청 중 오류가 발생했습니다",
            metadata={"installation_id": installation_id},
            code="github_api_network_failed",
        ) from exc
    except SyncConnectorException:
        raise
    except Exception as exc:
        logger.error(
            "[GITHUB][FACTORY] Failed to initialize ingestion adapter: installation_id=%s, error=%s",
            installation_id,
            exc,
            exc_info=True,
        )
        raise SyncInternalException(
            "Github ingestion adapter initialization failed",
            metadata={"installation_id": installation_id},
        ) from exc


async def create_github_repository_full_sync_adapter(
    installation_id: int,
) -> GithubRepositoryFullSyncAdapter:
    return await _create_github_repository_adapter(
        installation_id,
        GithubRepositoryFullSyncAdapter,
    )


async def create_github_repository_incremental_sync_adapter(
    installation_id: int,
) -> GithubRepositoryIncrementalSyncAdapter:
    return await _create_github_repository_adapter(
        installation_id,
        GithubRepositoryIncrementalSyncAdapter,
    )


async def create_github_repository_repair_adapter(
    installation_id: int,
) -> GithubRepositoryRepairAdapter:
    return await _create_github_repository_adapter(
        installation_id,
        GithubRepositoryRepairAdapter,
    )


async def create_github_pr_v2_backfill_adapter(
    installation_id: int,
) -> GithubPrV2BackfillAdapter:
    return await _create_github_repository_adapter(
        installation_id,
        GithubPrV2BackfillAdapter,
        force_v2_vector_store=True,
    )
