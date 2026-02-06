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
from datetime import datetime, timezone
from typing import Any

from langchain_core.documents import Document
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.components.connectors.jira.client import (
    JiraApiClient,
    JiraApiError,
    JiraRateLimitError,
)
from catchup.components.connectors.jira.field_mapper import JiraFieldMapper
from catchup.components.connectors.jira.transformers import JiraTransformer
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.configs.config import settings
from catchup.db.models import JiraEntityType, JiraSyncState, JiraSyncStatus

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
        cloud_id: str,
        access_token: str,
        site_url: str,
    ):
        """
        JiraIngestionService 초기화

        Args:
            cloud_id: Jira Cloud 인스턴스 ID (JiraOAuthToken에서 조회)
            access_token: OAuth access token
            site_url: Jira 사이트 URL (예: "https://catchup.atlassian.net")
        """
        self.cloud_id = cloud_id
        self.site_url = site_url.rstrip("/")

        # 컴포넌트 초기화
        self.client = JiraApiClient(cloud_id, access_token)
        self.field_mapper = JiraFieldMapper(self.client)
        self.transformer: JiraTransformer | None = None
        self.repository = PGVectorRepository()

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

    # ================================================================
    # 전체 동기화 (Full Sync)
    # ================================================================

    async def full_sync(
        self,
        db: Session,
        project_keys: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        전체 동기화

        지정된 프로젝트(또는 전체)의 모든 엔티티를 PGVector에 동기화.

        Args:
            db: SQLAlchemy Session (동기화 상태 저장용)
            project_keys: 동기화할 프로젝트 키 목록 (None이면 전체 프로젝트)

        Returns:
            동기화 결과 통계
            {
                "issues": {"synced": 150, "errors": 2},
                "epics": {"synced": 10, "errors": 0},
                "projects": {"synced": 3, "errors": 0},
                "sprints": {"synced": 12, "errors": 0},
            }
        """
        self._ensure_initialized()

        logger.info(
            f"Starting full sync for cloud_id={self.cloud_id}, "
            f"projects={project_keys or 'all'}"
        )

        results = {
            "issues": {"synced": 0, "errors": 0},
            "epics": {"synced": 0, "errors": 0},
            "projects": {"synced": 0, "errors": 0},
            "sprints": {"synced": 0, "errors": 0},
        }

        try:
            # 1. 프로젝트 동기화
            if project_keys:
                for project_key in project_keys:
                    try:
                        await self._sync_project(project_key)
                        results["projects"]["synced"] += 1
                    except JiraApiError as e:
                        logger.error(f"Failed to sync project {project_key}: {e}")
                        results["projects"]["errors"] += 1

            # 2. 이슈 동기화 (Epic 포함, Epic은 별도 entity_type으로 저장됨)
            issue_results = await self._sync_all_issues(project_keys)
            results["issues"]["synced"] = issue_results["issues"]
            results["epics"]["synced"] = issue_results["epics"]
            results["issues"]["errors"] = issue_results["errors"]

            # 3. 스프린트 동기화 (Agile API 사용 가능한 경우만)
            if await self.client.is_agile_available():
                sprint_results = await self._sync_all_sprints()
                results["sprints"]["synced"] = sprint_results["synced"]
                results["sprints"]["errors"] = sprint_results["errors"]

            # 동기화 상태 업데이트
            self._update_sync_state(
                db,
                JiraEntityType.ISSUE,
                JiraSyncStatus.SUCCESS,
                results["issues"]["synced"],
            )

            logger.info(f"Full sync completed: {results}")
            return results

        except Exception as e:
            logger.error(f"Full sync failed: {e}")
            self._update_sync_state(
                db,
                JiraEntityType.ISSUE,
                JiraSyncStatus.FAILED,
                0,
                str(e),
            )
            raise

    async def _sync_all_issues(
        self,
        project_keys: list[str] | None = None,
    ) -> dict[str, int]:
        """
        모든 이슈 동기화 (Batch API 사용)

        search_issues API로 배치 조회하여 효율적으로 동기화.
        Epic도 이슈로 조회되지만 별도 entity_type으로 저장.

        Returns:
            {"issues": 150, "epics": 10, "errors": 2}
        """
        self._ensure_initialized()

        # JQL 구성
        jql_parts = []
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
                    expand="changelog",  # 쉼표 구분 문자열
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
                        # changelog 추출 (expand로 포함된 경우)
                        changelog = issue_data.get("changelog", {}).get("histories", [])

                        doc = self.transformer.transform_issue(
                            issue_data,
                            self.site_url,
                            changelog=changelog,
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

    async def _sync_project(self, project_key: str) -> None:
        """단일 프로젝트 동기화"""
        self._ensure_initialized()

        logger.info(f"Syncing project: {project_key}")

        project_data = await self.client.get_project(
            project_key,
            expand="description,lead",
        )

        doc = self.transformer.transform_project(project_data, self.site_url)
        await self.repository.upsert_documents([doc], [doc.id])

    async def _sync_all_sprints(self) -> dict[str, int]:
        """모든 스프린트 동기화"""
        self._ensure_initialized()

        results = {"synced": 0, "errors": 0}

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

                    documents: list[Document] = []
                    doc_ids: list[str] = []

                    for sprint_data in sprints:
                        doc = self.transformer.transform_sprint(
                            sprint_data,
                            project_key,
                        )
                        documents.append(doc)
                        doc_ids.append(doc.id)
                        results["synced"] += 1

                    if documents:
                        await self.repository.upsert_documents(documents, doc_ids)

                except JiraApiError as e:
                    logger.error(f"Failed to sync sprints for board {board_id}: {e}")
                    results["errors"] += 1

                await asyncio.sleep(settings.JIRA_API_RATE_LIMIT_DELAY)

        except JiraApiError as e:
            logger.error(f"Failed to get boards: {e}")
            results["errors"] += 1

        logger.info(f"Sprint sync completed: {results}")
        return results

    # ================================================================
    # 증분 동기화 (Incremental Sync)
    # ================================================================

    async def incremental_sync(
        self,
        db: Session,
        since: datetime | None = None,
    ) -> dict[str, Any]:
        """
        증분 동기화

        마지막 동기화 이후 업데이트된 엔티티만 동기화.

        Args:
            db: SQLAlchemy Session
            since: 기준 시간 (None이면 마지막 성공 동기화 시간 사용)

        Returns:
            동기화 결과 통계
        """
        self._ensure_initialized()

        # 마지막 성공 동기화 시간 조회
        if since is None:
            sync_state = self._get_sync_state(db, JiraEntityType.ISSUE)
            if sync_state and sync_state.last_successful_sync_at:
                since = sync_state.last_successful_sync_at
            else:
                # 첫 증분 동기화 → 전체 동기화로 전환
                logger.info("No previous sync found, running full sync instead")
                return await self.full_sync(db)

        logger.info(
            f"Starting incremental sync for cloud_id={self.cloud_id}, since={since}"
        )

        results = {"issues": 0, "epics": 0, "errors": 0}

        try:
            # 업데이트된 이슈만 조회
            since_str = since.strftime("%Y-%m-%d %H:%M")
            jql = f'updated >= "{since_str}" ORDER BY updated DESC'

            next_page_token: str | None = None
            batch_size = settings.JIRA_SYNC_BATCH_SIZE
            processed_count = 0

            while True:
                response = await self.client.search_issues(
                    jql=jql,
                    fields=None,  # 모든 필드
                    expand="changelog",  # 쉼표 구분 문자열
                    max_results=batch_size,
                    next_page_token=next_page_token,
                )

                issues = response.get("issues", [])
                is_last = response.get("isLast", True)

                if not issues:
                    break

                processed_count += len(issues)
                logger.info(
                    f"Incremental sync: processing {len(issues)} issues "
                    f"(total processed: {processed_count})"
                )

                documents: list[Document] = []
                doc_ids: list[str] = []

                for issue_data in issues:
                    try:
                        changelog = issue_data.get("changelog", {}).get("histories", [])
                        doc = self.transformer.transform_issue(
                            issue_data,
                            self.site_url,
                            changelog=changelog,
                        )
                        documents.append(doc)
                        doc_ids.append(doc.id)

                        if doc.metadata.get("entity_type") == "epic":
                            results["epics"] += 1
                        else:
                            results["issues"] += 1

                    except Exception as e:
                        logger.error(
                            f"Failed to transform issue {issue_data.get('key')}: {e}"
                        )
                        results["errors"] += 1

                # Upsert (기존 문서 업데이트)
                if documents:
                    await self.repository.upsert_documents(documents, doc_ids)

                # 마지막 페이지면 종료
                if is_last:
                    break

                # 다음 페이지 토큰
                next_page_token = response.get("nextPageToken")
                if not next_page_token:
                    break

                await asyncio.sleep(settings.JIRA_API_RATE_LIMIT_DELAY)

            # 성공 시 동기화 상태 업데이트
            self._update_sync_state(
                db,
                JiraEntityType.ISSUE,
                JiraSyncStatus.SUCCESS,
                results["issues"] + results["epics"],
            )

            logger.info(f"Incremental sync completed: {results}")
            return results

        except Exception as e:
            logger.error(f"Incremental sync failed: {e}")
            self._update_sync_state(
                db,
                JiraEntityType.ISSUE,
                JiraSyncStatus.FAILED,
                0,
                str(e),
            )
            raise

    # ================================================================
    # 동기화 상태 관리
    # ================================================================

    def _get_sync_state(
        self,
        db: Session,
        entity_type: JiraEntityType,
    ) -> JiraSyncState | None:
        """동기화 상태 조회 (동기 메서드)"""
        stmt = select(JiraSyncState).where(
            JiraSyncState.cloud_id == self.cloud_id,
            JiraSyncState.entity_type == entity_type,
        )
        result = db.execute(stmt)
        return result.scalar_one_or_none()

    def _update_sync_state(
        self,
        db: Session,
        entity_type: JiraEntityType,
        status: JiraSyncStatus,
        synced_count: int,
        error_message: str | None = None,
    ) -> None:
        """동기화 상태 업데이트 (동기 메서드)"""
        sync_state = self._get_sync_state(db, entity_type)

        now = datetime.now(timezone.utc)

        if sync_state is None:
            sync_state = JiraSyncState(
                cloud_id=self.cloud_id,
                entity_type=entity_type,
            )
            db.add(sync_state)

        sync_state.last_sync_status = status
        sync_state.synced_entities = synced_count
        sync_state.last_sync_error = error_message

        if status == JiraSyncStatus.SUCCESS:
            sync_state.last_successful_sync_at = now

        db.commit()

    # ================================================================
    # 검색 API
    # ================================================================

    async def search(
        self,
        query: str,
        k: int = 5,
        entity_type: str | None = None,
        project_key: str | None = None,
    ) -> list[Document]:
        """
        벡터 시맨틱 검색

        Args:
            query: 검색 쿼리 (자연어)
            k: 반환할 결과 수
            entity_type: 엔티티 타입 필터 ("issue", "epic", "project", "sprint")
            project_key: 프로젝트 필터

        Returns:
            관련성 높은 Document 리스트
        """
        self._ensure_initialized()

        # 메타데이터 필터 구성
        filter_dict: dict[str, Any] = {"source": "jira"}

        if entity_type:
            filter_dict["entity_type"] = entity_type

        if project_key:
            filter_dict["project_key"] = project_key

        return await self.repository.search(
            query=query,
            k=k,
            filter=filter_dict if len(filter_dict) > 1 else None,
        )
