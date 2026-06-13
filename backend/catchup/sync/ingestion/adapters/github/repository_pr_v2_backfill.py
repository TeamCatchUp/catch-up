from __future__ import annotations

from fastapi.concurrency import run_in_threadpool
from langchain_core.documents import Document

from catchup.sync.ingestion.adapters.github.repository_base import (
    GithubRepositoryAdapterBase,
)
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubPrV2BackfillExecutionRequest,
)
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubPrV2BackfillSeed,
)
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubRepositoryFetchResult,
)
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubRepositoryPersistResult,
)
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubRepositorySummaryResult,
)
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubRepositorySyncExecutionResult,
)
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubRepositoryTransformResult,
)
from catchup.sync.ingestion.schemas import SyncWindow


class GithubPrV2BackfillAdapter(GithubRepositoryAdapterBase):
    """Backfill GitHub PR v2 records by hydrating v1 seeds through GitHub API."""

    async def fetch(
        self,
        *,
        execution: GithubPrV2BackfillExecutionRequest,
        sync_window: SyncWindow,
    ) -> GithubRepositoryFetchResult:
        _ = sync_window
        items, failed_ids = await self._fetch_pull_request_nodes(
            owner=execution.owner,
            repo=execution.repo,
            pull_request_ids=[seed.record_id for seed in execution.seeds],
        )
        return GithubRepositoryFetchResult(
            requested_count=len(execution.seeds),
            exact_items=tuple(items),
            failed_record_ids=tuple(failed_ids),
            record_type="pull_request",
            owner=execution.owner,
            repo=execution.repo,
            repo_full_name=execution.repo_full_name,
        )

    async def transform(
        self,
        *,
        execution: GithubPrV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        fetched: GithubRepositoryFetchResult,
    ) -> GithubRepositoryTransformResult:
        _ = sync_window
        seed_by_record_id = _seed_by_record_id(execution.seeds)
        bundles, build_failed_ids = await run_in_threadpool(
            self._build_pull_request_document_bundles_sync,
            execution.owner,
            execution.repo,
            list(fetched.exact_items),
        )

        v2_documents: list[Document] = []
        document_ids: list[str] = []
        transform_failed_ids: list[str] = []

        for bundle in bundles:
            record_id = str(bundle.pull_request.number)
            seed = seed_by_record_id.get(record_id)
            if seed is None:
                transform_failed_ids.append(record_id)
                continue

            try:
                document = self.pr_v2_mapper.to_document(
                    bundle.pull_request,
                    owner=execution.owner,
                    repo=execution.repo,
                    installation_id=self.scope_id,
                    content=seed.content,
                    synced_at=self._document_synced_at(bundle.document),
                )
            except Exception:
                transform_failed_ids.append(record_id)
                continue

            if document.id != seed.langchain_id:
                document = Document(
                    id=seed.langchain_id,
                    page_content=document.page_content,
                    metadata=dict(document.metadata),
                )
            v2_documents.append(document)
            document_ids.append(seed.langchain_id)

        failed_record_ids = _dedupe(
            (
                *fetched.failed_record_ids,
                *build_failed_ids,
                *transform_failed_ids,
            )
        )
        return GithubRepositoryTransformResult(
            requested_count=fetched.requested_count,
            v2_documents=tuple(v2_documents),
            document_ids=tuple(document_ids),
            error_count=len(failed_record_ids),
            failed_record_ids=failed_record_ids,
            owner=execution.owner,
            repo=execution.repo,
            repo_full_name=execution.repo_full_name,
        )

    async def summarize(
        self,
        *,
        execution: GithubPrV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        transformed: GithubRepositoryTransformResult,
    ) -> GithubRepositorySummaryResult:
        _ = execution
        _ = sync_window
        return GithubRepositorySummaryResult(
            summary_applied=False,
            v2_documents=transformed.v2_documents,
            document_ids=transformed.document_ids,
        )

    async def persist(
        self,
        *,
        execution: GithubPrV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        transformed: GithubRepositoryTransformResult,
        summary: GithubRepositorySummaryResult,
    ) -> GithubRepositoryPersistResult:
        _ = sync_window
        seed_by_langchain_id = _seed_by_langchain_id(execution.seeds)
        document_ids = list(summary.document_ids)
        v2_documents = list(summary.v2_documents)
        upstream_error_count = len(set(transformed.failed_record_ids))

        if not document_ids:
            return GithubRepositoryPersistResult(error_count=upstream_error_count)

        if self.vector_store is None:
            return GithubRepositoryPersistResult(
                error_count=upstream_error_count + len(document_ids),
                v2_error_count=len(document_ids),
                v2_failed_ids=tuple(document_ids),
            )

        embeddings = [seed_by_langchain_id[doc_id].embedding for doc_id in document_ids]

        try:
            persisted_ids = await self.vector_store.upsert_documents(
                v2_documents,
                ids=document_ids,
                embeddings=embeddings,
            )
        except Exception:
            return GithubRepositoryPersistResult(
                error_count=upstream_error_count + len(document_ids),
                v2_error_count=len(document_ids),
                v2_failed_ids=tuple(document_ids),
            )

        persisted_id_set = {str(persisted_id) for persisted_id in persisted_ids or []}
        failed_ids = tuple(
            doc_id for doc_id in document_ids if doc_id not in persisted_id_set
        )
        return GithubRepositoryPersistResult(
            persisted_count=len(document_ids) - len(failed_ids),
            error_count=upstream_error_count + len(failed_ids),
            v2_error_count=len(failed_ids),
            v2_failed_ids=failed_ids,
        )

    def build_result(
        self,
        *,
        execution: GithubPrV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        fetched: GithubRepositoryFetchResult,
        transformed: GithubRepositoryTransformResult,
        summary: GithubRepositorySummaryResult,
        persisted: GithubRepositoryPersistResult,
    ) -> GithubRepositorySyncExecutionResult:
        _ = sync_window
        failed_ids = _dedupe(
            (
                *_langchain_ids_for_record_ids(
                    execution.seeds,
                    transformed.failed_record_ids,
                ),
                *persisted.v2_failed_ids,
            )
        )
        return GithubRepositorySyncExecutionResult(
            tenant_id=execution.tenant_id,
            target="repository_pr_v2_backfill",
            persisted_count=persisted.persisted_count,
            deleted_count=persisted.deleted_count,
            failed_count=len(failed_ids),
            v2_failed_count=persisted.v2_error_count,
            v2_failed_ids=persisted.v2_failed_ids,
            skipped=persisted.skipped,
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=persisted,
            record_type="pull_request",
            metadata={
                "record_type": "pull_request",
                "repo_full_name": execution.repo_full_name,
                "requested_count": len(execution.seeds),
                "failed_ids": list(failed_ids),
                "failed_record_ids": list(transformed.failed_record_ids),
                "v2_failed_ids": list(persisted.v2_failed_ids),
            },
        )


def _seed_by_record_id(
    seeds: tuple[GithubPrV2BackfillSeed, ...],
) -> dict[str, GithubPrV2BackfillSeed]:
    return {seed.record_id: seed for seed in seeds}


def _seed_by_langchain_id(
    seeds: tuple[GithubPrV2BackfillSeed, ...],
) -> dict[str, GithubPrV2BackfillSeed]:
    return {seed.langchain_id: seed for seed in seeds}


def _langchain_ids_for_record_ids(
    seeds: tuple[GithubPrV2BackfillSeed, ...],
    record_ids: tuple[str, ...],
) -> tuple[str, ...]:
    seeds_by_record_id = _seed_by_record_id(seeds)
    return tuple(
        seeds_by_record_id[record_id].langchain_id
        if record_id in seeds_by_record_id
        else record_id
        for record_id in record_ids
    )


def _dedupe(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
