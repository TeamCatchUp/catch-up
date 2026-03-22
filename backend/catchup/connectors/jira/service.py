"""
Jira 데이터 동기화 서비스

Jira API에서 데이터를 가져와 PGVector에 저장하는 서비스.
JiraApiClient, JiraFieldMapper, JiraTransformer, PGVectorRepository를 조합.

사용법:
    # 초기화
    service = JiraIngestionService(cloud_id, access_token, site_url)
    await service.initialize()

    # 전체 동기화
    await service.full_sync(project_keys=["CATCH", "PROJ"], sync_from_dt=datetime.now(timezone.utc))

    # 증분 동기화
    await service.incremental_sync(project_key="CATCH", record_id="CATCH-1", event_kind="updated", since=None)
"""

import asyncio
from dataclasses import dataclass, field
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi.concurrency import run_in_threadpool
from langchain_core.documents import Document

from catchup.connectors.atlassian.token_manager import AtlassianTokenProvider
from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.connectors.jira.client import (
    JiraApiClient,
    JiraApiError,
    JiraRateLimitError,
)
from catchup.connectors.jira.field_mapper import JiraFieldMapper
from catchup.connectors.jira.transformers import JiraTransformer, normalize_issue_type
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.components.summarizer import SummarizerService, SummarizeRequest, get_summarizer_service
from catchup.configs.config import settings
from catchup.db.engine import SessionLocal
from catchup.db.jira import domain_repository as jira_entities
from catchup.sync.audit import SyncAuditContext
from catchup.sync.common.schemas import TargetSyncResult

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class JiraRecordGapItem:
    record_type: str
    expected_count: int = 0
    stored_count: int = 0
    missing_count: int = 0
    missing_ids: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class JiraRecordGapReport:
    records: list[JiraRecordGapItem] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class JiraRecordRetryItem:
    record_type: str
    requested_ids: list[str] = field(default_factory=list)
    retried_count: int = 0
    succeeded_count: int = 0
    failed_ids: list[str] = field(default_factory=list)
    remaining_missing_ids: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class JiraRecordRetryResult:
    records: list[JiraRecordRetryItem] = field(default_factory=list)


class JiraIngestionService:
    """
    Jira 데이터 동기화 서비스

    Jira Cloud에서 데이터를 가져와 PGVector 벡터 저장소에 적재.
    Issue, Epic, Project, Sprint 등 엔티티별 동기화 지원.

    Attributes:
        client: Jira REST API 클라이언트
        field_mapper: 커스텀 필드 ID → 이름 매퍼
        transformer: Jira 엔티티 → LangChain Document 변환기
        repository: PGVector 벡터 저장소
        cloud_id: Jira Cloud 인스턴스 ID
        site_url: Jira 사이트 URL
    """

    def __init__(
        self,
        repository: PGVectorRepository,
        cloud_id: str,
        token_provider: AtlassianTokenProvider,
        site_url: str,
        enable_summarization: bool = True,
    ):
        """
        JiraIngestionService 초기화

        Args:
            cloud_id: Jira Cloud 인스턴스 ID (JiraOAuthToken에서 조회)
            token_provider: 요청 시점 최신 토큰 제공자
            site_url: Jira 사이트 URL (예: "https://catchup.atlassian.net")
            enable_summarization: 임베딩 전 LLM 요약 활성화 여부
        """
        self.cloud_id = cloud_id
        self.site_url = site_url.rstrip("/")
        self.enable_summarization = enable_summarization

        # 컴포넌트 초기화
        self.client = JiraApiClient(cloud_id, token_provider)
        self.field_mapper = JiraFieldMapper(self.client)
        self.transformer: JiraTransformer | None = None
        self.repository = repository
        self.summarizer: SummarizerService | None = None

        self._initialized = False

    async def initialize(self) -> None:
        """
        서비스 초기화

        Field Mapper와 PGVector Repository를 초기화.
        동기화 작업 전에 반드시 호출해야 함.
        """
        if self._initialized:
            return

        logger.info(f"Initializing JiraIngestionService for cloud_id={self.cloud_id}")

        # Field Mapper 초기화 (Jira 필드 목록 조회)
        await self.field_mapper.initialize()

        # Transformer 생성 (field_mapper 필요)
        self.transformer = JiraTransformer(self.field_mapper)

        # Summarizer 초기화 (요약 활성화 시)
        if self.enable_summarization:
            self.summarizer = get_summarizer_service()
            logger.info("Summarization enabled for embedding optimization")

        # PGVector 초기화
        self.repository.ensure_initialized()

        self._initialized = True
        logger.info("JiraIngestionService initialized successfully")

    def _ensure_initialized(self) -> None:
        """초기화 확인"""
        if not self._initialized or self.transformer is None:
            raise RuntimeError(
                "JiraIngestionService not initialized. "
                "Call await service.initialize() first."
            )

    def _resolve_sync_from_dt(
        self,
        sync_days: int | None,
    ) -> datetime:
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
        return sorted(record_ids)

    @staticmethod
    def _build_gap_item(
        *,
        record_type: str,
        expected_ids: list[str],
        stored_ids: list[str],
        stored_count: int,
    ) -> JiraRecordGapItem:
        missing_ids = sorted(set(expected_ids) - set(stored_ids))
        return JiraRecordGapItem(
            record_type=record_type,
            expected_count=len(expected_ids),
            stored_count=stored_count,
            missing_count=len(missing_ids),
            missing_ids=missing_ids,
        )

    def _load_project_context_sync(
        self,
        project_key: str,
    ) -> None:
        with SessionLocal() as db:
            self.transformer.project_cache = jira_entities.get_projects_by_keys(
                db,
                self.cloud_id,
                [project_key],
            )
            sprints = jira_entities.get_sprints_by_cloud_id(db, self.cloud_id)
            self.transformer.sprint_cache = {s.sprint_id: s for s in sprints}

    async def _prepare_project_context(
        self,
        project_key: str,
    ) -> None:
        await run_in_threadpool(self._load_project_context_sync, project_key)

    def _load_project_keys_db(self) -> list[str]:
        with SessionLocal() as db:
            projects = jira_entities.get_projects_by_cloud_id(db, self.cloud_id)
            return [project.project_key for project in projects]

    async def _load_project_keys(self) -> list[str]:
        return await run_in_threadpool(self._load_project_keys_db)

    def _load_project_sync_context_db(
        self,
        project_key: str,
    ) -> tuple[dict[str, Any], dict[int, Any]]:
        with SessionLocal() as db:
            project_cache = jira_entities.get_projects_by_keys(
                db,
                self.cloud_id,
                [project_key],
            )
            sprints = jira_entities.get_sprints_by_cloud_id(db, self.cloud_id)
            sprint_cache = {sprint.sprint_id: sprint for sprint in sprints}
            return project_cache, sprint_cache

    async def _load_project_sync_context(
        self,
        project_key: str,
    ) -> tuple[dict[str, Any], dict[int, Any]]:
        return await run_in_threadpool(
            self._load_project_sync_context_db,
            project_key,
        )

    def _classify_record_type(
        self,
        issue_data: dict[str, Any],
    ) -> str:
        issue_type = normalize_issue_type(
            issue_data.get("fields", {}).get("issuetype", {}).get("name", ""),
        )
        return "epic" if issue_type.lower() == "epic" else "issue"

    def _build_issue_jql(
        self,
        *,
        project_key: str,
        since: datetime | None = None,
    ) -> str:
        jql_parts = [f'project = "{project_key}"']
        if since:
            since_str = since.strftime("%Y-%m-%d %H:%M")
            jql_parts.insert(0, f'updated >= "{since_str}"')

        return " AND ".join(jql_parts) + " ORDER BY updated DESC"

    async def _collect_project_record_ids(
        self,
        *,
        project_key: str,
        since: datetime | None,
    ) -> tuple[list[str], list[str]]:
        issue_ids: list[str] = []
        epic_ids: list[str] = []
        next_page_token: str | None = None
        jql = self._build_issue_jql(project_key=project_key, since=since)

        while True:
            response = await self.client.search_issues(
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

                if self._classify_record_type(issue_data) == "epic":
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

    async def _fetch_retry_issue(
        self,
        issue_key: str,
    ) -> dict[str, Any] | None:
        try:
            return await self.client.get_issue(issue_key)
        except JiraApiError as exc:
            logger.warning(
                "[JIRA][REPAIR] Failed to fetch issue: cloud_id=%s, issue_key=%s, error=%s",
                self.cloud_id,
                issue_key,
                exc,
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
        documents: list[Document] = []
        fetched_issues, failed_ids = await self._fetch_retry_issues(requested_ids)

        for issue_key, issue_data in fetched_issues:
            actual_record_type = self._classify_record_type(issue_data)
            if actual_record_type != expected_record_type:
                failed_ids.append(issue_key)
                continue

            try:
                documents.append(
                    self.transformer.transform_issue(
                        issue_data,
                        self.site_url,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "[JIRA][REPAIR] Failed to transform issue: cloud_id=%s, project_key=%s, issue_key=%s, error=%s",
                    self.cloud_id,
                    project_key,
                    issue_key,
                    exc,
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
        documents, failed_ids = await self._build_retry_documents(
            project_key=project_key,
            requested_ids=requested_ids,
            expected_record_type=record_type,
        )
        succeeded_count = 0

        if documents:
            try:
                upsert_documents = documents
                if self.summarizer:
                    upsert_documents = await self._summarize_documents(
                        documents,
                        project_key=project_key,
                        audit_context=None,
                    )
                await self.repository.upsert_documents(
                    upsert_documents,
                    [doc.id for doc in upsert_documents],
                    audit_context=None,
                    context=(
                        f"entity_type={record_type},"
                        f"project_key={project_key},"
                        f"mode=partial_retry,"
                        f"doc_count={len(upsert_documents)}"
                    ),
                )
                succeeded_count = len(upsert_documents)
            except Exception as exc:
                logger.error(
                    "[JIRA][REPAIR] Failed to upsert %s docs: cloud_id=%s, project_key=%s, error=%s",
                    record_type,
                    self.cloud_id,
                    project_key,
                    exc,
                    exc_info=True,
                )
                failed_ids.extend(
                    self._extract_record_ids_from_doc_ids([doc.id for doc in documents])
                )

        return JiraRecordRetryItem(
            record_type=record_type,
            requested_ids=requested_ids,
            retried_count=len(requested_ids),
            succeeded_count=succeeded_count,
            failed_ids=self._sort_record_ids(set(failed_ids)),
        )

    async def sync_metadata(
        self,
        project_keys: list[str] | None = None,
        *,
        raise_on_error: bool = False,
    ) -> dict[str, dict[str, int]]:
        """
        Jira App Installation 직후 메타데이터 동기화

        Users + Projects(+ 선택적 Sprints)를 먼저 동기화하여
        이후 Issue 동기화의 캐시 품질을 높임.
        """
        self._ensure_initialized()

        results = {
            "users": {"synced": 0, "errors": 0},
            "projects": {"synced": 0, "errors": 0},
            "sprints": {"synced": 0, "errors": 0},
        }

        user_results = await self._sync_all_users()
        if raise_on_error and user_results["errors"] > 0:
            raise RuntimeError(f"jira user metadata refresh failed: cloud_id={self.cloud_id}")

        project_results = await self._sync_all_projects(project_keys)
        if raise_on_error and project_results["errors"] > 0:
            raise RuntimeError(f"jira project metadata refresh failed: cloud_id={self.cloud_id}")

        results["users"] = user_results
        results["projects"] = project_results

        if await self.client.is_agile_available():
            sprint_results = await self._sync_all_sprints()
            results["sprints"] = sprint_results
            if raise_on_error and sprint_results["errors"] > 0:
                raise RuntimeError(
                    f"jira sprint metadata refresh failed: cloud_id={self.cloud_id}"
                )

        return results

    # ================================================================
    # 전체 동기화 (Full Sync)
    # ================================================================

    async def full_sync(
        self,
        project_keys: list[str] | None = None,
        sync_from_dt: datetime | None = None,
        audit_context: SyncAuditContext | None = None,
    ) -> TargetSyncResult:
        """
        전체 동기화

        툴 연동시 최초 1회 실행
        Users -> Projects -> Sprints(Agile API 가능 시) -> Issues&Epics
        """
        self._ensure_initialized()

        sync_from = sync_from_dt or (
            datetime.now(timezone.utc) - timedelta(days=settings.DEFAULT_SYNC_DAYS)
        )

        logger.info(
            f"[JIRA][FULL SYNC] Started for cloud_id={self.cloud_id}"
            f" projects={project_keys or 'all'}"
            f" since={sync_from.isoformat()}"
        )

        results = {
            "issues": {"synced": 0, "errors": 0},
            "epics": {"synced": 0, "errors": 0},
            "sprints": {"synced": 0, "errors": 0},
        }

        try:
            if await self.client.is_agile_available():
                sprint_results = await self._sync_all_sprints()
                results["sprints"] = sprint_results
            else:
                logger.info("[JIRA][FULL SYNC] Sprint Sync Skipped : Agile API Not Available")

            if not project_keys:
                project_keys = await self._load_project_keys()
            
            for project_key in project_keys:
                try:
                    project_result = await self._sync_project_issues(
                        project_key,
                        since=sync_from,
                        audit_context=audit_context,
                    )
                    results["issues"]["synced"] += project_result["issues"]
                    results["epics"]["synced"] += project_result["epics"]
                    results["issues"]["errors"] += project_result["errors"]
                except Exception as e:
                    logger.error(
                        f"[JIRA][FULL SYNC] Project sync failed: "
                        f"cloud_id={self.cloud_id}, project_key={project_key}, error={e}"
                    )
                    results["issues"]["errors"] += 1
                    results["epics"]["errors"] += 1
            logger.info(f"[JIRA][FULL SYNC] Completed : {results}")
            return TargetSyncResult(
                synced_count=(
                    int(results["issues"]["synced"])
                    + int(results["epics"]["synced"])
                    + int(results["sprints"]["synced"])
                ),
                error_count=(
                    int(results["issues"]["errors"])
                    + int(results["epics"]["errors"])
                    + int(results["sprints"]["errors"])
                ),
            )

        except Exception as e:
            logger.error(f"[JIRA][FULL SYNC] Failed : {e}")
            raise
        
    async def _sync_project_issues(
        self,
        project_key: str,
        since: datetime | None = None,
        audit_context: SyncAuditContext | None = None,
    ) -> dict[str, int]:
        """
        단일 프로젝트의 이슈 동기화 (Pipeline 방식)

        Stage 1 (Producer): API 조회 + Transform → Queue에 배치 전달
        Stage 2 (Consumer): Summarize + Embed/Upsert

        Returns:
            {"issues": 150, "epics": 10, "errors": 2}
        """
        self._ensure_initialized()

        # RDBMS에서 캐시 로드
        project_cache: dict = {}
        sprint_cache: dict = {}

        try:
            project_cache, sprint_cache = await self._load_project_sync_context(
                project_key,
            )

            logger.info(
                f"[JIRA][FULL SYNC] Loaded caches: "
                f"project_key={project_key}, {len(sprint_cache)} sprints"
            )
        except Exception as e:
            logger.warning(
                f"[JIRA][FULL SYNC] Failed to load caches, continuing without enrichment: "
                f"project_key={project_key}, error={e}"
            )

        # Transformer에 캐시 전달
        self.transformer.project_cache = project_cache
        self.transformer.sprint_cache = sprint_cache

        results = {"issues": 0, "epics": 0, "errors": 0}
        queue: asyncio.Queue = asyncio.Queue(maxsize=2)

        producer = asyncio.create_task(
            self._fetch_and_transform(project_key, since, queue, results)
        )
        consumer = asyncio.create_task(
            self._summarize_and_store(queue, project_key=project_key, audit_context=audit_context)
        )

        await asyncio.gather(producer, consumer)

        logger.info(
            f"[JIRA][FULL SYNC] Project issue sync completed: "
            f"project_key={project_key}, results={results}"
        )
        return results

    async def _fetch_and_transform(
        self,
        project_key: str,
        since: datetime | None,
        queue: asyncio.Queue,
        results: dict[str, int],
    ) -> None:
        """Stage 1 (Producer): API 조회 + Transform → Queue에 배치 전달"""
        jql_parts = [f'project = "{project_key}"']
        if since:
            since_str = since.strftime("%Y-%m-%d %H:%M")
            jql_parts.insert(0, f'updated >= "{since_str}"')

        jql = " AND ".join(jql_parts) + " ORDER BY updated DESC"

        logger.info(
            f"[JIRA][FULL SYNC] Fetching issues: "
            f"project_key={project_key}, jql={jql}"
        )

        next_page_token: str | None = None
        batch_size = settings.JIRA_SYNC_BATCH_SIZE
        processed_count = 0

        try:
            while True:
                try:
                    response = await self.client.search_issues(
                        jql=jql,
                        fields=None,
                        max_results=batch_size,
                        next_page_token=next_page_token,
                    )

                    issues = response.get("issues", [])
                    is_last = response.get("isLast", True)

                    if not issues:
                        break

                    processed_count += len(issues)
                    logger.info(
                        f"[JIRA][FULL SYNC] Processing batch: "
                        f"project_key={project_key}, batch={len(issues)}, total={processed_count}"
                    )

                    documents: list[Document] = []
                    doc_ids: list[str] = []

                    for issue_data in issues:
                        try:
                            doc = self.transformer.transform_issue(
                                issue_data,
                                self.site_url,
                            )
                            documents.append(doc)
                            doc_ids.append(doc.id)

                            if doc.metadata.get("entity_type") == "epic":
                                results["epics"] += 1
                            else:
                                results["issues"] += 1

                        except Exception as e:
                            logger.error(
                                f"[JIRA][FULL SYNC] Transform failed: "
                                f"project_key={project_key}, issue_key={issue_data.get('key')}, error={e}"
                            )
                            results["errors"] += 1

                    if documents:
                        await queue.put((documents, doc_ids))

                    if is_last:
                        break

                    next_page_token = response.get("nextPageToken")
                    if not next_page_token:
                        break

                    await asyncio.sleep(settings.JIRA_API_RATE_LIMIT_DELAY)

                except JiraRateLimitError as e:
                    logger.warning(
                        f"[JIRA][FULL SYNC] Rate limited: "
                        f"project_key={project_key}, retry_after={e.retry_after}s"
                    )
                    await asyncio.sleep(e.retry_after)
                    continue
        finally:
            await queue.put(None)

    async def _summarize_and_store(
        self,
        queue: asyncio.Queue,
        *,
        project_key: str,
        audit_context: SyncAuditContext | None = None,
    ) -> None:
        """Stage 2 (Consumer): Queue에서 배치 수신 → Summarize → Embed/Upsert"""
        while True:
            batch = await queue.get()
            if batch is None:
                break

            documents, doc_ids = batch

            if self.summarizer:
                documents = await self._summarize_documents(
                    documents,
                    project_key=project_key,
                    audit_context=audit_context,
                )

            await self.repository.upsert_documents(
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
        """
        문서들의 page_content를 LLM으로 요약하여 교체

        contextual_content(구조화된 정보 포함)를 요약 입력으로 사용하여
        더 풍부한 컨텍스트 기반 요약 생성.

        Args:
            documents: 요약할 Document 리스트

        Returns:
            page_content가 요약된 Document 리스트
        """
        if not self.summarizer or not documents:
            return documents

        # SummarizeRequest 리스트 생성 (source + entity_type → source_type)
        requests = []
        for doc in documents:
            content = doc.metadata.get("contextual_content", doc.page_content)
            entity_type = doc.metadata.get("entity_type", "issue")
            source_type = f"jira_{entity_type}"  # jira_issue, jira_epic, jira_sprint
            requests.append(SummarizeRequest(content=content, source_type=source_type))

        # 일괄 요약
        summarized = await self.summarizer.summarize_batch(
            requests,
            audit_context=audit_context,
            context=(
                f"entity_type=issue,project_key={project_key},"
                f"doc_count={len(documents)}"
            ),
        )

        # 요약된 텍스트로 교체
        for doc, summary in zip(documents, summarized):
            doc.page_content = summary

        logger.debug(f"Summarized {len(documents)} documents for embedding")
        return documents

    async def _sync_all_projects(
        self,
        project_keys: list[str] | None = None,
    ) -> dict[str, int]:
        """
        프로젝트 동기화 (RDBMS 저장)

        Args:
            db: SQLAlchemy Session
            project_keys: 동기화할 프로젝트 키 목록 (None이면 접근 가능한 모든 프로젝트)

        Returns:
            {"synced": 3, "errors": 0}
        """
        self._ensure_initialized()

        results = {"synced": 0, "errors": 0}
        projects_data: list[dict] = []

        def _sync_projects_snapshot_sync() -> dict[str, int]:
            with SessionLocal() as db:
                try:
                    result = jira_entities.sync_projects_snapshot(
                        db,
                        self.cloud_id,
                        projects_data,
                    )
                    db.commit()
                    return result
                except Exception:
                    db.rollback()
                    raise

        try:
            # 프로젝트 목록 결정
            if project_keys:
                keys_to_sync = project_keys
            else:
                all_projects = await self.client.get_all_projects()
                keys_to_sync = [p.get("key") for p in all_projects if p.get("key")]
                logger.info(f"Found {len(keys_to_sync)} accessible projects")

            # 각 프로젝트 조회 및 데이터 수집
            for project_key in keys_to_sync:
                try:
                    project_data = await self.client.get_project(
                        project_key,
                        expand="description,lead",
                    )

                    lead = project_data.get("lead", {})
                    url = f"{self.site_url}/projects/{project_key}"

                    # RDBMS 저장용 데이터 구성
                    projects_data.append({
                        "cloud_id": self.cloud_id,
                        "project_key": project_key,
                        "project_id": project_data.get("id", ""),
                        "project_name": project_data.get("name", ""),
                        "description": project_data.get("description"),
                        "project_type": project_data.get("projectTypeKey"),
                        "lead_account_id": lead.get("accountId"),
                        "lead_display_name": lead.get("displayName"),
                        "url": url,
                    })

                    results["synced"] += 1

                except JiraApiError as e:
                    logger.error(f"Failed to sync project {project_key}: {e}")
                    results["errors"] += 1

                await asyncio.sleep(settings.JIRA_API_RATE_LIMIT_DELAY)

            sync_result = await run_in_threadpool(
                _sync_projects_snapshot_sync,
            )
            logger.info(
                "[JIRA][METADATA] Project snapshot synced: cloud_id=%s, upserted=%s, deleted=%s",
                self.cloud_id,
                sync_result["upserted"],
                sync_result["deleted"],
            )

        except JiraApiError as e:
            logger.error(f"Failed to get project list (API error): {e}")
            results["errors"] += 1
        except Exception as e:
            logger.error(f"Failed to sync projects (DB error): {e}")
            results["errors"] += 1

        logger.info(f"Project sync completed: {results}")
        return results

    async def _sync_all_sprints(
        self,
    ) -> dict[str, int]:
        """
        모든 스프린트 동기화 (RDBMS 저장)

        Returns:
            {"synced": N, "errors": M}
        """
        self._ensure_initialized()

        results = {"synced": 0, "errors": 0}
        sprints_data: list[dict] = []

        def _upsert_sprints_sync() -> int:
            with SessionLocal() as db:
                try:
                    result = jira_entities.upsert_sprints_bulk(
                        db,
                        sprints_data,
                    )
                    db.commit()
                    return result
                except Exception:
                    db.rollback()
                    raise

        try:
            # 모든 보드 조회
            boards = await self.client.get_boards()

            for board in boards:
                board_id = board.get("id")
                project_key = board.get("location", {}).get("projectKey")

                try:
                    # 보드의 스프린트 조회
                    sprints_response = await self.client.get_board_sprints(board_id)
                    sprints = sprints_response.get("values", [])

                    for sprint_data in sprints:
                        # RDBMS 저장용 데이터 구성
                        sprints_data.append({
                            "cloud_id": self.cloud_id,
                            "sprint_id": sprint_data.get("id"),
                            "sprint_name": sprint_data.get("name", ""),
                            "state": sprint_data.get("state"),
                            "goal": sprint_data.get("goal"),
                            "project_key": project_key,
                            "board_id": board_id,
                            "start_date": parse_atlassian_datetime(
                                sprint_data.get("startDate")
                            ),
                            "end_date": parse_atlassian_datetime(
                                sprint_data.get("endDate")
                            ),
                            "complete_date": parse_atlassian_datetime(
                                sprint_data.get("completeDate")
                            ),
                        })

                        results["synced"] += 1

                except JiraApiError as e:
                    logger.error(f"Failed to sync sprints for board {board_id}: {e}")
                    results["errors"] += 1

                await asyncio.sleep(settings.JIRA_API_RATE_LIMIT_DELAY)

            # RDBMS 벌크 저장
            if sprints_data:
                await run_in_threadpool(
                    _upsert_sprints_sync,
                )
                logger.info(f"Saved {len(sprints_data)} sprints to RDBMS")

        except JiraApiError as e:
            logger.error(f"Failed to get boards (API error): {e}")
            results["errors"] += 1
        except Exception as e:
            logger.error(f"Failed to sync sprints (DB error): {e}")
            results["errors"] += 1

        logger.info(f"Sprint sync completed: {results}")
        return results

    async def _sync_all_users(
        self,
    ) -> dict[str, int]:
        """
        모든 사용자 동기화 (RDBMS 저장)

        Jira Cloud의 모든 사용자를 조회하여 RDBMS에 저장.

        Returns:
            {"synced": N, "errors": M}
        """
        self._ensure_initialized()

        results = {"synced": 0, "errors": 0}
        users_data: list[dict] = []

        def _upsert_users_sync() -> int:
            with SessionLocal() as db:
                try:
                    result = jira_entities.upsert_users_bulk(
                        db,
                        users_data,
                    )
                    db.commit()
                    return result
                except Exception:
                    db.rollback()
                    raise

        try:
            # 모든 사용자 조회
            all_users = await self.client.get_all_users()
            logger.info(f"Fetched {len(all_users)} users from Jira API")

            for user_data in all_users:
                account_id = user_data.get("accountId")
                if not account_id:
                    continue

                # RDBMS 저장용 데이터 구성
                users_data.append({
                    "cloud_id": self.cloud_id,
                    "account_id": account_id,
                    "account_type": user_data.get("accountType", "atlassian"),
                    "active": user_data.get("active", True),
                    "display_name": user_data.get("displayName", "Unknown"),
                    "email_address": user_data.get("emailAddress"),
                    "avatar_url": user_data.get("avatarUrls", {}).get("48x48"),
                    "self_url": user_data.get("self"),
                })

            # RDBMS 벌크 저장 (저장 후 카운트)
            if users_data:
                saved_count = await run_in_threadpool(
                    _upsert_users_sync,
                )
                results["synced"] = saved_count
                logger.info(f"Saved {saved_count} users to RDBMS")
            else:
                logger.warning("No valid users to save (all missing accountId)")

        except JiraApiError as e:
            logger.error(f"Failed to sync users (API error): {e}")
            results["errors"] += 1
        except Exception as e:
            logger.error(f"Failed to sync users (DB error): {e}", exc_info=True)
            results["errors"] += 1

        logger.info(f"User sync completed: {results}")
        return results

    async def build_record_gap_report(
        self,
        *,
        project_key: str,
        sync_days: int | None = None,
        sync_from_dt: datetime | None = None,
    ) -> JiraRecordGapReport:
        self._ensure_initialized()
        since = sync_from_dt or self._resolve_sync_from_dt(sync_days)

        expected_issue_ids, expected_epic_ids = await self._collect_project_record_ids(
            project_key=project_key,
            since=since,
        )
        stored_issue_doc_ids = await self.repository.list_jira_record_ids(
            project_key=project_key,
            entity_type="issue",
            since=since,
        )
        stored_epic_doc_ids = await self.repository.list_jira_record_ids(
            project_key=project_key,
            entity_type="epic",
            since=since,
        )

        issue_item = self._build_gap_item(
            record_type="issue",
            expected_ids=expected_issue_ids,
            stored_ids=self._extract_record_ids_from_doc_ids(stored_issue_doc_ids),
            stored_count=len(stored_issue_doc_ids),
        )
        epic_item = self._build_gap_item(
            record_type="epic",
            expected_ids=expected_epic_ids,
            stored_ids=self._extract_record_ids_from_doc_ids(stored_epic_doc_ids),
            stored_count=len(stored_epic_doc_ids),
        )

        return JiraRecordGapReport(records=[issue_item, epic_item])

    async def retry_missing_records(
        self,
        *,
        project_key: str,
        sync_days: int | None = None,
        sync_from_dt: datetime | None = None,
        issue_ids: list[str] | None = None,
        epic_ids: list[str] | None = None,
    ) -> JiraRecordRetryResult:
        self._ensure_initialized()
        requested_issue_ids = list(issue_ids or [])
        requested_epic_ids = list(epic_ids or [])
        result_items: list[JiraRecordRetryItem] = []

        if requested_issue_ids or requested_epic_ids:
            await self._prepare_project_context(project_key)

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

        return JiraRecordRetryResult(records=result_items)

    async def delete_issue_documents(
            self,
            issue_keys: list[str],
    ) -> int:
        self._ensure_initialized()

        unique_issue_keys = sorted({key for key in issue_keys if key})
        if not unique_issue_keys:
            return 0
        
        doc_ids:list[str] = []
        for issue_key in unique_issue_keys:
            doc_ids.append(f"jira:issue:{issue_key}")
            doc_ids.append(f"jira:epic:{issue_key}")

        await self.repository.delete_documents(doc_ids)

        logger.info(
            f"[JIRA][FLUSH] Deleted documents from issue_deleted events: "
            f"cloud_id={self.cloud_id}, issue_count={len(unique_issue_keys)}, doc_count={len(doc_ids)}"
        )
        return len(doc_ids)

    async def incremental_sync(
        self,
        *,
        project_key: str,
        record_id: str,
        event_kind: str,
        since: datetime | None,
        audit_context: SyncAuditContext | None = None,
    ) -> dict[str, int | bool]:
        normalized_event_kind = event_kind.strip().lower()
        if normalized_event_kind == "deleted":
            deleted = await self.delete_issue_documents([record_id])
            return {
                "synced": deleted,
                "errors": 0,
                "skipped": False,
            }

        result = await self._sync_project_issues(
            project_key=project_key,
            since=since,
            audit_context=audit_context,
        )
        return {
            "synced": int(result.get("issues", 0)) + int(result.get("epics", 0)),
            "errors": int(result.get("errors", 0)),
            "skipped": False,
        }
            
