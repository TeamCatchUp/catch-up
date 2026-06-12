from __future__ import annotations

from fastapi.concurrency import run_in_threadpool

from catchup.sync.ingestion.adapters.github.repository_base import (
    GithubRepositoryAdapterBase,
)
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubRepositoryFetchResult,
)
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubRepositoryIncrementalSyncExecutionRequest,
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


class GithubRepositoryIncrementalSyncAdapter(GithubRepositoryAdapterBase):
    """GitHub repository exact-record incremental sync adapter."""

    async def fetch(
        self,
        *,
        execution: GithubRepositoryIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
    ) -> GithubRepositoryFetchResult:
        _ = sync_window
        repo_ref = await self._get_repo_ref(execution.repo_id)
        if execution.is_delete_event:
            return GithubRepositoryFetchResult(
                requested_count=1,
                record_type=execution.record_type,
                owner=repo_ref.owner,
                repo=repo_ref.repo,
                repo_full_name=repo_ref.full_name,
            )

        if execution.record_type == "issue":
            items, failed_ids = await self._fetch_issue_nodes(
                owner=repo_ref.owner,
                repo=repo_ref.repo,
                issue_ids=[execution.record_id],
            )
        else:
            items, failed_ids = await self._fetch_pull_request_nodes(
                owner=repo_ref.owner,
                repo=repo_ref.repo,
                pull_request_ids=[execution.record_id],
            )
        return GithubRepositoryFetchResult(
            requested_count=1,
            exact_items=tuple(items),
            failed_record_ids=tuple(failed_ids),
            record_type=execution.record_type,
            owner=repo_ref.owner,
            repo=repo_ref.repo,
            repo_full_name=repo_ref.full_name,
        )

    async def transform(
        self,
        *,
        execution: GithubRepositoryIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        fetched: GithubRepositoryFetchResult,
    ) -> GithubRepositoryTransformResult:
        _ = sync_window
        if execution.is_delete_event:
            return GithubRepositoryTransformResult(
                requested_count=fetched.requested_count,
                owner=fetched.owner,
                repo=fetched.repo,
                repo_full_name=fetched.repo_full_name,
            )

        if execution.record_type == "issue":
            documents, failed_ids = await run_in_threadpool(
                self._build_issue_documents_sync,
                fetched.owner or "",
                fetched.repo or "",
                list(fetched.exact_items),
            )
            v2_documents = []
        else:
            pr_bundles, failed_ids = await run_in_threadpool(
                self._build_pull_request_document_bundles_sync,
                fetched.owner or "",
                fetched.repo or "",
                list(fetched.exact_items),
            )
            documents = [bundle.document for bundle in pr_bundles]
            if self.pr_v2_vector_store is not None:
                v2_documents = self._build_v2_documents_from_pr_bundles(
                    owner=fetched.owner or "",
                    repo=fetched.repo or "",
                    bundles=list(pr_bundles),
                )
            else:
                v2_documents = []
        document_ids = tuple(doc.id for doc in documents)
        failed_record_ids = tuple((*fetched.failed_record_ids, *failed_ids))
        return GithubRepositoryTransformResult(
            requested_count=fetched.requested_count,
            v1_documents=tuple(documents),
            v2_documents=tuple(v2_documents),
            document_ids=document_ids,
            error_count=len(set(failed_record_ids)),
            failed_record_ids=failed_record_ids,
            owner=fetched.owner,
            repo=fetched.repo,
            repo_full_name=fetched.repo_full_name,
        )

    async def summarize(
        self,
        *,
        execution: GithubRepositoryIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        transformed: GithubRepositoryTransformResult,
    ) -> GithubRepositorySummaryResult:
        _ = sync_window
        v1_documents = list(transformed.v1_documents)
        if self.summarizer and v1_documents:
            v1_documents = await self._summarize_documents(
                v1_documents,
                repo_full_name=transformed.repo_full_name or str(execution.repo_id),
                entity_type=execution.record_type,
                audit_context=execution.audit_context,
            )
        v2_documents = self._apply_v1_page_content_to_v2_content(
            v1_documents=v1_documents,
            v2_documents=list(transformed.v2_documents),
        )
        return GithubRepositorySummaryResult(
            summary_applied=bool(self.summarizer and v1_documents),
            v1_documents=tuple(v1_documents),
            v2_documents=tuple(v2_documents),
            document_ids=tuple(doc.id for doc in v1_documents),
        )

    async def persist(
        self,
        *,
        execution: GithubRepositoryIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        transformed: GithubRepositoryTransformResult,
        summary: GithubRepositorySummaryResult,
    ) -> GithubRepositoryPersistResult:
        _ = sync_window
        if execution.is_delete_event:
            doc_id = self._document_id_for_incremental_delete(
                execution=execution,
                owner=transformed.owner or "",
                repo=transformed.repo or "",
            )
            await self.repository.delete_documents([doc_id])
            v2_failed_ids: tuple[str, ...] = ()
            if (
                execution.record_type == "pull_request"
                and self.pr_v2_vector_store is not None
            ):
                try:
                    await self.pr_v2_vector_store.delete([doc_id])
                except Exception:
                    v2_failed_ids = (doc_id,)
            return GithubRepositoryPersistResult(
                deleted_count=1,
                v2_error_count=len(v2_failed_ids),
                v2_failed_ids=v2_failed_ids,
            )

        error_count = transformed.error_count
        v1_documents = list(summary.v1_documents)
        v2_documents = list(summary.v2_documents)
        document_ids = list(summary.document_ids)
        if not v1_documents:
            return GithubRepositoryPersistResult(error_count=max(1, error_count))

        v2_failed_ids: tuple[str, ...] = ()
        context = (
            f"entity_type={execution.record_type},"
            f"repo={transformed.repo_full_name or execution.repo_id},"
            "mode=incremental_exact,"
            f"doc_count={len(v1_documents)}"
        )
        if v2_documents:
            dual_write_result = await self._upsert_v1_v2_documents_dual_write(
                v1_documents=v1_documents,
                v2_documents=v2_documents,
                ids=document_ids,
                audit_context=execution.audit_context,
                context=context,
            )
            v2_failed_ids = dual_write_result.v2_failed_ids
        else:
            await self.repository.upsert_documents(
                v1_documents,
                document_ids,
                audit_context=execution.audit_context,
                context=context,
            )
        return GithubRepositoryPersistResult(
            persisted_count=len(v1_documents),
            error_count=error_count,
            v2_error_count=len(v2_failed_ids),
            v2_failed_ids=v2_failed_ids,
        )

    def build_result(
        self,
        *,
        execution: GithubRepositoryIncrementalSyncExecutionRequest,
        sync_window: SyncWindow,
        fetched: GithubRepositoryFetchResult,
        transformed: GithubRepositoryTransformResult,
        summary: GithubRepositorySummaryResult,
        persisted: GithubRepositoryPersistResult,
    ) -> GithubRepositorySyncExecutionResult:
        _ = sync_window
        return GithubRepositorySyncExecutionResult(
            tenant_id=execution.tenant_id,
            persisted_count=persisted.persisted_count,
            deleted_count=persisted.deleted_count,
            failed_count=persisted.error_count + persisted.v2_error_count,
            v2_failed_count=persisted.v2_error_count,
            v2_failed_ids=persisted.v2_failed_ids,
            skipped=persisted.skipped,
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=persisted,
            record_type=fetched.record_type,
            batch_index=fetched.batch_index,
            is_last=fetched.is_last,
            checkpoint=fetched.checkpoint,
            next_cursor=fetched.next_cursor,
            stopped_by_since=fetched.stopped_by_since,
            metadata={
                "record_type": fetched.record_type,
                "batch_index": fetched.batch_index,
                "is_last": fetched.is_last,
                "checkpoint": fetched.checkpoint,
                "next_cursor": fetched.next_cursor,
                "stopped_by_since": fetched.stopped_by_since,
                "v2_failed_count": persisted.v2_error_count,
                "v2_failed_ids": list(persisted.v2_failed_ids),
            },
        )

    @staticmethod
    def _document_id_for_incremental_delete(
        *,
        execution: GithubRepositoryIncrementalSyncExecutionRequest,
        owner: str,
        repo: str,
    ) -> str:
        if execution.record_type == "issue":
            return f"github:issue:{owner}/{repo}:{execution.record_id}"
        return f"github:pr:{owner}/{repo}:{execution.record_id}"
