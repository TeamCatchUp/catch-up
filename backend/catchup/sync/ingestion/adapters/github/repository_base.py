from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import structlog
from langchain_core.documents import Document
from sqlalchemy.orm import Session

from catchup.components.summarizer import SummarizeRequest
from catchup.components.summarizer import SummarizerService
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.components.vector_db.v2 import VectorStore
from catchup.connectors.github.client import GitHubApiClient
from catchup.connectors.github.client import GitHubRateLimitError
from catchup.connectors.github.schemas import GithubIssue
from catchup.connectors.github.schemas import GithubPullRequest
from catchup.connectors.github.schemas import GithubUser
from catchup.db.engine import SessionLocal
from catchup.db.github import domain_repository as github_entities
from catchup.db.models import SourceType
from catchup.db.user_source_mapping import (
    find_premapped_name_by_external_user_identifier,
)
from catchup.db.user_source_mapping import find_premapped_names_by_source_type
from catchup.db.user_source_mapping import find_user_id_by_source_mapping
from catchup.sync.audit import SyncAuditContext
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubPrDocumentBundle,
)
from catchup.sync.ingestion.adapters.github.repository_models import GithubRecordType
from catchup.sync.ingestion.adapters.github.repository_models import GithubRepoRef
from catchup.sync.ingestion.adapters.github.repository_models import (
    GithubRepositoryDualWriteResult,
)
from catchup.sync.ingestion.adapters.github.repository_models import SyncOperation
from catchup.sync.ingestion.document_builders.github import GithubTransformer
from catchup.sync.ingestion.vector_records import GithubPrV2RecordMapper

logger = structlog.get_logger(__name__)


class GithubRepositoryAdapterBase:
    """Shared GitHub repository adapter utilities."""

    def __init__(
        self,
        *,
        installation_id: int,
        client: GitHubApiClient,
        repository: PGVectorRepository,
        summarizer: SummarizerService | None = None,
        pr_v2_vector_store: VectorStore | None = None,
        transformer: GithubTransformer | None = None,
    ) -> None:
        self.installation_id = installation_id
        self.client = client
        self.repository = repository
        self.summarizer = summarizer
        self.pr_v2_vector_store = pr_v2_vector_store
        self.transformer = transformer or GithubTransformer()
        self.pr_v2_mapper = GithubPrV2RecordMapper()
        self._github_name_cache: dict[str, str | None] = {}
        self._github_user_id_cache: dict[str, str | None] = {}

    async def _get_repo_ref(self, repo_id: int) -> GithubRepoRef:
        return await asyncio.to_thread(self._load_repo_ref_sync, repo_id)

    def _load_repo_ref_sync(self, repo_id: int) -> GithubRepoRef:
        with SessionLocal() as db:
            repo_names = self._get_repo_names_by_ids(db, [repo_id])

        if not repo_names:
            raise ValueError(f"github repository not found: repo_id={repo_id}")

        full_name = repo_names[0]
        owner, repo = full_name.split("/", 1)
        return GithubRepoRef(
            repo_id=repo_id,
            full_name=full_name,
            owner=owner,
            repo=repo,
        )

    async def _fetch_issue_nodes(
        self,
        *,
        owner: str,
        repo: str,
        issue_ids: list[str],
    ) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
        return await self._fetch_retry_nodes(
            owner=owner,
            repo=repo,
            record_ids=issue_ids,
            record_type="issue",
        )

    async def _fetch_pull_request_nodes(
        self,
        *,
        owner: str,
        repo: str,
        pull_request_ids: list[str],
    ) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
        return await self._fetch_retry_nodes(
            owner=owner,
            repo=repo,
            record_ids=pull_request_ids,
            record_type="pull_request",
        )

    async def _fetch_retry_nodes(
        self,
        *,
        owner: str,
        repo: str,
        record_ids: list[str],
        record_type: GithubRecordType,
        concurrency: int = 8,
    ) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
        if not record_ids:
            return [], []

        if record_type == "issue":
            entity_label = "issue"
            id_label = "issue_id"
        else:
            entity_label = "pull request"
            id_label = "pr_id"

        semaphore = asyncio.Semaphore(max(1, min(concurrency, len(record_ids))))

        async def _fetch_one(
            record_id: str,
        ) -> tuple[str, dict[str, Any] | None, bool]:
            try:
                number = int(record_id)
            except ValueError:
                logger.warning(
                    "github_retry_invalid_record_id",
                    connector="github",
                    operation="repair",
                    installation_id=self.installation_id,
                    owner=owner,
                    repo=repo,
                    record_type=record_type,
                    entity_label=entity_label,
                    id_label=id_label,
                    record_id=record_id,
                )
                return record_id, None, True

            try:
                async with semaphore:
                    if record_type == "issue":
                        data = await self.client.get_issue_graphql(owner, repo, number)
                    else:
                        data = await self.client.get_pull_request_graphql(
                            owner,
                            repo,
                            number,
                        )

                if not data:
                    return record_id, None, True

                return record_id, data, False
            except GitHubRateLimitError:
                raise
            except Exception as exc:
                logger.warning(
                    "github_retry_record_fetch_failed",
                    connector="github",
                    operation="repair",
                    installation_id=self.installation_id,
                    owner=owner,
                    repo=repo,
                    record_type=record_type,
                    entity_label=entity_label,
                    id_label=id_label,
                    record_id=record_id,
                    error=str(exc),
                )
                return record_id, None, True

        results = await asyncio.gather(*[_fetch_one(record_id) for record_id in record_ids])

        items: list[tuple[str, dict[str, Any]]] = []
        failed_ids: list[str] = []
        for record_id, data, failed in results:
            if failed or data is None:
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
        batch_documents: list[Document] = []
        batch_doc_ids: list[str] = []
        errors = 0

        with SessionLocal() as db:
            for issue_data in issue_batch:
                try:
                    issue = self.transformer.parse_issue(issue_data)
                    issue = self._apply_issue_user_mapping(db, issue)
                    doc = self.transformer.transform_issue(
                        issue,
                        owner,
                        repo,
                        self.installation_id,
                    )
                    batch_documents.append(doc)
                    batch_doc_ids.append(doc.id)
                except Exception as exc:
                    logger.warning(
                        "github_issue_batch_document_build_failed",
                        connector="github",
                        operation=SyncOperation.ISSUE_SYNC,
                        installation_id=self.installation_id,
                        owner=owner,
                        repo=repo,
                        issue_number=issue_data.get("number"),
                        error=str(exc),
                        exc_info=True,
                    )
                    errors += 1
        return batch_documents, batch_doc_ids, errors

    def _build_pull_request_batch_bundles_sync(
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
                    pr = self.transformer.parse_pull_request(pr_data)
                    pr = self._apply_pr_user_mapping(db, pr)
                    doc = self.transformer.transform_pull_request(
                        pr,
                        owner,
                        repo,
                        self.installation_id,
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
                        installation_id=self.installation_id,
                        owner=owner,
                        repo=repo,
                        pull_request_number=pr_data.get("number"),
                        error=str(exc),
                        exc_info=True,
                    )
                    errors += 1

        return batch_bundles, batch_doc_ids, errors

    def _build_issue_documents_sync(
        self,
        owner: str,
        repo: str,
        issue_items: list[tuple[str, dict[str, Any]]],
    ) -> tuple[list[Document], list[str]]:
        documents: list[Document] = []
        failed_ids: list[str] = []

        with SessionLocal() as db:
            self._preload_premapped_github_names(db)
            for record_id, issue_data in issue_items:
                try:
                    issue = self.transformer.parse_issue(issue_data)
                    issue = self._apply_issue_user_mapping(db, issue)
                    documents.append(
                        self.transformer.transform_issue(
                            issue,
                            owner,
                            repo,
                            self.installation_id,
                        )
                    )
                except Exception as exc:
                    logger.warning(
                        "github_issue_document_build_failed",
                        connector="github",
                        operation="repair",
                        installation_id=self.installation_id,
                        owner=owner,
                        repo=repo,
                        issue_id=record_id,
                        error=str(exc),
                        exc_info=True,
                    )
                    failed_ids.append(record_id)

        return documents, failed_ids

    def _build_pull_request_document_bundles_sync(
        self,
        owner: str,
        repo: str,
        pr_items: list[tuple[str, dict[str, Any]]],
    ) -> tuple[list[GithubPrDocumentBundle], list[str]]:
        bundles: list[GithubPrDocumentBundle] = []
        failed_ids: list[str] = []

        with SessionLocal() as db:
            self._preload_premapped_github_names(db)
            for record_id, pr_data in pr_items:
                try:
                    pr = self.transformer.parse_pull_request(pr_data)
                    pr = self._apply_pr_user_mapping(db, pr)
                    doc = self.transformer.transform_pull_request(
                        pr,
                        owner,
                        repo,
                        self.installation_id,
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
                        installation_id=self.installation_id,
                        owner=owner,
                        repo=repo,
                        pull_request_id=record_id,
                        error=str(exc),
                        exc_info=True,
                    )
                    failed_ids.append(record_id)

        return bundles, failed_ids

    def _build_v2_documents_from_pr_bundles(
        self,
        *,
        owner: str,
        repo: str,
        bundles: list[GithubPrDocumentBundle],
    ) -> list[Document]:
        if not bundles:
            return []

        try:
            return [
                self.pr_v2_mapper.to_document(
                    bundle.pull_request,
                    owner=owner,
                    repo=repo,
                    installation_id=self.installation_id,
                    content=bundle.document.page_content,
                    synced_at=self._document_synced_at(bundle.document),
                )
                for bundle in bundles
            ]
        except Exception as exc:
            logger.error(
                "github_pr_v2_documents_build_failed",
                connector="github",
                operation="pr_v2_dual_write",
                installation_id=self.installation_id,
                owner=owner,
                repo=repo,
                doc_count=len(bundles),
                error=str(exc),
                exc_info=True,
            )
            return []

    @staticmethod
    def _apply_v1_page_content_to_v2_content(
        *,
        v1_documents: list[Document],
        v2_documents: list[Document],
    ) -> list[Document]:
        if not v2_documents:
            return []
        if len(v1_documents) != len(v2_documents):
            logger.error(
                "github_pr_v2_document_count_mismatch",
                connector="github",
                operation="pr_v2_dual_write",
                v1_count=len(v1_documents),
                v2_count=len(v2_documents),
            )
            return []
        return [
            Document(
                id=v2_document.id,
                page_content=v1_document.page_content,
                metadata=dict(v2_document.metadata),
            )
            for v1_document, v2_document in zip(
                v1_documents,
                v2_documents,
                strict=True,
            )
        ]

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
    ) -> GithubRepositoryDualWriteResult:
        if self.pr_v2_vector_store is None or not v2_documents:
            persisted_ids = await self.repository.upsert_documents(
                v1_documents,
                ids,
                audit_context=audit_context,
                context=context,
            )
            return GithubRepositoryDualWriteResult(persisted_ids=persisted_ids)

        embeddings = await self.repository.generate_embeddings(
            v1_documents,
            audit_context=audit_context,
            context=context,
        )
        await self.repository.delete_documents(ids)
        result_ids = await self.repository.store_with_embeddings(
            v1_documents,
            embeddings,
            ids,
            audit_context=audit_context,
            context=context,
        )

        v2_failed_ids: tuple[str, ...] = ()
        try:
            if len(v1_documents) != len(v2_documents) or len(v1_documents) != len(ids):
                raise ValueError("v1 document, v2 document, and id counts must match")
            await self.pr_v2_vector_store.upsert_documents(
                v2_documents,
                ids=ids,
                embeddings=embeddings,
            )
        except Exception:
            v2_failed_ids = tuple(ids)
        return GithubRepositoryDualWriteResult(
            persisted_ids=result_ids,
            v2_failed_ids=v2_failed_ids,
        )

    @staticmethod
    def _document_synced_at(document: Document) -> datetime:
        synced_at = document.metadata.get("synced_at")
        if isinstance(synced_at, datetime):
            return synced_at
        if isinstance(synced_at, str):
            return datetime.fromisoformat(synced_at.replace("Z", "+00:00"))
        raise ValueError("document metadata synced_at must be an ISO datetime string")

    def _get_repo_names_by_ids(self, db: Session, repo_ids: list[int]) -> list[str]:
        repos = github_entities.get_repositories_by_installation(db, self.installation_id)
        repo_id_set = set(repo_ids)
        return [repo.full_name for repo in repos if repo.repo_id in repo_id_set]

    def _resolve_github_real_name(self, db: Session, login: str | None) -> str | None:
        if not login:
            return None

        if login in self._github_name_cache:
            return self._github_name_cache[login]

        resolved_name = find_premapped_name_by_external_user_identifier(
            db=db,
            source_type=SourceType.GITHUB,
            external_user_identifier=login,
        )
        self._github_name_cache[login] = resolved_name
        return resolved_name

    def _resolve_github_catchup_user_id(
        self,
        db: Session,
        login: str | None,
    ) -> str | None:
        if not login:
            return None

        if login in self._github_user_id_cache:
            return self._github_user_id_cache[login]

        user_id = find_user_id_by_source_mapping(
            db=db,
            source_type=SourceType.GITHUB,
            external_user_identifier=login,
        )
        resolved_id = str(user_id) if user_id is not None else None
        self._github_user_id_cache[login] = resolved_id
        return resolved_id

    def _preload_premapped_github_names(self, db: Session) -> int:
        premapped = find_premapped_names_by_source_type(db, SourceType.GITHUB)
        self._github_name_cache = {
            login: name
            for login, name in premapped.items()
            if login
        }
        return len(self._github_name_cache)

    def _apply_user_mapping(self, db: Session, user: GithubUser | None) -> GithubUser | None:
        if user is None:
            return None

        mapped_name = self._resolve_github_real_name(db, user.login)
        catchup_user_id = self._resolve_github_catchup_user_id(db, user.login)
        updates: dict[str, str] = {}
        if mapped_name:
            updates["name"] = mapped_name
        if catchup_user_id:
            updates["catchup_user_id"] = catchup_user_id
        if not updates:
            return user
        return user.model_copy(update=updates)

    def _apply_issue_user_mapping(self, db: Session, issue: GithubIssue) -> GithubIssue:
        comments = [
            comment.model_copy(
                update={"author": self._apply_user_mapping(db, comment.author)}
            )
            for comment in issue.comments
        ]
        return issue.model_copy(
            update={
                "author": self._apply_user_mapping(db, issue.author),
                "assignees": [
                    self._apply_user_mapping(db, assignee)
                    for assignee in issue.assignees
                ],
                "comments": comments,
            }
        )

    def _apply_pr_user_mapping(self, db: Session, pr: GithubPullRequest) -> GithubPullRequest:
        issue_comments = [
            comment.model_copy(
                update={"author": self._apply_user_mapping(db, comment.author)}
            )
            for comment in pr.issue_comments
        ]
        comments = [
            comment.model_copy(
                update={"author": self._apply_user_mapping(db, comment.author)}
            )
            for comment in pr.comments
        ]
        reviews = [
            review.model_copy(
                update={"author": self._apply_user_mapping(db, review.author)}
            )
            for review in pr.reviews
        ]

        commits = []
        for commit in pr.commits:
            commit_author_name = self._resolve_github_real_name(db, commit.author_login)
            commit_author = self._apply_user_mapping(db, commit.author)
            updates = {}
            if commit_author_name and commit.author_name != commit_author_name:
                updates["author_name"] = commit_author_name
            if commit_author is not commit.author:
                updates["author"] = commit_author
            commits.append(commit.model_copy(update=updates) if updates else commit)

        return pr.model_copy(
            update={
                "author": self._apply_user_mapping(db, pr.author),
                "assignees": [
                    self._apply_user_mapping(db, assignee)
                    for assignee in pr.assignees
                ],
                "reviewers": [
                    self._apply_user_mapping(db, reviewer)
                    for reviewer in pr.reviewers
                ],
                "merged_by": self._apply_user_mapping(db, pr.merged_by),
                "reviews": reviews,
                "issue_comments": issue_comments,
                "comments": comments,
                "commits": commits,
            }
        )
