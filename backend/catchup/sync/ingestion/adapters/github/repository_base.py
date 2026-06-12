from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from datetime import datetime
from typing import Any

import structlog
from langchain_core.documents import Document

from catchup.components.summarizer import SummarizeRequest
from catchup.components.summarizer import SummarizerService
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.components.vector_db.v2 import VectorStore
from catchup.connectors.github.client import GitHubApiClient
from catchup.connectors.github.client import GitHubRateLimitError
from catchup.sync.audit import SyncAuditContext
from catchup.sync.ingestion.adapters.github.repository_document_builder import (
    GithubRepositoryDocumentBuilder,
)
from catchup.sync.ingestion.adapters.github.repository_document_builder import (
    document_synced_at,
)
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubIssueDocumentBundle,
)
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubPrDocumentBundle,
)
from catchup.sync.ingestion.adapters.github.repository_models import GithubRepoRef
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubRepositoryV2DocumentBuildResult,
)
from catchup.sync.ingestion.adapters.github.repository_ref_resolver import (
    GithubRepositoryRefResolver,
)
from catchup.sync.ingestion.adapters.github.repository_user_mapping import (
    GithubRepositoryUserMapper,
)
from catchup.sync.ingestion.document_builders.github import GithubTransformer
from catchup.sync.ingestion.dual_write import DualWriter
from catchup.sync.ingestion.dual_write import DualWriteResult
from catchup.sync.ingestion.dual_write import apply_page_content_to_vector_content
from catchup.sync.ingestion.vector_records import GithubIssueV2RecordMapper
from catchup.sync.ingestion.vector_records import GithubPrV2RecordMapper

logger = structlog.get_logger(__name__)
GITHUB_GRAPHQL_BATCH_SIZE = 50


class GithubRepositoryAdapterBase:
    """Shared GitHub repository adapter utilities."""

    def __init__(
        self,
        *,
        installation_id: int,
        client: GitHubApiClient,
        repository: PGVectorRepository,
        summarizer: SummarizerService | None = None,
        vector_store: VectorStore | None = None,
        transformer: GithubTransformer | None = None,
    ) -> None:
        self.installation_id = installation_id
        self.client = client
        self.repository = repository
        self.summarizer = summarizer
        self.vector_store = vector_store
        self.transformer = transformer or GithubTransformer()
        self.issue_v2_mapper = GithubIssueV2RecordMapper()
        self.pr_v2_mapper = GithubPrV2RecordMapper()
        self.repo_ref_resolver = GithubRepositoryRefResolver(installation_id)
        self.user_mapper = GithubRepositoryUserMapper()
        self.document_builder = GithubRepositoryDocumentBuilder(
            installation_id=installation_id,
            transformer=self.transformer,
            user_mapper=self.user_mapper,
            issue_v2_mapper=self.issue_v2_mapper,
            pr_v2_mapper=self.pr_v2_mapper,
        )

    async def _get_repo_ref(self, repo_id: int) -> GithubRepoRef:
        return await self.repo_ref_resolver.get_repo_ref(repo_id)

    async def _fetch_issue_nodes(
        self,
        *,
        owner: str,
        repo: str,
        issue_ids: list[str],
    ) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
        return await self._fetch_issue_nodes_batch(
            owner=owner,
            repo=repo,
            issue_ids=issue_ids,
        )

    async def _fetch_issue_nodes_batch(
        self,
        *,
        owner: str,
        repo: str,
        issue_ids: list[str],
    ) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
        return await self._fetch_numbered_nodes_batch(
            owner=owner,
            repo=repo,
            record_ids=issue_ids,
            record_type="issue",
            log_event="github_issue_batch_fetch_failed",
            fetch_nodes=self.client.get_issues_graphql,
        )

    async def _fetch_pull_request_nodes(
        self,
        *,
        owner: str,
        repo: str,
        pull_request_ids: list[str],
    ) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
        return await self._fetch_pull_request_nodes_batch(
            owner=owner,
            repo=repo,
            pull_request_ids=pull_request_ids,
        )

    async def _fetch_pull_request_nodes_batch(
        self,
        *,
        owner: str,
        repo: str,
        pull_request_ids: list[str],
    ) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
        return await self._fetch_numbered_nodes_batch(
            owner=owner,
            repo=repo,
            record_ids=pull_request_ids,
            record_type="pull_request",
            log_event="github_pr_batch_fetch_failed",
            fetch_nodes=self.client.get_pull_requests_graphql,
        )

    async def _fetch_numbered_nodes_batch(
        self,
        *,
        owner: str,
        repo: str,
        record_ids: list[str],
        record_type: str,
        log_event: str,
        fetch_nodes: Callable[
            [str, str, list[int]],
            Awaitable[dict[str, dict[str, Any]]],
        ],
    ) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
        if not record_ids:
            return [], []

        valid_ids: list[str] = []
        valid_numbers: list[int] = []
        failed_ids: list[str] = []
        for record_id in record_ids:
            try:
                number = int(record_id)
            except ValueError:
                failed_ids.append(record_id)
                continue
            valid_ids.append(record_id)
            valid_numbers.append(number)

        if not valid_numbers:
            return [], failed_ids

        items: list[tuple[str, dict[str, Any]]] = []
        for start in range(0, len(valid_ids), GITHUB_GRAPHQL_BATCH_SIZE):
            id_batch = valid_ids[start : start + GITHUB_GRAPHQL_BATCH_SIZE]
            number_batch = valid_numbers[start : start + GITHUB_GRAPHQL_BATCH_SIZE]
            try:
                data_by_number = await fetch_nodes(owner, repo, number_batch)
            except GitHubRateLimitError:
                raise
            except Exception as exc:
                logger.warning(
                    log_event,
                    connector="github",
                    operation="repair",
                    installation_id=self.installation_id,
                    owner=owner,
                    repo=repo,
                    record_type=record_type,
                    record_count=len(id_batch),
                    error=str(exc),
                    exc_info=True,
                )
                failed_ids.extend(id_batch)
                continue

            for record_id in id_batch:
                data = data_by_number.get(record_id)
                if data is None:
                    failed_ids.append(record_id)
                    continue
                items.append((record_id, data))

        return items, failed_ids

    def _build_issue_batch_documents_sync(
        self,
        owner: str,
        repo: str,
        issue_batch: list[dict[str, Any]],
    ) -> tuple[list[Document], list[str], int]:
        return self.document_builder.build_issue_batch_documents_sync(
            owner,
            repo,
            issue_batch,
        )

    def _build_issue_batch_bundles_sync(
        self,
        owner: str,
        repo: str,
        issue_batch: list[dict[str, Any]],
    ) -> tuple[list[GithubIssueDocumentBundle], list[str], int]:
        return self.document_builder.build_issue_batch_bundles_sync(
            owner,
            repo,
            issue_batch,
        )

    def _build_pull_request_batch_bundles_sync(
        self,
        owner: str,
        repo: str,
        pr_batch: list[dict[str, Any]],
    ) -> tuple[list[GithubPrDocumentBundle], list[str], int]:
        return self.document_builder.build_pull_request_batch_bundles_sync(
            owner,
            repo,
            pr_batch,
        )

    def _build_issue_documents_sync(
        self,
        owner: str,
        repo: str,
        issue_items: list[tuple[str, dict[str, Any]]],
    ) -> tuple[list[Document], list[str]]:
        return self.document_builder.build_issue_documents_sync(
            owner,
            repo,
            issue_items,
        )

    def _build_issue_document_bundles_sync(
        self,
        owner: str,
        repo: str,
        issue_items: list[tuple[str, dict[str, Any]]],
    ) -> tuple[list[GithubIssueDocumentBundle], list[str]]:
        return self.document_builder.build_issue_document_bundles_sync(
            owner,
            repo,
            issue_items,
        )

    def _build_pull_request_document_bundles_sync(
        self,
        owner: str,
        repo: str,
        pr_items: list[tuple[str, dict[str, Any]]],
    ) -> tuple[list[GithubPrDocumentBundle], list[str]]:
        return self.document_builder.build_pull_request_document_bundles_sync(
            owner,
            repo,
            pr_items,
        )

    def _build_v2_documents_from_pr_bundles(
        self,
        *,
        owner: str,
        repo: str,
        bundles: list[GithubPrDocumentBundle],
    ) -> GithubRepositoryV2DocumentBuildResult:
        return self.document_builder.build_v2_documents_from_pr_bundles(
            owner=owner,
            repo=repo,
            bundles=bundles,
        )

    def _build_v2_documents_from_issue_bundles(
        self,
        *,
        owner: str,
        repo: str,
        bundles: list[GithubIssueDocumentBundle],
    ) -> GithubRepositoryV2DocumentBuildResult:
        return self.document_builder.build_v2_documents_from_issue_bundles(
            owner=owner,
            repo=repo,
            bundles=bundles,
        )

    @staticmethod
    def _apply_v1_page_content_to_v2_content(
        *,
        v1_documents: list[Document],
        v2_documents: list[Document],
        entity_type: str,
    ) -> list[Document]:
        return apply_page_content_to_vector_content(
            source_documents=v1_documents,
            vector_documents=v2_documents,
            connector="github",
            entity_type=entity_type,
            operation=f"{_github_dual_write_log_token(entity_type)}_v2_dual_write",
        )

    async def _summarize_documents(
        self,
        documents: list[Document],
        *,
        repo_full_name: str,
        entity_type: str,
        audit_context: SyncAuditContext | None = None,
    ) -> list[Document]:
        if not self.summarizer or not documents:
            return documents

        requests = []
        for doc in documents:
            content = doc.metadata.get("contextual_content", doc.page_content)
            doc_entity_type = doc.metadata.get("entity_type", entity_type)
            source_type = f"github_{doc_entity_type}"
            requests.append(SummarizeRequest(content=content, source_type=source_type))

        summarized = await self.summarizer.summarize_batch(
            requests,
            audit_context=audit_context,
            context=(
                f"entity_type={entity_type},repo={repo_full_name},"
                f"doc_count={len(documents)}"
            ),
        )

        for doc, summary in zip(documents, summarized):
            doc.page_content = summary

        logger.debug(
            "github_documents_summarized",
            connector="github",
            repo_full_name=repo_full_name,
            entity_type=entity_type,
            doc_count=len(documents),
        )
        return documents

    async def _upsert_v1_v2_documents_dual_write(
        self,
        *,
        v1_documents: list[Document],
        v2_documents: list[Document],
        ids: list[str],
        audit_context: SyncAuditContext | None,
        context: str,
    ) -> DualWriteResult:
        return await DualWriter(
            repository=self.repository,
            vector_store=self.vector_store,
        ).upsert_documents(
            source_documents=v1_documents,
            vector_documents=v2_documents,
            ids=ids,
            audit_context=audit_context,
            context=context,
        )

    @staticmethod
    def _document_synced_at(document: Document) -> datetime:
        return document_synced_at(document)


def _github_dual_write_log_token(entity_type: str) -> str:
    return "pr" if entity_type == "pull_request" else entity_type
