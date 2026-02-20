"""
Jira 데이터 동기화 서비스

Jira API에서 데이터를 가져와 PGVector에 저장하는 서비스.
JiraApiClient, JiraFieldMapper, JiraTransformer, PGVectorRepository를 조합.

사용법:
    # 초기화
    service = JiraIngestionService(cloud_id, access_token, site_url)
    await service.initialize()

    # 전체 동기화
    await service.full_sync(project_keys=["CATCH", "PROJ"])

    # 증분 동기화
    await service.incremental_sync()
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from langchain_core.documents import Document
from sqlalchemy.orm import Session

from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.connectors.jira.client import (
    JiraApiClient,
    JiraApiError,
    JiraRateLimitError,
)
from catchup.connectors.jira.field_mapper import JiraFieldMapper
from catchup.connectors.jira.transformers import JiraTransformer
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.components.summarizer import SummarizerService, SummarizeRequest, get_summarizer_service
from catchup.configs.config import settings
from catchup.db.models import JiraEntityType, JiraSyncStatus
from catchup.db.jira import domain_repository as jira_entities
from catchup.db.jira import sync_repository as jira_sync

logger = logging.getLogger(__name__)


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
        access_token: str,
        site_url: str,
        enable_summarization: bool = True,
    ):
        """
        JiraIngestionService 초기화

        Args:
            cloud_id: Jira Cloud 인스턴스 ID (JiraOAuthToken에서 조회)
            access_token: OAuth access token
            site_url: Jira 사이트 URL (예: "https://catchup.atlassian.net")
            enable_summarization: 임베딩 전 LLM 요약 활성화 여부
        """
        self.cloud_id = cloud_id
        self.site_url = site_url.rstrip("/")
        self.enable_summarization = enable_summarization

        # 컴포넌트 초기화
        self.client = JiraApiClient(cloud_id, access_token)
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
        await self.repository.initialize()

        self._initialized = True
        logger.info("JiraIngestionService initialized successfully")

    def _ensure_initialized(self) -> None:
        """초기화 확인"""
        if not self._initialized or self.transformer is None:
            raise RuntimeError(
                "JiraIngestionService not initialized. "
                "Call await service.initialize() first."
            )

    async def sync_metadata(
        self,
        db: Session,
        project_keys: list[str] | None = None,
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

        user_results = await self._sync_all_users(db)
        project_results = await self._sync_all_projects(db, project_keys)

        results["users"] = user_results
        results["projects"] = project_results

        if await self.client.is_agile_available():
            sprint_results = await self._sync_all_sprints(db)
            results["sprints"] = sprint_results

        return results

    # ================================================================
    # 전체 동기화 (Full Sync)
    # ================================================================

    async def full_sync(
        self,
        db: Session,
        project_keys: list[str] | None = None,
        sync_days: int | None = None,
    ) -> dict[str, Any]:
        """
        전체 동기화

        툴 연동시 최초 1회 실행
        Users -> Projects -> Sprints(Agile API 가능 시) -> Issues&Epics
        """
        self._ensure_initialized()

        days = sync_days if sync_days is not None else settings.DEFAULT_SYNC_DAYS
        sync_from = datetime.now(timezone.utc) - timedelta(days=days)

        logger.info(
            f"[JIRA][FULL SYNC] Started for cloud_id = {self.cloud_id}"
            f" projects={project_keys or 'all'}"
            f" since={sync_from.isoformat()}"
        )

        results = {
            "issues": {"synced": 0, "errors": 0},
            "epics": {"synced": 0, "errors": 0},
            "projects": {"synced": 0, "errors": 0},
            "sprints": {"synced": 0, "errors": 0},
            "users": {"synced": 0, "errors": 0},
        }

        try:
            user_results = await self._sync_all_users(db)
            results["users"] = user_results

            project_results = await self._sync_all_projects(db, project_keys)
            results["projects"] = project_results

            jira_sync.create_or_update_sync_state(
                db,
                cloud_id=self.cloud_id,
                entity_type=JiraEntityType.PROJECT,
                status = JiraSyncStatus.SUCCESS,
                synced_count = results["projects"]["synced"]
            )

            if await self.client.is_agile_available():
                sprint_results = await self._sync_all_sprints(db)
                results["sprints"] = sprint_results
                jira_sync.create_or_update_sync_state(
                    db,
                    cloud_id = self.cloud_id,
                    entity_type = JiraEntityType.SPRINT,
                    status = JiraSyncStatus.SUCCESS,
                    synced_count=results["sprints"]["synced"],
                )
            else:
                logger.info("[JIRA][FULL SYNC] Sprint Sync Skipped : Agile API Not Avaiable")
            
            issue_results = await self._sync_all_issues(
                db,
                project_keys=project_keys,
                since=sync_from,
            )
            results["issues"]["synced"] = issue_results["issues"]
            results["epics"]["synced"] = issue_results["epics"]
            results["issues"]["errors"] = issue_results["errors"]

            jira_sync.create_or_update_sync_state(
                db = db,
                cloud_id = self.cloud_id,
                entity_type = JiraEntityType.ISSUE,
                status = JiraSyncStatus.SUCCESS,
                synced_count = results["issues"]["synced"],
            )
            jira_sync.create_or_update_sync_state(
                db=db,
                cloud_id=self.cloud_id,
                entity_type=JiraEntityType.EPIC,
                status=JiraSyncStatus.SUCCESS,
                synced_count=results["epics"]["synced"],
            )

            logger.info("[JIRA][FULL SYNC] Completed : {results}")
            return results

        except Exception as e:
            logger.error(f"[JIRA][FULL SYNC] Failed : {e}")
            jira_sync.create_or_update_sync_state(
                db=db,
                cloud_id=self.cloud_id,
                entity_type=JiraEntityType.ISSUE,
                status=JiraSyncStatus.FAILED,
                synced_count=0,
                error=str(e)[:1000],
            )
            jira_sync.create_or_update_sync_state(
                db=db,
                cloud_id=self.cloud_id,
                entity_type=JiraEntityType.EPIC,
                status=JiraSyncStatus.FAILED,
                synced_count=0,
                error=str(e)[:1000],
            )
            raise

    async def _sync_all_issues(
        self,
        db: Session,
        project_keys: list[str] | None = None,
        since: datetime | None = None,
    ) -> dict[str, int]:
        """
        모든 이슈 동기화 (Batch API 사용)

        search_issues API로 배치 조회하여 효율적으로 동기화.
        Epic도 이슈로 조회되지만 별도 entity_type으로 저장.
        RDBMS에서 Project/Sprint 캐시를 로드하여 Document enrichment에 활용.

        Returns:
            {"issues": 150, "epics": 10, "errors": 2}
        """
        self._ensure_initialized()

        # RDBMS에서 캐시 로드 (테이블이 없어도 계속 진행)
        project_cache: dict = {}
        sprint_cache: dict = {}

        try:
            # RDBMS에서 Project 캐시 로드
            if project_keys:
                project_cache = jira_entities.get_projects_by_keys(
                    db, self.cloud_id, project_keys
                )
            else:
                projects = jira_entities.get_projects_by_cloud_id(db, self.cloud_id)
                project_cache = {p.project_key: p for p in projects}

            # RDBMS에서 Sprint 캐시 로드
            sprints = jira_entities.get_sprints_by_cloud_id(db, self.cloud_id)
            sprint_cache = {s.sprint_id: s for s in sprints}

            logger.info(
                f"Loaded caches: {len(project_cache)} projects, {len(sprint_cache)} sprints"
            )
        except Exception as e:
            # 캐시 로드 실패 시 빈 캐시로 진행 (enrichment 없이)
            db.rollback()
            logger.warning(f"Failed to load caches, continuing without enrichment: {e}")

        # Transformer에 캐시 전달
        self.transformer.project_cache = project_cache
        self.transformer.sprint_cache = sprint_cache

        # JQL 구성
        jql_parts = []
        if since:
            since_str = since.strftime("%Y-%m-%d %H:%M")
            jql_parts.append(f'updated >= "{since_str}"')
        if project_keys:
            projects_str = ", ".join(f'"{pk}"' for pk in project_keys)
            jql_parts.append(f"project IN ({projects_str})")

        # 정렬: 최근 업데이트 순
        jql = " AND ".join(jql_parts) if jql_parts else ""
        jql += " ORDER BY updated DESC"
        jql = jql.strip()

        logger.info(f"Syncing issues with JQL: {jql}")

        results = {"issues": 0, "epics": 0, "errors": 0}
        next_page_token: str | None = None
        batch_size = settings.JIRA_SYNC_BATCH_SIZE
        processed_count = 0

        while True:
            try:
                # 배치 조회 (새 /search/jql API 사용 - nextPageToken 기반 페이지네이션)
                response = await self.client.search_issues(
                    jql=jql,
                    fields=None,  # 모든 필드
                    max_results=batch_size,
                    next_page_token=next_page_token,
                )

                issues = response.get("issues", [])
                is_last = response.get("isLast", True)

                if not issues:
                    break

                processed_count += len(issues)
                logger.info(
                    f"Processing {len(issues)} issues (total processed: {processed_count})"
                )

                # 변환 및 저장
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

                        # Epic인지 Issue인지 카운트
                        if doc.metadata.get("entity_type") == "epic":
                            results["epics"] += 1
                        else:
                            results["issues"] += 1

                    except Exception as e:
                        logger.error(
                            f"Failed to transform issue {issue_data.get('key')}: {e}"
                        )
                        results["errors"] += 1

                # PGVector에 Upsert (기존 문서 업데이트, 없으면 추가)
                if documents:
                    # 요약 적용 (summarizer가 활성화된 경우)
                    if self.summarizer:
                        documents = await self._summarize_documents(documents)
                    await self.repository.upsert_documents(documents, doc_ids)

                # 마지막 페이지면 종료
                if is_last:
                    break

                # 다음 페이지 토큰
                next_page_token = response.get("nextPageToken")
                if not next_page_token:
                    break

                # Rate limit 방지 딜레이
                await asyncio.sleep(settings.JIRA_API_RATE_LIMIT_DELAY)

            except JiraRateLimitError as e:
                logger.warning(f"Rate limited, waiting {e.retry_after}s...")
                await asyncio.sleep(e.retry_after)
                continue

        logger.info(f"Issue sync completed: {results}")
        return results

    async def _summarize_documents(
        self,
        documents: list[Document],
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
        summarized = await self.summarizer.summarize_batch(requests)

        # 요약된 텍스트로 교체
        for doc, summary in zip(documents, summarized):
            doc.page_content = summary

        logger.debug(f"Summarized {len(documents)} documents for embedding")
        return documents

    async def _sync_all_projects(
        self,
        db: Session,
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

            # RDBMS 벌크 저장
            if projects_data:
                jira_entities.upsert_projects_bulk(db, projects_data)
                logger.info(f"Saved {len(projects_data)} projects to RDBMS")

        except JiraApiError as e:
            logger.error(f"Failed to get project list (API error): {e}")
            results["errors"] += 1
        except Exception as e:
            # DB 에러 등 발생 시 트랜잭션 롤백
            db.rollback()
            logger.error(f"Failed to sync projects (DB error): {e}")
            results["errors"] += 1

        logger.info(f"Project sync completed: {results}")
        return results

    async def _sync_all_sprints(
        self,
        db: Session,
    ) -> dict[str, int]:
        """
        모든 스프린트 동기화 (RDBMS 저장)

        Args:
            db: SQLAlchemy Session

        Returns:
            {"synced": N, "errors": M}
        """
        self._ensure_initialized()

        results = {"synced": 0, "errors": 0}
        sprints_data: list[dict] = []

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
                jira_entities.upsert_sprints_bulk(db, sprints_data)
                logger.info(f"Saved {len(sprints_data)} sprints to RDBMS")

        except JiraApiError as e:
            logger.error(f"Failed to get boards (API error): {e}")
            results["errors"] += 1
        except Exception as e:
            # DB 에러 등 발생 시 트랜잭션 롤백
            db.rollback()
            logger.error(f"Failed to sync sprints (DB error): {e}")
            results["errors"] += 1

        logger.info(f"Sprint sync completed: {results}")
        return results

    async def _sync_all_users(self, db: Session) -> dict[str, int]:
        """
        모든 사용자 동기화 (RDBMS 저장)

        Jira Cloud의 모든 사용자를 조회하여 RDBMS에 저장.

        Args:
            db: SQLAlchemy Session

        Returns:
            {"synced": N, "errors": M}
        """
        self._ensure_initialized()

        results = {"synced": 0, "errors": 0}
        users_data: list[dict] = []

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
                saved_count = jira_entities.upsert_users_bulk(db, users_data)
                results["synced"] = saved_count
                logger.info(f"Saved {saved_count} users to RDBMS")
            else:
                logger.warning("No valid users to save (all missing accountId)")

        except JiraApiError as e:
            logger.error(f"Failed to sync users (API error): {e}")
            results["errors"] += 1
        except Exception as e:
            # DB 에러 등 발생 시 트랜잭션 롤백
            db.rollback()
            logger.error(f"Failed to sync users (DB error): {e}", exc_info=True)
            results["errors"] += 1

        logger.info(f"User sync completed: {results}")
        return results

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
            

    # ================================================================
    # 증분 동기화 (Incremental Sync)
    # ================================================================

    async def incremental_sync(
        self,
        db: Session,
        since: datetime | None = None,
        project_keys: list[str] | None = None,
        event_types: set[str] | None = None,
    ) -> dict[str, Any]:
        """
        증분 동기화

        마지막 동기화 이후 업데이트된 엔티티만 동기화.

        Args:
            db: SQLAlchemy Session
            since: 기준 시간 (None이면 마지막 성공 동기화 시간 사용)
            project_keys: 동기화 대상 프로젝트 키 목록 (None이면 전체)
            event_types: flush에서 관측된 이벤트 타입 집합 (로깅/추적용)

        Returns:
            동기화 결과 통계
        """
        self._ensure_initialized()

        normalized_event_types = {event for event in (event_types or set()) if event}

        if since is None:
            sync_state = jira_sync.get_sync_state(db, self.cloud_id, JiraEntityType.ISSUE)
            if sync_state and sync_state.last_successful_sync_at:
                since = sync_state.last_successful_sync_at
            else:
                # 동기화 이력 없음 -> 프로젝트 단위 Full Sync
                logger.info(
                    f"[JIRA][INCREMENTAL SYNC] No previous sync state. "
                    f"Running full sync: cloud_id={self.cloud_id}, projects={project_keys or 'all'}"
                )
                full_result = await self.full_sync(db, project_keys=project_keys)
                return {
                    "issues": full_result["issues"]["synced"],
                    "epics": full_result["epics"]["synced"],
                    "errors": full_result["issues"]["errors"] + full_result["epics"]["errors"],
                }
        
        logger.info(
            f"[JIRA][INCREMENTAL SYNC] Started: "
            f"cloud_id={self.cloud_id}, since={since}, projects={project_keys or 'all'}, "
            f"event_types={sorted(normalized_event_types) if normalized_event_types else ['all']}"
        )

        results = {"issues": 0, "epics": 0, "errors": 0}

        try:
            since_str = since.strftime("%Y-%m-%d %H:%M")

            # 프로젝트 범위 + 시점 기반 JQL 구성
            jql_parts = [f'updated >= "{since_str}"']
            if project_keys:
                projects_str = ", ".join(f'"{project_key}"' for project_key in project_keys)
                jql_parts.append(f"project IN ({projects_str})")
            jql = " AND ".join(jql_parts) + " ORDER BY updated DESC"

            next_page_token: str | None = None
            batch_size = settings.JIRA_SYNC_BATCH_SIZE
            processed_count = 0

            while True:
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
                    f"[JIRA][INCREMENTAL SYNC] Processing batch: "
                    f"cloud_id={self.cloud_id}, batch={len(issues)}, total={processed_count}"
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
                            f"[JIRA][INCREMENTAL SYNC] Transform failed: "
                            f"cloud_id={self.cloud_id}, issue_key={issue_data.get('key')}, error={e}"
                        )
                        results["errors"] += 1

                if documents:
                    await self.repository.upsert_documents(documents, doc_ids)

                if is_last:
                    break

                next_page_token = response.get("nextPageToken")
                if not next_page_token:
                    break

                await asyncio.sleep(settings.JIRA_API_RATE_LIMIT_DELAY)

            jira_sync.create_or_update_sync_state(
                db=db,
                cloud_id=self.cloud_id,
                entity_type=JiraEntityType.ISSUE,
                status=JiraSyncStatus.SUCCESS,
                synced_count=results["issues"],
            )
            jira_sync.create_or_update_sync_state(
                db=db,
                cloud_id=self.cloud_id,
                entity_type=JiraEntityType.EPIC,
                status=JiraSyncStatus.SUCCESS,
                synced_count=results["epics"],
            )

            logger.info(f"[JIRA][INCREMENTAL SYNC] Completed: cloud_id={self.cloud_id}, results={results}")
            return results

        except Exception as e:
            logger.error(f"[JIRA][INCREMENTAL SYNC] Failed: cloud_id={self.cloud_id}, error={e}")
            jira_sync.create_or_update_sync_state(
                db=db,
                cloud_id=self.cloud_id,
                entity_type=JiraEntityType.ISSUE,
                status=JiraSyncStatus.FAILED,
                synced_count=0,
                error=str(e)[:1000],
            )
            jira_sync.create_or_update_sync_state(
                db=db,
                cloud_id=self.cloud_id,
                entity_type=JiraEntityType.EPIC,
                status=JiraSyncStatus.FAILED,
                synced_count=0,
                error=str(e)[:1000],
            )
            raise
