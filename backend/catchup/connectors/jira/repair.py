import asyncio
from datetime import datetime
from typing import Literal
from typing import Any

import structlog
from catchup.components.summarizer import SummarizeRequest
from langchain_core.documents import Document

from catchup.connectors.jira.client import JiraApiError
from catchup.connectors.jira.client import JiraRateLimitError
from catchup.connectors.jira.context_store import JiraContextStore
from catchup.connectors.jira.issue_query import build_gap_item
from catchup.connectors.jira.issue_query import build_issue_since_jql
from catchup.connectors.jira.issue_query import classify_record_type
from catchup.connectors.jira.issue_query import extract_record_ids_from_doc_ids
from catchup.connectors.jira.issue_query import sort_record_ids
from catchup.connectors.jira.results import JiraRecordGapReport
from catchup.connectors.jira.results import JiraRecordRetryItem
from catchup.connectors.jira.results import JiraRecordRetryResult
from catchup.connectors.jira.runtime import JiraRuntime
from catchup.configs.config import settings

logger = structlog.get_logger()


class JiraRepairService:
    """Full Sync Repair / Manual Repair"""

    def __init__(
        self,
        runtime: JiraRuntime,
        context_store: JiraContextStore,
    ):
        self.runtime = runtime
        self.context_store = context_store

    async def _collect_project_record_ids(
        self,
        *,
        project_key: str,
        since: datetime | None,
    ) -> tuple[list[str], list[str]]:
        """동일 기간의 Jira 원본 식별자 목록을 expected set으로 수집한다."""
        issue_ids: list[str] = []
        epic_ids: list[str] = []
        next_page_token: str | None = None
        jql = build_issue_since_jql(project_key=project_key, since=since)

        while True:
            response = await self.runtime.client.search_issues(
                jql=jql,
                fields=["issuetype", "key"],
                max_results=settings.JIRA_SYNC_BATCH_SIZE,
                next_page_token=next_page_token,
            )

            issues = response.get("issues", [])
            if not issues:
                break

            for issue_data in issues:
                issue_key = issue_data.get("key")
                if not issue_key:
                    continue

                if classify_record_type(issue_data) == "epic":
                    epic_ids.append(issue_key)
                else:
                    issue_ids.append(issue_key)

            if response.get("isLast", True):
                break

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

            await asyncio.sleep(settings.JIRA_API_RATE_LIMIT_DELAY)

        return issue_ids, epic_ids

    async def _fetch_retry_issue(self, issue_key: str) -> dict[str, Any] | None:
        """단일 missing issue를 by-id로 다시 조회한다."""
        try:
            return await self.runtime.client.get_issue(issue_key)
        except JiraRateLimitError:
            raise
        except JiraApiError as exc:
            logger.warning(
                "jira_repair_issue_fetch_failed",
                cloud_id=self.runtime.cloud_id,
                issue_key=issue_key,
                error=str(exc),
            )
            return None

    async def _fetch_retry_issues(
        self,
        issue_keys: list[str],
    ) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
        if not issue_keys:
            return [], []

        results = await asyncio.gather(
            *[self._fetch_retry_issue(issue_key) for issue_key in issue_keys]
        )

        issues: list[tuple[str, dict[str, Any]]] = []
        failed_ids: list[str] = []
        for issue_key, issue_data in zip(issue_keys, results):
            if issue_data is None:
                failed_ids.append(issue_key)
                continue
            issues.append((issue_key, issue_data))

        return issues, failed_ids

    async def _build_retry_documents(
        self,
        *,
        project_key: str,
        requested_ids: list[str],
        expected_record_type: str,
    ) -> tuple[list[Document], list[str]]:
        """retry 대상 issue를 document로 재구성하고 실패한 id를 분리한다."""
        documents: list[Document] = []
        fetched_issues, failed_ids = await self._fetch_retry_issues(requested_ids)

        for issue_key, issue_data in fetched_issues:
            actual_record_type = classify_record_type(issue_data)
            if actual_record_type != expected_record_type:
                failed_ids.append(issue_key)
                continue

            try:
                documents.append(
                    self.runtime.transformer.transform_issue(
                        issue_data,
                        self.runtime.site_url,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "jira_repair_issue_transform_failed",
                    cloud_id=self.runtime.cloud_id,
                    project_key=project_key,
                    issue_key=issue_key,
                    error=str(exc),
                )
                failed_ids.append(issue_key)

        return documents, failed_ids

    async def _retry_record_batch(
        self,
        *,
        project_key: str,
        record_type: Literal["issue", "epic"],
        requested_ids: list[str],
    ) -> JiraRecordRetryItem:
        """동일 record_type의 missing id 묶음을 한 번에 재저장한다."""
        documents, failed_ids = await self._build_retry_documents(
            project_key=project_key,
            requested_ids=requested_ids,
            expected_record_type=record_type,
        )
        succeeded_count = 0

        if documents:
            try:
                if self.runtime.summarizer:
                    documents = await self._summarize_documents(documents)

                await self.runtime.repository.upsert_documents(
                    documents,
                    [doc.id for doc in documents],
                    audit_context=None,
                    context=(
                        f"entity_type={record_type},"
                        f"project_key={project_key},"
                        f"mode=partial_retry,"
                        f"doc_count={len(documents)}"
                    ),
                )
                succeeded_count = len(documents)
            except Exception as exc:
                logger.error(
                    "jira_repair_upsert_failed",
                    cloud_id=self.runtime.cloud_id,
                    project_key=project_key,
                    record_type=record_type,
                    error=str(exc),
                )
                failed_ids.extend(
                    extract_record_ids_from_doc_ids([doc.id for doc in documents])
                )

        return JiraRecordRetryItem(
            record_type=record_type,
            requested_ids=requested_ids,
            retried_count=len(requested_ids),
            succeeded_count=succeeded_count,
            failed_ids=sort_record_ids(set(failed_ids)),
        )

    async def _summarize_documents(
        self,
        documents: list[Document],
    ) -> list[Document]:
        """repair 재저장 경로에서도 본 저장 규칙과 같은 summarize 단계를 재사용한다."""
        if not self.runtime.summarizer or not documents:
            return documents

        requests = []
        for doc in documents:
            content = doc.metadata.get("contextual_content", doc.page_content)
            entity_type = doc.metadata.get("entity_type", "issue")
            source_type = f"jira_{entity_type}"
            requests.append(SummarizeRequest(content=content, source_type=source_type))

        summarized = await self.runtime.summarizer.summarize_batch(requests)
        for doc, summary in zip(documents, summarized):
            doc.page_content = summary

        return documents

    async def build_record_gap_report(
        self,
        *,
        project_key: str,
        since: datetime,
    ) -> JiraRecordGapReport:
        """Jira 원본 식별자와 저장된 문서를 비교해 missing report를 만든다."""
        expected_issue_ids, expected_epic_ids = await self._collect_project_record_ids(
            project_key=project_key,
            since=since,
        )
        stored_issue_doc_ids = await self.runtime.repository.list_jira_record_ids(
            project_key=project_key,
            entity_type="issue",
            since=since,
        )
        stored_epic_doc_ids = await self.runtime.repository.list_jira_record_ids(
            project_key=project_key,
            entity_type="epic",
            since=since,
        )

        issue_item = build_gap_item(
            record_type="issue",
            expected_ids=expected_issue_ids,
            stored_ids=extract_record_ids_from_doc_ids(stored_issue_doc_ids),
            stored_count=len(stored_issue_doc_ids),
        )
        epic_item = build_gap_item(
            record_type="epic",
            expected_ids=expected_epic_ids,
            stored_ids=extract_record_ids_from_doc_ids(stored_epic_doc_ids),
            stored_count=len(stored_epic_doc_ids),
        )

        logger.info(
            "jira_record_gap_report_built",
            cloud_id=self.runtime.cloud_id,
            project_key=project_key,
            sync_from=since.isoformat(),
            issue_missing_count=issue_item.missing_count,
            epic_missing_count=epic_item.missing_count,
        )

        return JiraRecordGapReport(records=[issue_item, epic_item])

    async def retry_missing_records(
        self,
        *,
        project_key: str,
        issue_ids: list[str] | None = None,
        epic_ids: list[str] | None = None,
    ) -> JiraRecordRetryResult:
        """수동 복구 요청에서 issue/epic missing id를 재시도한다."""
        requested_issue_ids = list(issue_ids or [])
        requested_epic_ids = list(epic_ids or [])
        result_items: list[JiraRecordRetryItem] = []

        if requested_issue_ids or requested_epic_ids:
            await self.context_store.prepare_transformer_context()

        if requested_issue_ids:
            result_items.append(
                await self._retry_record_batch(
                    project_key=project_key,
                    record_type="issue",
                    requested_ids=requested_issue_ids,
                )
            )

        if requested_epic_ids:
            result_items.append(
                await self._retry_record_batch(
                    project_key=project_key,
                    record_type="epic",
                    requested_ids=requested_epic_ids,
                )
            )

        logger.info(
            "jira_missing_records_retry_completed",
            cloud_id=self.runtime.cloud_id,
            project_key=project_key,
            issue_retry_count=len(requested_issue_ids),
            epic_retry_count=len(requested_epic_ids),
        )

        return JiraRecordRetryResult(records=result_items)

    async def delete_issue_documents(self, issue_keys: list[str]) -> int:
        """issue delete 이벤트를 위해 issue/epic 문서를 함께 정리한다."""
        unique_issue_keys = sorted({key for key in issue_keys if key})
        if not unique_issue_keys:
            return 0

        doc_ids: list[str] = []
        for issue_key in unique_issue_keys:
            doc_ids.append(f"jira:issue:{issue_key}")
            doc_ids.append(f"jira:epic:{issue_key}")

        await self.runtime.repository.delete_documents(doc_ids)

        logger.info(
            "jira_issue_documents_deleted",
            cloud_id=self.runtime.cloud_id,
            issue_count=len(unique_issue_keys),
            doc_count=len(doc_ids),
        )
        return len(doc_ids)
