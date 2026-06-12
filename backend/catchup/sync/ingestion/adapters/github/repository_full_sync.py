from __future__ import annotations

from fastapi.concurrency import run_in_threadpool

from catchup.sync.ingestion.adapters.github.repository_base import (
    GithubRepositoryAdapterBase,
)
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubRepositoryFetchResult,
)
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubRepositoryFullSyncExecutionRequest,
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


class GithubRepositoryFullSyncAdapter(GithubRepositoryAdapterBase):
    """
    Handler가 GitHub GraphQL cursor를 넘기며 이 adapter를 반복 호출
    """

    async def fetch(
        self,
        *,
        execution: GithubRepositoryFullSyncExecutionRequest,
        sync_window: SyncWindow,
    ) -> GithubRepositoryFetchResult:
        """
        현재 execution의 cursor가 가리키는 GraphQL page 1개를 처리함. (~50 records)
        """
        if execution.record_type == "issue":
            page = await self.client.fetch_issues_graphql_page(
                owner=execution.owner,
                repo=execution.repo,
                after_cursor=execution.after_cursor,
                since=sync_window.window_start,
            )
        else:
            page = await self.client.fetch_pull_requests_graphql_page(
                owner=execution.owner,
                repo=execution.repo,
                after_cursor=execution.after_cursor,
                since=sync_window.window_start,
            )
        return GithubRepositoryFetchResult(
            requested_count=1,
            records=page.nodes,
            record_type=execution.record_type,
            batch_index=execution.batch_index,
            is_last=page.is_last,
            checkpoint=execution.batch_index,
            next_cursor=page.next_cursor,
            stopped_by_since=page.stopped_by_since,
        )

    async def transform(
        self,
        *,
        execution: GithubRepositoryFullSyncExecutionRequest,
        sync_window: SyncWindow,
        fetched: GithubRepositoryFetchResult,
    ) -> GithubRepositoryTransformResult:
        _ = sync_window
        if execution.record_type == "issue":
            documents, document_ids, error_count = await run_in_threadpool(
                self._build_issue_batch_documents_sync,
                execution.owner,
                execution.repo,
                list(fetched.records),
            )
            v2_documents = []
        else:
            pr_bundles, document_ids, error_count = await run_in_threadpool(
                self._build_pull_request_batch_bundles_sync,
                execution.owner,
                execution.repo,
                list(fetched.records),
            )
            documents = [bundle.document for bundle in pr_bundles]
            if self.pr_v2_vector_store is not None:
                v2_documents = self._build_v2_documents_from_pr_bundles(
                    owner=execution.owner,
                    repo=execution.repo,
                    bundles=list(pr_bundles),
                )
            else:
                v2_documents = []
        return GithubRepositoryTransformResult(
            requested_count=fetched.requested_count,
            v1_documents=tuple(documents),
            v2_documents=tuple(v2_documents),
            document_ids=tuple(document_ids),
            error_count=error_count + len(fetched.failed_record_ids),
            failed_record_ids=fetched.failed_record_ids,
            owner=execution.owner,
            repo=execution.repo,
            repo_full_name=execution.repo_full_name,
        )

    async def summarize(
        self,
        *,
        execution: GithubRepositoryFullSyncExecutionRequest,
        sync_window: SyncWindow,
        transformed: GithubRepositoryTransformResult,
    ) -> GithubRepositorySummaryResult:
        _ = sync_window
        v1_documents = list(transformed.v1_documents)
        if self.summarizer and v1_documents:
            v1_documents = await self._summarize_documents(
                v1_documents,
                repo_full_name=execution.repo_full_name,
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
        execution: GithubRepositoryFullSyncExecutionRequest,
        sync_window: SyncWindow,
        transformed: GithubRepositoryTransformResult,
        summary: GithubRepositorySummaryResult,
    ) -> GithubRepositoryPersistResult:
        _ = sync_window
        error_count = transformed.error_count
        v1_documents = list(summary.v1_documents)
        v2_documents = list(summary.v2_documents)
        document_ids = list(summary.document_ids)
        if not v1_documents:
            return GithubRepositoryPersistResult(error_count=error_count)

        v2_failed_ids: tuple[str, ...] = ()
        context = (
            f"entity_type={execution.record_type},"
            f"repo={execution.repo_full_name},"
            f"batch={execution.batch_index},"
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
        execution: GithubRepositoryFullSyncExecutionRequest,
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
