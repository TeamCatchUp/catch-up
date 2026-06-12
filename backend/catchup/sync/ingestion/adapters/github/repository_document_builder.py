from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from langchain_core.documents import Document

from catchup.db.engine import SessionLocal
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubIssueDocumentBundle,
)
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubPrDocumentBundle,
)
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubRepositoryV2DocumentBuildResult,
)
from catchup.sync.ingestion.adapters.github.repository_models import SyncOperation
from catchup.sync.ingestion.adapters.github.repository_user_mapping import (
    GithubRepositoryUserMapper,
)
from catchup.sync.ingestion.document_builders.github import GithubTransformer
from catchup.sync.ingestion.vector_records import GithubIssueV2RecordMapper
from catchup.sync.ingestion.vector_records import GithubPrV2RecordMapper

logger = structlog.get_logger(__name__)


class GithubRepositoryDocumentBuilder:
    """Build v1/v2 documents from GitHub repository GraphQL payloads."""

    def __init__(
        self,
        *,
        installation_id: int,
        transformer: GithubTransformer,
        user_mapper: GithubRepositoryUserMapper,
        issue_v2_mapper: GithubIssueV2RecordMapper,
        pr_v2_mapper: GithubPrV2RecordMapper,
    ) -> None:
        self._installation_id = installation_id
        self._transformer = transformer
        self._user_mapper = user_mapper
        self._issue_v2_mapper = issue_v2_mapper
        self._pr_v2_mapper = pr_v2_mapper

    def build_issue_batch_documents_sync(
        self,
        owner: str,
        repo: str,
        issue_batch: list[dict[str, Any]],
    ) -> tuple[list[Document], list[str], int]:
        bundles, doc_ids, errors = self.build_issue_batch_bundles_sync(
            owner,
            repo,
            issue_batch,
        )
        return [bundle.document for bundle in bundles], doc_ids, errors

    def build_issue_batch_bundles_sync(
        self,
        owner: str,
        repo: str,
        issue_batch: list[dict[str, Any]],
    ) -> tuple[list[GithubIssueDocumentBundle], list[str], int]:
        batch_bundles: list[GithubIssueDocumentBundle] = []
        batch_doc_ids: list[str] = []
        errors = 0

        with SessionLocal() as db:
            for issue_data in issue_batch:
                try:
                    issue = self._transformer.parse_issue(issue_data)
                    issue = self._user_mapper.apply_issue(db, issue)
                    doc = self._transformer.transform_issue(
                        issue,
                        owner,
                        repo,
                        self._installation_id,
                    )
                    batch_bundles.append(
                        GithubIssueDocumentBundle(
                            issue=issue,
                            document=doc,
                        )
                    )
                    batch_doc_ids.append(doc.id)
                except Exception as exc:
                    logger.warning(
                        "github_issue_batch_document_build_failed",
                        connector="github",
                        operation=SyncOperation.ISSUE_SYNC,
                        installation_id=self._installation_id,
                        owner=owner,
                        repo=repo,
                        issue_number=issue_data.get("number"),
                        error=str(exc),
                        exc_info=True,
                    )
                    errors += 1
        return batch_bundles, batch_doc_ids, errors

    def build_pull_request_batch_bundles_sync(
        self,
        owner: str,
        repo: str,
        pr_batch: list[dict[str, Any]],
    ) -> tuple[list[GithubPrDocumentBundle], list[str], int]:
        batch_bundles: list[GithubPrDocumentBundle] = []
        batch_doc_ids: list[str] = []
        errors = 0

        with SessionLocal() as db:
            for pr_data in pr_batch:
                try:
                    pr = self._transformer.parse_pull_request(pr_data)
                    pr = self._user_mapper.apply_pull_request(db, pr)
                    doc = self._transformer.transform_pull_request(
                        pr,
                        owner,
                        repo,
                        self._installation_id,
                    )
                    batch_bundles.append(
                        GithubPrDocumentBundle(
                            pull_request=pr,
                            document=doc,
                        )
                    )
                    batch_doc_ids.append(doc.id)
                except Exception as exc:
                    logger.warning(
                        "github_pr_batch_document_build_failed",
                        connector="github",
                        operation=SyncOperation.PR_SYNC,
                        installation_id=self._installation_id,
                        owner=owner,
                        repo=repo,
                        pull_request_number=pr_data.get("number"),
                        error=str(exc),
                        exc_info=True,
                    )
                    errors += 1

        return batch_bundles, batch_doc_ids, errors

    def build_issue_documents_sync(
        self,
        owner: str,
        repo: str,
        issue_items: list[tuple[str, dict[str, Any]]],
    ) -> tuple[list[Document], list[str]]:
        bundles, failed_ids = self.build_issue_document_bundles_sync(
            owner,
            repo,
            issue_items,
        )
        return [bundle.document for bundle in bundles], failed_ids

    def build_issue_document_bundles_sync(
        self,
        owner: str,
        repo: str,
        issue_items: list[tuple[str, dict[str, Any]]],
    ) -> tuple[list[GithubIssueDocumentBundle], list[str]]:
        bundles: list[GithubIssueDocumentBundle] = []
        failed_ids: list[str] = []

        with SessionLocal() as db:
            self._user_mapper.preload_premapped_names(db)
            for record_id, issue_data in issue_items:
                try:
                    issue = self._transformer.parse_issue(issue_data)
                    issue = self._user_mapper.apply_issue(db, issue)
                    doc = self._transformer.transform_issue(
                        issue,
                        owner,
                        repo,
                        self._installation_id,
                    )
                    bundles.append(GithubIssueDocumentBundle(issue=issue, document=doc))
                except Exception as exc:
                    logger.warning(
                        "github_issue_document_build_failed",
                        connector="github",
                        operation="repair",
                        installation_id=self._installation_id,
                        owner=owner,
                        repo=repo,
                        issue_id=record_id,
                        error=str(exc),
                        exc_info=True,
                    )
                    failed_ids.append(record_id)

        return bundles, failed_ids

    def build_pull_request_document_bundles_sync(
        self,
        owner: str,
        repo: str,
        pr_items: list[tuple[str, dict[str, Any]]],
    ) -> tuple[list[GithubPrDocumentBundle], list[str]]:
        bundles: list[GithubPrDocumentBundle] = []
        failed_ids: list[str] = []

        with SessionLocal() as db:
            self._user_mapper.preload_premapped_names(db)
            for record_id, pr_data in pr_items:
                try:
                    pr = self._transformer.parse_pull_request(pr_data)
                    pr = self._user_mapper.apply_pull_request(db, pr)
                    doc = self._transformer.transform_pull_request(
                        pr,
                        owner,
                        repo,
                        self._installation_id,
                    )
                    bundles.append(
                        GithubPrDocumentBundle(
                            pull_request=pr,
                            document=doc,
                        )
                    )
                except Exception as exc:
                    logger.warning(
                        "github_pr_document_build_failed",
                        connector="github",
                        operation="repair",
                        installation_id=self._installation_id,
                        owner=owner,
                        repo=repo,
                        pull_request_id=record_id,
                        error=str(exc),
                        exc_info=True,
                    )
                    failed_ids.append(record_id)

        return bundles, failed_ids

    def build_v2_documents_from_pr_bundles(
        self,
        *,
        owner: str,
        repo: str,
        bundles: list[GithubPrDocumentBundle],
    ) -> GithubRepositoryV2DocumentBuildResult:
        if not bundles:
            return GithubRepositoryV2DocumentBuildResult()

        documents: list[Document] = []
        failed_ids: list[str] = []
        for bundle in bundles:
            try:
                documents.append(
                    self._pr_v2_mapper.to_document(
                        bundle.pull_request,
                        owner=owner,
                        repo=repo,
                        installation_id=self._installation_id,
                        content=bundle.document.page_content,
                        synced_at=document_synced_at(bundle.document),
                    )
                )
            except Exception as exc:
                failed_ids.append(bundle.document.id)
                logger.error(
                    "github_pr_v2_document_build_failed",
                    connector="github",
                    operation="pr_v2_dual_write",
                    installation_id=self._installation_id,
                    owner=owner,
                    repo=repo,
                    document_id=bundle.document.id,
                    pull_request_number=bundle.pull_request.number,
                    error=str(exc),
                    exc_info=True,
                )
        return GithubRepositoryV2DocumentBuildResult(
            documents=documents,
            failed_ids=tuple(failed_ids),
        )

    def build_v2_documents_from_issue_bundles(
        self,
        *,
        owner: str,
        repo: str,
        bundles: list[GithubIssueDocumentBundle],
    ) -> GithubRepositoryV2DocumentBuildResult:
        if not bundles:
            return GithubRepositoryV2DocumentBuildResult()

        documents: list[Document] = []
        failed_ids: list[str] = []
        for bundle in bundles:
            try:
                documents.append(
                    self._issue_v2_mapper.to_document(
                        bundle.issue,
                        owner=owner,
                        repo=repo,
                        installation_id=self._installation_id,
                        content=bundle.document.page_content,
                        synced_at=document_synced_at(bundle.document),
                    )
                )
            except Exception as exc:
                failed_ids.append(bundle.document.id)
                logger.error(
                    "github_issue_v2_document_build_failed",
                    connector="github",
                    operation="issue_v2_dual_write",
                    installation_id=self._installation_id,
                    owner=owner,
                    repo=repo,
                    document_id=bundle.document.id,
                    issue_number=bundle.issue.number,
                    error=str(exc),
                    exc_info=True,
                )
        return GithubRepositoryV2DocumentBuildResult(
            documents=documents,
            failed_ids=tuple(failed_ids),
        )


def document_synced_at(document: Document) -> datetime:
    synced_at = document.metadata.get("synced_at")
    if isinstance(synced_at, datetime):
        return synced_at
    if isinstance(synced_at, str):
        return datetime.fromisoformat(synced_at.replace("Z", "+00:00"))
    raise ValueError("document metadata synced_at must be an ISO datetime string")
