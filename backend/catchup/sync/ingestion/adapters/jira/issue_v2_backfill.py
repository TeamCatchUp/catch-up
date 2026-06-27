from __future__ import annotations

import traceback

import structlog
from fastapi.concurrency import run_in_threadpool

from catchup.sync.ingestion.adapters.jira.issue_common import (
    JiraIssueIngestionAdapterBase,
)
from catchup.sync.ingestion.adapters.jira.issue_execution import (
    JiraIssueFetchedIssuesResult,
)
from catchup.sync.ingestion.adapters.jira.issue_execution import JiraIssuePersistResult
from catchup.sync.ingestion.adapters.jira.issue_execution import JiraIssueSummaryResult
from catchup.sync.ingestion.adapters.jira.issue_execution import (
    JiraIssueSyncExecutionResult,
)
from catchup.sync.ingestion.adapters.jira.issue_execution import (
    JiraIssueTransformResult,
)
from catchup.sync.ingestion.adapters.jira.issue_execution import (
    JiraIssueV2BackfillExecutionRequest,
)
from catchup.sync.ingestion.adapters.jira.issue_execution import JiraIssueV2BackfillSeed
from catchup.sync.ingestion.schemas import SyncWindow

logger = structlog.get_logger(__name__)


class JiraIssueV2BackfillAdapter(JiraIssueIngestionAdapterBase):
    """Backfill Jira Issue v2 records by hydrating v1 seeds through Jira API."""

    async def fetch(
        self,
        *,
        execution: JiraIssueV2BackfillExecutionRequest,
        sync_window: SyncWindow,
    ) -> JiraIssueFetchedIssuesResult:
        _ = sync_window
        issues: list[dict] = []
        failed_record_ids: list[str] = []
        error_messages: list[str] = []

        for seed in execution.seeds:
            try:
                issues.append(await self._dependencies.client.get_issue(seed.record_id))
            except Exception as exc:
                error_messages.append(_format_exception_trace(exc))
                logger.warning(
                    "jira_issue_v2_backfill_hydrate_failed",
                    cloud_id=execution.tenant_id,
                    project_key=execution.project_key,
                    issue_key=seed.record_id,
                    document_id=seed.langchain_id,
                    error=str(exc),
                    exc_info=True,
                )
                failed_record_ids.append(seed.record_id)

        return JiraIssueFetchedIssuesResult(
            issues=tuple(issues),
            fetched_record_ids=tuple(
                issue.get("key", "") for issue in issues if issue.get("key")
            ),
            failed_record_ids=tuple(dict.fromkeys(failed_record_ids)),
            fetch_error_count=len(set(failed_record_ids)),
            error_type="jira_issue_v2_backfill_hydrate_failed"
            if failed_record_ids
            else None,
            error_message=_combine_error_messages(error_messages),
        )

    async def transform(
        self,
        *,
        execution: JiraIssueV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        fetched: JiraIssueFetchedIssuesResult,
    ) -> JiraIssueTransformResult:
        _ = sync_window
        seed_by_issue_key = {seed.record_id: seed for seed in execution.seeds}
        seed_langchain_id_by_issue_key = {
            seed.record_id: seed.langchain_id for seed in execution.seeds
        }

        parsed_issues, parse_failed_ids, parse_error_message = await run_in_threadpool(
            self._parse_fetched_issues,
            tuple(fetched.issues),
        )

        if self._dependencies.v2_document_builder is None:
            v2_failed_ids = tuple(seed.langchain_id for seed in execution.seeds)
            return JiraIssueTransformResult(
                v2_failed_ids=v2_failed_ids,
                error_count=len(v2_failed_ids),
                error_type="jira_issue_v2_backfill_document_builder_missing",
                error_message="Jira v2 document builder is missing",
            )

        v2_documents, document_ids, build_failed_ids = (
            self._dependencies.v2_document_builder.build_from_backfill_seeds(
                tuple(parsed_issues),
                cloud_id=execution.tenant_id,
                seed_by_issue_key=seed_by_issue_key,
            )
        )
        failed_record_ids = tuple(
            dict.fromkeys(
                (
                    *fetched.failed_record_ids,
                    *parse_failed_ids,
                    *build_failed_ids,
                )
            )
        )
        v2_failed_ids = tuple(
            dict.fromkeys(
                seed_langchain_id_by_issue_key.get(record_id, record_id)
                for record_id in failed_record_ids
            )
        )
        return JiraIssueTransformResult(
            v2_documents=tuple(v2_documents),
            prepared_document_ids=tuple(document_ids),
            error_count=len(failed_record_ids),
            v2_failed_ids=v2_failed_ids,
            issue_count=len(parsed_issues),
            error_type=_transform_error_type(
                parse_failed_ids=parse_failed_ids,
                build_failed_ids=build_failed_ids,
            ),
            error_message=_first_error_type(
                parse_error_message,
                _document_build_error_message(build_failed_ids),
                fetched.error_message,
            ),
        )

    async def summarize(
        self,
        *,
        execution: JiraIssueV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        transformed: JiraIssueTransformResult,
    ) -> JiraIssueSummaryResult:
        _ = execution, sync_window
        return JiraIssueSummaryResult(
            summary_applied=False,
            document_count=len(transformed.v2_documents),
            v2_documents=transformed.v2_documents,
            document_ids=transformed.prepared_document_ids,
        )

    async def persist(
        self,
        *,
        execution: JiraIssueV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        transformed: JiraIssueTransformResult,
        summary: JiraIssueSummaryResult,
    ) -> JiraIssuePersistResult:
        _ = sync_window
        document_ids = list(summary.document_ids)
        v2_documents = list(summary.v2_documents)
        upstream_v2_failed_ids = tuple(transformed.v2_failed_ids)
        seed_by_langchain_id = _seed_by_langchain_id(execution.seeds)

        if not document_ids:
            return JiraIssuePersistResult(
                v2_error_count=len(upstream_v2_failed_ids),
                v2_failed_ids=upstream_v2_failed_ids,
                error_type=transformed.error_type,
                error_message=transformed.error_message,
            )

        if self._dependencies.vector_store is None:
            v2_failed_ids = tuple(dict.fromkeys((*upstream_v2_failed_ids, *document_ids)))
            return JiraIssuePersistResult(
                v2_error_count=len(v2_failed_ids),
                v2_failed_ids=v2_failed_ids,
                error_type="jira_issue_v2_backfill_vector_store_missing",
                error_message="Jira v2 vector store is missing",
            )

        embeddings = [seed_by_langchain_id[doc_id].embedding for doc_id in document_ids]
        try:
            persisted_ids = await self._dependencies.vector_store.upsert_documents(
                v2_documents,
                ids=document_ids,
                embeddings=embeddings,
            )
        except Exception as exc:
            error_message = _format_exception_trace(exc)
            logger.warning(
                "jira_issue_v2_backfill_upsert_failed",
                cloud_id=execution.tenant_id,
                project_key=execution.project_key,
                document_ids=document_ids,
                error=str(exc),
                exc_info=True,
            )
            v2_failed_ids = tuple(dict.fromkeys((*upstream_v2_failed_ids, *document_ids)))
            return JiraIssuePersistResult(
                v2_error_count=len(v2_failed_ids),
                v2_failed_ids=v2_failed_ids,
                error_type="jira_issue_v2_backfill_upsert_failed",
                error_message=error_message,
            )

        persisted_id_set = {str(persisted_id) for persisted_id in persisted_ids or []}
        write_failed_ids = tuple(
            doc_id for doc_id in document_ids if doc_id not in persisted_id_set
        )
        metadata_check_ids = [
            doc_id for doc_id in document_ids if doc_id in persisted_id_set
        ]
        if self._dependencies.v2_knowledge_repository is None:
            metadata_failed_ids = tuple(metadata_check_ids)
        else:
            metadata_failed_ids = (
                await self._dependencies.v2_knowledge_repository.find_missing_metadata_namespace_ids(
                    metadata_check_ids,
                    namespace="jira_issue",
                )
            )
        if metadata_failed_ids:
            logger.warning(
                "jira_issue_v2_backfill_metadata_missing_after_persist",
                connector="jira",
                entity_type="issue",
                scope_id=execution.tenant_id,
                target_id=execution.project_key,
                namespace="jira_issue",
                missing_metadata_ids=list(metadata_failed_ids),
                persisted_id_count=len(metadata_check_ids),
                missing_count=len(metadata_failed_ids),
            )
        failed_document_ids = tuple(
            dict.fromkeys((*write_failed_ids, *metadata_failed_ids))
        )
        v2_failed_ids = tuple(
            dict.fromkeys((*upstream_v2_failed_ids, *failed_document_ids))
        )
        return JiraIssuePersistResult(
            persisted_count=len(document_ids) - len(failed_document_ids),
            persisted_ids=tuple(
                document_id
                for document_id in document_ids
                if document_id not in failed_document_ids
            ),
            v2_error_count=len(v2_failed_ids),
            v2_failed_ids=v2_failed_ids,
            error_type="jira_issue_v2_backfill_metadata_missing_after_persist"
            if metadata_failed_ids
            else transformed.error_type,
            error_message=_metadata_missing_error_message(metadata_failed_ids)
            or transformed.error_message,
        )

    def build_result(
        self,
        *,
        execution: JiraIssueV2BackfillExecutionRequest,
        sync_window: SyncWindow,
        fetched: JiraIssueFetchedIssuesResult,
        transformed: JiraIssueTransformResult,
        summary: JiraIssueSummaryResult,
        persisted: JiraIssuePersistResult,
    ) -> JiraIssueSyncExecutionResult:
        _ = sync_window
        failed_ids = tuple(
            dict.fromkeys((*transformed.v2_failed_ids, *persisted.v2_failed_ids))
        )
        v2_failed_ids = tuple(
            dict.fromkeys((*transformed.v2_failed_ids, *persisted.v2_failed_ids))
        )
        return JiraIssueSyncExecutionResult(
            tenant_id=execution.tenant_id,
            target=execution.target,
            persisted_count=persisted.persisted_count,
            deleted_count=persisted.deleted_count,
            failed_count=len(failed_ids),
            v2_failed_count=len(v2_failed_ids),
            v2_failed_ids=v2_failed_ids,
            fetched=fetched,
            transformed=transformed,
            summary=summary,
            persisted=persisted,
            issue_count=transformed.issue_count,
            document_count=len(summary.v2_documents),
            error_count=transformed.error_count,
            metadata={
                "project_key": execution.project_key,
                "requested_count": len(execution.seeds),
                "error_type": _first_error_type(
                    fetched.error_type,
                    transformed.error_type,
                    persisted.error_type,
                ),
                "error_message": _first_error_type(
                    fetched.error_message,
                    transformed.error_message,
                    persisted.error_message,
                ),
                "failed_ids": list(failed_ids),
                "failed_record_ids": list(transformed.v2_failed_ids),
                "v2_failed_ids": list(v2_failed_ids),
            },
        )

    def _parse_fetched_issues(
        self,
        issues: tuple[dict, ...],
    ):
        parsed_issues = []
        failed_issue_keys: list[str] = []
        error_messages: list[str] = []
        for issue_data in issues:
            issue_key = str(issue_data.get("key") or "")
            try:
                parsed_issues.append(
                    self._dependencies.transformer.parse_issue(
                        issue_data,
                        self._dependencies.site_url,
                    )
                )
            except Exception as exc:
                error_messages.append(_format_exception_trace(exc))
                logger.warning(
                    "jira_issue_v2_backfill_parse_failed",
                    cloud_id=self._dependencies.cloud_id,
                    issue_key=issue_key,
                    error=str(exc),
                    exc_info=True,
                )
                if issue_key:
                    failed_issue_keys.append(issue_key)
        return (
            parsed_issues,
            tuple(dict.fromkeys(failed_issue_keys)),
            _combine_error_messages(error_messages),
        )


def _seed_by_langchain_id(
    seeds: tuple[JiraIssueV2BackfillSeed, ...],
) -> dict[str, JiraIssueV2BackfillSeed]:
    return {seed.langchain_id: seed for seed in seeds}


def _transform_error_type(
    *,
    parse_failed_ids: tuple[str, ...],
    build_failed_ids: tuple[str, ...],
) -> str | None:
    if parse_failed_ids:
        return "jira_issue_v2_backfill_parse_failed"
    if build_failed_ids:
        return "jira_issue_v2_backfill_document_build_failed"
    return None


def _first_error_type(*error_types: str | None) -> str | None:
    return next((error_type for error_type in error_types if error_type), None)


def _format_exception_trace(exc: Exception) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__, limit=3))


def _combine_error_messages(error_messages: list[str]) -> str | None:
    if not error_messages:
        return None
    return " | ".join(dict.fromkeys(error_messages))


def _document_build_error_message(build_failed_ids: tuple[str, ...]) -> str | None:
    if not build_failed_ids:
        return None
    return f"Jira v2 document build failed for record_ids={list(build_failed_ids)}"


def _metadata_missing_error_message(metadata_failed_ids: tuple[str, ...]) -> str | None:
    if not metadata_failed_ids:
        return None
    return (
        "Jira v2 metadata namespace missing after persist: "
        f"document_ids={list(metadata_failed_ids)}"
    )


JiraIssueV2BackfillIngestionAdapter = JiraIssueV2BackfillAdapter
