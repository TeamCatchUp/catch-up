"""Jira issue/epic ingestion 실행 모듈.

collect, fetch-transform, summarize, vector upsert를 한 파이프라인으로 묶는다.
"""

import asyncio
from datetime import datetime
from typing import Literal

import structlog
from langchain_core.documents import Document

from catchup.components.summarizer import SummarizeRequest
from catchup.configs.config import settings
from catchup.connectors.jira.client import JiraRateLimitError
from catchup.connectors.jira.context_store import JiraContextStore
from catchup.connectors.jira.issue_query import build_issue_range_jql
from catchup.connectors.jira.issue_query import build_issue_sync_jql
from catchup.connectors.jira.issue_query import classify_record_type
from catchup.connectors.jira.runtime import JiraRuntime
from catchup.sync.audit import SyncAuditContext

logger = structlog.get_logger()


class JiraIssueSyncService:
    """Issue/Epic 동기화 파이프라인"""

    def __init__(
        self,
        runtime: JiraRuntime,
        context_store: JiraContextStore,
    ):
        self.runtime = runtime
        self.context_store = context_store

    async def collect_issue_identifiers(
        self,
        *,
        project_key: str,
        range_start: datetime,
        range_end: datetime,
    ) -> list[str]:
        """issue/epic identifier 목록을 페이지 단위로 수집"""
        identifiers: list[str] = []
        jql = build_issue_range_jql(
            project_key=project_key,
            range_start=range_start,
            range_end=range_end,
        )
        next_page_token: str | None = None
        batch_size = settings.JIRA_SYNC_BATCH_SIZE

        logger.info(
            "jira_issue_identifier_collection_started",
            cloud_id=self.runtime.cloud_id,
            project_key=project_key,
            range_start=range_start.isoformat(),
            range_end=range_end.isoformat(),
            batch_size=batch_size,
        )

        while True:
            try:
                response = await self.runtime.client.search_issues(
                    jql=jql,
                    fields=["issuetype", "key"],
                    max_results=batch_size,
                    next_page_token=next_page_token,
                )
            except JiraRateLimitError as exc:
                logger.warning(
                    "jira_issue_identifier_collection_rate_limited",
                    cloud_id=self.runtime.cloud_id,
                    project_key=project_key,
                    retry_after=exc.retry_after,
                    range_start=range_start.isoformat(),
                    range_end=range_end.isoformat(),
                )
                raise

            issues = response.get("issues", [])
            is_last = response.get("isLast", True)

            if not issues:
                break

            logger.info(
                "jira_issue_identifier_batch_loaded",
                cloud_id=self.runtime.cloud_id,
                project_key=project_key,
                range_start=range_start.isoformat(),
                range_end=range_end.isoformat(),
                batch_count=len(issues),
                is_last=is_last,
            )

            for issue_data in issues:
                issue_key = str(issue_data.get("key") or "").strip()
                if not issue_key:
                    continue

                record_type = classify_record_type(issue_data)
                if record_type == "epic":
                    identifiers.append(f"jira:epic:{issue_key}")
                    continue

                identifiers.append(f"jira:issue:{issue_key}")

            if is_last:
                break

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

            await asyncio.sleep(settings.JIRA_API_RATE_LIMIT_DELAY)

        logger.info(
            "jira_issue_identifier_collection_completed",
            cloud_id=self.runtime.cloud_id,
            project_key=project_key,
            range_start=range_start.isoformat(),
            range_end=range_end.isoformat(),
            identifier_count=len(identifiers),
        )
        return identifiers

    async def sync_issue_range(
        self,
        *,
        project_key: str,
        range_start: datetime,
        range_end: datetime,
        audit_context: SyncAuditContext | None = None,
    ) -> dict[str, int]:
        """range 기반 Full Sync용 진입점"""
        return await self._sync_issue_documents(
            project_key=project_key,
            range_start=range_start,
            range_end=range_end,
            audit_context=audit_context,
            sync_mode="full",
        )

    async def _sync_issue_documents(
        self,
        *,
        project_key: str,
        since: datetime | None = None,
        range_start: datetime | None = None,
        range_end: datetime | None = None,
        audit_context: SyncAuditContext | None = None,
        sync_mode: Literal["full", "incremental"] = "full",
    ) -> dict[str, int]:
        """
        Issue 문서 동기화의 공통 실행 메서드
        full은 range 기반, incremental은 since 기반
        """
        if sync_mode == "full":
            if range_start is None or range_end is None:
                raise ValueError("jira full sync requires range_start and range_end")
            if since is not None:
                raise ValueError("jira full sync does not support since")
        elif sync_mode == "incremental":
            if range_start is not None or range_end is not None:
                raise ValueError("jira incremental sync does not support range_start/range_end")

        logger.info(
            "jira_project_issue_sync_started",
            cloud_id=self.runtime.cloud_id,
            project_key=project_key,
            sync_mode=sync_mode,
            since=since.isoformat() if since else None,
            range_start=range_start.isoformat() if range_start else None,
            range_end=range_end.isoformat() if range_end else None,
            job_id=audit_context.job_id if audit_context else None,
            task_id=audit_context.task_id if audit_context else None,
        )

        sprint_cache: dict = {}

        try:
            sprint_cache = await self.context_store.prepare_transformer_context()
            logger.info(
                "jira_project_context_loaded",
                cloud_id=self.runtime.cloud_id,
                project_key=project_key,
                sync_mode=sync_mode,
                sprint_count=len(sprint_cache),
            )
        except Exception as exc:
            logger.warning(
                "jira_project_context_load_failed",
                cloud_id=self.runtime.cloud_id,
                project_key=project_key,
                sync_mode=sync_mode,
                error=str(exc),
            )

        results = {"issues": 0, "epics": 0, "errors": 0}
        queue: asyncio.Queue = asyncio.Queue(maxsize=2)

        producer = asyncio.create_task(
            self._fetch_and_transform(
                project_key=project_key,
                queue=queue,
                results=results,
                since=since,
                range_start=range_start,
                range_end=range_end,
                sync_mode=sync_mode,
            )
        )
        consumer = asyncio.create_task(
            self._summarize_and_store(
                queue,
                project_key=project_key,
                audit_context=audit_context,
            )
        )

        await asyncio.gather(producer, consumer)

        logger.info(
            "jira_project_sync_completed",
            cloud_id=self.runtime.cloud_id,
            project_key=project_key,
            sync_mode=sync_mode,
            since=since.isoformat() if since else None,
            range_start=range_start.isoformat() if range_start else None,
            range_end=range_end.isoformat() if range_end else None,
            issue_count=results["issues"],
            epic_count=results["epics"],
            error_count=results["errors"],
        )
        return results

    async def _fetch_and_transform(
        self,
        *,
        project_key: str,
        queue: asyncio.Queue,
        results: dict[str, int],
        since: datetime | None = None,
        range_start: datetime | None = None,
        range_end: datetime | None = None,
        sync_mode: Literal["full", "incremental"] = "full",
    ) -> None:
        """API fetch & transform"""
        jql = build_issue_sync_jql(
            project_key=project_key,
            since=since,
            range_start=range_start,
            range_end=range_end,
        )
        jql_mode = "range" if range_start is not None and range_end is not None else "since"

        logger.info(
            "jira_issue_fetch_started",
            cloud_id=self.runtime.cloud_id,
            project_key=project_key,
            sync_mode=sync_mode,
            jql_mode=jql_mode,
            since=since.isoformat() if since else None,
            range_start=range_start.isoformat() if range_start else None,
            range_end=range_end.isoformat() if range_end else None,
        )

        next_page_token: str | None = None
        batch_size = settings.JIRA_SYNC_BATCH_SIZE
        processed_count = 0

        try:
            while True:
                try:
                    response = await self.runtime.client.search_issues(
                        jql=jql,
                        fields=None,
                        max_results=batch_size,
                        next_page_token=next_page_token,
                    )

                    issues = response.get("issues", [])
                    is_last = response.get("isLast", True)

                    if not issues:
                        if processed_count == 0:
                            logger.info(
                                "jira_issue_fetch_empty",
                                cloud_id=self.runtime.cloud_id,
                                project_key=project_key,
                                sync_mode=sync_mode,
                                jql_mode=jql_mode,
                                since=since.isoformat() if since else None,
                                range_start=range_start.isoformat() if range_start else None,
                                range_end=range_end.isoformat() if range_end else None,
                            )
                        break

                    processed_count += len(issues)
                    logger.info(
                        "jira_issue_batch_loaded",
                        cloud_id=self.runtime.cloud_id,
                        project_key=project_key,
                        sync_mode=sync_mode,
                        jql_mode=jql_mode,
                        batch_count=len(issues),
                        processed_count=processed_count,
                        is_last=is_last,
                    )

                    documents: list[Document] = []
                    doc_ids: list[str] = []

                    for issue_data in issues:
                        try:
                            doc = self.runtime.transformer.transform_issue(
                                issue_data,
                                self.runtime.site_url,
                            )
                            documents.append(doc)
                            doc_ids.append(doc.id)

                            if doc.metadata.get("entity_type") == "epic":
                                results["epics"] += 1
                            else:
                                results["issues"] += 1
                        except Exception as exc:
                            logger.error(
                                "jira_issue_transform_failed",
                                cloud_id=self.runtime.cloud_id,
                                project_key=project_key,
                                sync_mode=sync_mode,
                                jql_mode=jql_mode,
                                issue_key=issue_data.get("key"),
                                error=str(exc),
                            )
                            results["errors"] += 1

                    if documents:
                        await queue.put((documents, doc_ids))
                        logger.info(
                            "jira_issue_batch_enqueued",
                            cloud_id=self.runtime.cloud_id,
                            project_key=project_key,
                            sync_mode=sync_mode,
                            jql_mode=jql_mode,
                            document_count=len(documents),
                        )
                    else:
                        logger.warning(
                            "jira_issue_batch_produced_no_documents",
                            cloud_id=self.runtime.cloud_id,
                            project_key=project_key,
                            sync_mode=sync_mode,
                            jql_mode=jql_mode,
                            batch_count=len(issues),
                        )

                    if is_last:
                        break

                    next_page_token = response.get("nextPageToken")
                    if not next_page_token:
                        logger.warning(
                            "jira_issue_fetch_stopped_without_next_page_token",
                            cloud_id=self.runtime.cloud_id,
                            project_key=project_key,
                            sync_mode=sync_mode,
                            jql_mode=jql_mode,
                            processed_count=processed_count,
                        )
                        break

                    await asyncio.sleep(settings.JIRA_API_RATE_LIMIT_DELAY)
                except JiraRateLimitError as exc:
                    logger.warning(
                        "jira_issue_fetch_rate_limited",
                        cloud_id=self.runtime.cloud_id,
                        project_key=project_key,
                        sync_mode=sync_mode,
                        jql_mode=jql_mode,
                        retry_after=exc.retry_after,
                        processed_count=processed_count,
                    )
                    raise
        finally:
            logger.info(
                "jira_issue_fetch_completed",
                cloud_id=self.runtime.cloud_id,
                project_key=project_key,
                sync_mode=sync_mode,
                jql_mode=jql_mode,
                processed_count=processed_count,
                issue_count=results["issues"],
                epic_count=results["epics"],
                error_count=results["errors"],
            )
            await queue.put(None)

    async def _summarize_and_store(
        self,
        queue: asyncio.Queue,
        *,
        project_key: str,
        audit_context: SyncAuditContext | None = None,
    ) -> None:
        """Summarize & Persist"""
        while True:
            batch = await queue.get()
            if batch is None:
                break

            documents, doc_ids = batch

            if self.runtime.summarizer:
                documents = await self._summarize_documents(
                    documents,
                    project_key=project_key,
                    audit_context=audit_context,
                )

            await self.runtime.repository.upsert_documents(
                documents,
                doc_ids,
                audit_context=audit_context,
                context=(
                    f"entity_type=issue,project_key={project_key},"
                    f"doc_count={len(documents)}"
                ),
            )

    async def _summarize_documents(
        self,
        documents: list[Document],
        *,
        project_key: str,
        audit_context: SyncAuditContext | None = None,
    ) -> list[Document]:
        if not self.runtime.summarizer or not documents:
            return documents

        requests = []
        for doc in documents:
            content = doc.metadata.get("contextual_content", doc.page_content)
            entity_type = doc.metadata.get("entity_type", "issue")
            source_type = f"jira_{entity_type}"
            requests.append(SummarizeRequest(content=content, source_type=source_type))

        summarized = await self.runtime.summarizer.summarize_batch(
            requests,
            audit_context=audit_context,
            context=(
                f"entity_type=issue,project_key={project_key},"
                f"doc_count={len(documents)}"
            ),
        )

        for doc, summary in zip(documents, summarized):
            doc.page_content = summary

        logger.debug(
            "jira_documents_summarized",
            cloud_id=self.runtime.cloud_id,
            document_count=len(documents),
        )
        return documents

    async def incremental_sync(
        self,
        *,
        project_key: str,
        record_id: str,
        event_kind: str,
        since: datetime | None,
        audit_context: SyncAuditContext | None = None,
        delete_documents,
    ) -> dict[str, int | bool]:
        normalized_event_kind = event_kind.strip().lower()
        if normalized_event_kind == "deleted":
            deleted = await delete_documents([record_id])
            return {
                "synced": deleted,
                "errors": 0,
                "skipped": False,
            }

        result = await self._sync_issue_documents(
            project_key=project_key,
            since=since,
            audit_context=audit_context,
            sync_mode="incremental",
        )
        return {
            "synced": int(result.get("issues", 0)) + int(result.get("epics", 0)),
            "errors": int(result.get("errors", 0)),
            "skipped": False,
        }
