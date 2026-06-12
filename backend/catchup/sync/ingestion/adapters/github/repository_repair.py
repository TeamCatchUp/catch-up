from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from catchup.configs.config import settings
from catchup.sync.ingestion.adapters.github.repository_base import (
    GithubRepositoryAdapterBase,
)
from catchup.sync.ingestion.adapters.github.repository_models import GithubRecordGapItem
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubRecordGapReport,
)
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubRecordRetryItem,
)
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubRecordRetryResult,
)
from catchup.sync.ingestion.adapters.github.repository_models import GithubRecordType
from catchup.sync.ingestion.adapters.github.repository_models import GithubRepoRef

logger = logging.getLogger(__name__)


class GithubRepositoryRepairAdapter(GithubRepositoryAdapterBase):
    """GitHub repository record gap and retry adapter."""

    async def build_record_gap_report(
        self,
        *,
        repo_id: int,
        sync_days: int | None = None,
        sync_from_dt: datetime | None = None,
    ) -> GithubRecordGapReport:
        repo_ref = await self._get_repo_ref(repo_id)
        sync_from_dt = sync_from_dt or self._resolve_sync_from_dt(sync_days)

        (
            expected_issue_ids,
            expected_pull_request_ids,
            stored_issue_doc_ids,
            stored_pull_request_doc_ids,
        ) = await asyncio.gather(
            self.client.list_issue_numbers_graphql(
                repo_ref.owner,
                repo_ref.repo,
                since=sync_from_dt,
            ),
            self.client.list_pull_request_numbers_graphql(
                repo_ref.owner,
                repo_ref.repo,
                since=sync_from_dt,
            ),
            self.repository.list_github_record_ids(
                owner=repo_ref.owner,
                repo=repo_ref.repo,
                entity_type="issue",
                since=sync_from_dt,
            ),
            self.repository.list_github_record_ids(
                owner=repo_ref.owner,
                repo=repo_ref.repo,
                entity_type="pr",
                since=sync_from_dt,
            ),
        )

        return GithubRecordGapReport(
            records=[
                self._build_gap_item(
                    record_type="issue",
                    expected_ids=expected_issue_ids,
                    stored_ids=self._extract_record_ids_from_doc_ids(stored_issue_doc_ids),
                    stored_count=len(stored_issue_doc_ids),
                ),
                self._build_gap_item(
                    record_type="pull_request",
                    expected_ids=expected_pull_request_ids,
                    stored_ids=self._extract_record_ids_from_doc_ids(
                        stored_pull_request_doc_ids
                    ),
                    stored_count=len(stored_pull_request_doc_ids),
                ),
            ]
        )

    async def retry_missing_records(
        self,
        *,
        repo_id: int,
        issue_ids: list[str] | None = None,
        pull_request_ids: list[str] | None = None,
    ) -> GithubRecordRetryResult:
        repo_ref = await self._get_repo_ref(repo_id)
        retry_tasks = []
        if issue_ids:
            retry_tasks.append(
                self._retry_record_batch(
                    repo_ref=repo_ref,
                    record_type="issue",
                    requested_ids=list(issue_ids),
                )
            )
        if pull_request_ids:
            retry_tasks.append(
                self._retry_record_batch(
                    repo_ref=repo_ref,
                    record_type="pull_request",
                    requested_ids=list(pull_request_ids),
                )
            )

        result_items = await asyncio.gather(*retry_tasks) if retry_tasks else []
        return GithubRecordRetryResult(records=list(result_items))

    async def _retry_record_batch(
        self,
        *,
        repo_ref: GithubRepoRef,
        record_type: GithubRecordType,
        requested_ids: list[str],
    ) -> GithubRecordRetryItem:
        if record_type == "issue":
            nodes, failed_ids = await self._fetch_issue_nodes(
                owner=repo_ref.owner,
                repo=repo_ref.repo,
                issue_ids=requested_ids,
            )
            documents, build_failed_ids = await asyncio.to_thread(
                self._build_issue_documents_sync,
                repo_ref.owner,
                repo_ref.repo,
                nodes,
            )
            v2_documents = []
        else:
            nodes, failed_ids = await self._fetch_pull_request_nodes(
                owner=repo_ref.owner,
                repo=repo_ref.repo,
                pull_request_ids=requested_ids,
            )
            pr_bundles, build_failed_ids = await asyncio.to_thread(
                self._build_pull_request_document_bundles_sync,
                repo_ref.owner,
                repo_ref.repo,
                nodes,
            )
            documents = [bundle.document for bundle in pr_bundles]
            if self.pr_v2_vector_store is not None:
                v2_documents = self._build_v2_documents_from_pr_bundles(
                    owner=repo_ref.owner,
                    repo=repo_ref.repo,
                    bundles=list(pr_bundles),
                )
            else:
                v2_documents = []

        failed_ids.extend(build_failed_ids)
        succeeded_count = 0

        if documents:
            try:
                upsert_documents = documents
                if self.summarizer:
                    upsert_documents = await self._summarize_documents(
                        documents,
                        repo_full_name=repo_ref.full_name,
                        entity_type=record_type,
                        audit_context=None,
                    )
                v2_upsert_documents = self._apply_v1_page_content_to_v2_content(
                    v1_documents=upsert_documents,
                    v2_documents=v2_documents,
                )

                context = (
                    f"entity_type={record_type},"
                    f"repo={repo_ref.full_name},"
                    "mode=partial_retry,"
                    f"doc_count={len(upsert_documents)}"
                )
                if v2_upsert_documents:
                    dual_write_result = await self._upsert_v1_v2_documents_dual_write(
                        v1_documents=upsert_documents,
                        v2_documents=v2_upsert_documents,
                        ids=[doc.id for doc in upsert_documents],
                        audit_context=None,
                        context=context,
                    )
                    failed_ids.extend(dual_write_result.v2_failed_ids)
                else:
                    await self.repository.upsert_documents(
                        upsert_documents,
                        [doc.id for doc in upsert_documents],
                        audit_context=None,
                        context=context,
                    )
                succeeded_count = len(upsert_documents)
            except Exception as exc:
                logger.error(
                    "[GITHUB][REPAIR] Failed to upsert %s docs: installation_id=%s, repo=%s, error=%s",
                    record_type,
                    self.installation_id,
                    repo_ref.full_name,
                    exc,
                    exc_info=True,
                )
                failed_ids.extend(
                    self._extract_record_ids_from_doc_ids([doc.id for doc in documents])
                )

        return GithubRecordRetryItem(
            record_type=record_type,
            requested_ids=requested_ids,
            retried_count=len(requested_ids),
            succeeded_count=succeeded_count,
            failed_ids=self._sort_record_ids(set(failed_ids)),
        )

    def _resolve_sync_from_dt(self, sync_days: int | None) -> datetime:
        days = sync_days if sync_days is not None else settings.DEFAULT_SYNC_DAYS
        return datetime.now(timezone.utc) - timedelta(days=days)

    @staticmethod
    def _extract_record_ids_from_doc_ids(doc_ids: list[str]) -> list[str]:
        record_ids: list[str] = []
        for doc_id in doc_ids:
            if not doc_id or ":" not in doc_id:
                continue
            record_ids.append(doc_id.rsplit(":", 1)[-1])
        return record_ids

    @staticmethod
    def _sort_record_ids(record_ids: set[str]) -> list[str]:
        def _key(value: str) -> tuple[int, int | str]:
            try:
                return (0, int(value))
            except ValueError:
                return (1, value)

        return sorted(record_ids, key=_key)

    def _build_gap_item(
        self,
        *,
        record_type: str,
        expected_ids: list[str],
        stored_ids: list[str],
        stored_count: int,
    ) -> GithubRecordGapItem:
        missing_ids = self._sort_record_ids(set(expected_ids) - set(stored_ids))
        return GithubRecordGapItem(
            record_type=record_type,
            expected_count=len(expected_ids),
            stored_count=stored_count,
            missing_count=len(missing_ids),
            missing_ids=missing_ids,
        )
