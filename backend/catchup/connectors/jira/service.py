"""
Jira 데이터 동기화 facade 서비스

외부 호출부가 의존하는 public API를 유지하면서,
실제 실행은 내부 collaborator에 위임한다.
"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone

import structlog

from catchup.audit.enums import AuditEventStatus
from catchup.audit.enums import AuditLevel
from catchup.components.summarizer import SummarizerService
from catchup.components.summarizer import get_summarizer_service
from catchup.components.vector_db.pgvector import PGVectorRepository
from catchup.configs.config import settings
from catchup.connectors.atlassian.token_manager import AtlassianTokenProvider
from catchup.connectors.jira.client import JiraApiClient
from catchup.connectors.jira.client import JiraRateLimitError
from catchup.connectors.jira.context_store import JiraContextStore
from catchup.connectors.jira.field_mapper import JiraFieldMapper
from catchup.connectors.jira.issue_query import build_full_sync_audit_context
from catchup.connectors.jira.issue_query import to_target_sync_result
from catchup.connectors.jira.issue_sync import JiraIssueSyncService
from catchup.connectors.jira.metadata_sync import JiraMetadataSyncService
from catchup.connectors.jira.results import JiraRecordGapReport
from catchup.connectors.jira.results import JiraRecordRetryResult
from catchup.connectors.jira.repair import JiraRepairService
from catchup.connectors.jira.runtime import JiraRuntime
from catchup.connectors.jira.transformers import JiraTransformer
from catchup.events.enums import SyncIngestionEventAction
from catchup.sync.audit import SyncAuditContext
from catchup.sync.audit import emit_sync_ingestion_audit
from catchup.sync.common.schemas import TargetSyncResult

logger = structlog.get_logger()


class JiraIngestionService:
    """Jira connector의 public facade.

    worker, repair service, auth API 같은 외부 호출부는 이 클래스만 사용한다.
    """

    def __init__(
        self,
        repository: PGVectorRepository,
        cloud_id: str,
        token_provider: AtlassianTokenProvider,
        site_url: str,
        enable_summarization: bool = True,
    ):
        self.cloud_id = cloud_id
        self.site_url = site_url.rstrip("/")
        self.enable_summarization = enable_summarization

        self.client = JiraApiClient(cloud_id, token_provider)
        self.field_mapper = JiraFieldMapper(self.client)
        self.transformer: JiraTransformer | None = None
        self.repository = repository
        self.summarizer: SummarizerService | None = None

        self.runtime: JiraRuntime | None = None
        self.context_store: JiraContextStore | None = None
        self.issue_sync: JiraIssueSyncService | None = None
        self.metadata_sync: JiraMetadataSyncService | None = None
        self.repair: JiraRepairService | None = None

        self._initialized = False

    async def initialize(self) -> None:
        """runtime과 하위 collaborator를 한 번만 조립한다."""
        if self._initialized:
            return

        logger.info(
            "jira_ingestion_service_initializing",
            cloud_id=self.cloud_id,
        )

        await self.field_mapper.initialize()
        self.transformer = JiraTransformer(self.field_mapper)

        if self.enable_summarization:
            self.summarizer = get_summarizer_service()
            logger.info(
                "jira_ingestion_service_summarization_enabled",
                cloud_id=self.cloud_id,
            )

        self.repository.ensure_initialized()

        self.runtime = JiraRuntime(
            cloud_id=self.cloud_id,
            site_url=self.site_url,
            client=self.client,
            transformer=self.transformer,
            repository=self.repository,
            summarizer=self.summarizer,
        )
        self.context_store = JiraContextStore(self.runtime)
        self.issue_sync = JiraIssueSyncService(self.runtime, self.context_store)
        self.metadata_sync = JiraMetadataSyncService(self.runtime)
        self.repair = JiraRepairService(self.runtime, self.context_store)

        self._initialized = True
        logger.info(
            "jira_ingestion_service_initialized",
            cloud_id=self.cloud_id,
        )

    def _ensure_initialized(self) -> None:
        if (
            not self._initialized
            or self.transformer is None
            or self.runtime is None
            or self.context_store is None
            or self.issue_sync is None
            or self.metadata_sync is None
            or self.repair is None
        ):
            raise RuntimeError("JiraIngestionService not initialized.")

    def _resolve_sync_from_dt(self, sync_days: int | None) -> datetime:
        days = sync_days if sync_days is not None else settings.DEFAULT_SYNC_DAYS
        return datetime.now(timezone.utc) - timedelta(days=days)

    async def sync_metadata(
        self,
        project_keys: list[str] | None = None,
        *,
        raise_on_error: bool = False,
    ) -> dict[str, dict[str, int]]:
        """Jira metadata refresh를 metadata collaborator에 위임한다."""
        self._ensure_initialized()
        return await self.metadata_sync.sync_metadata(
            project_keys=project_keys,
            raise_on_error=raise_on_error,
        )

    async def sync_issue_range(
        self,
        *,
        project_key: str,
        range_start: datetime,
        range_end: datetime,
        audit_context: SyncAuditContext | None = None,
    ) -> TargetSyncResult:
        """
        시간 분할 기반 Full Sync 진입점.

        실제 fetch/store는 issue_sync가 수행하고,
        여기서는 Full Sync audit emit과 최종 결과 변환만 담당한다.
        """

        self._ensure_initialized()

        if range_start >= range_end:
            raise ValueError("jira issue range_start must be earlier than range_end")

        logger.info(
            "jira_issue_range_sync_started",
            cloud_id=self.cloud_id,
            project_key=project_key,
            range_start=range_start.isoformat(),
            range_end=range_end.isoformat(),
            job_id=audit_context.job_id if audit_context else None,
            task_id=audit_context.task_id if audit_context else None,
        )

        try:
            project_result = await self.issue_sync.sync_issue_range(
                project_key=project_key,
                range_start=range_start,
                range_end=range_end,
                audit_context=audit_context,
            )
        except JiraRateLimitError as exc:
            if audit_context is not None:
                emit_sync_ingestion_audit(
                    action=SyncIngestionEventAction.FULL_SYNC,
                    status=AuditEventStatus.FAIL,
                    audit_context=audit_context,
                    context=build_full_sync_audit_context(
                        project_key=project_key,
                        range_start=range_start,
                        range_end=range_end,
                        error=str(exc),
                    ),
                    level=AuditLevel.WARNING,
                )
            raise
        except Exception as exc:
            if audit_context is not None:
                emit_sync_ingestion_audit(
                    action=SyncIngestionEventAction.FULL_SYNC,
                    status=AuditEventStatus.FAIL,
                    audit_context=audit_context,
                    context=build_full_sync_audit_context(
                        project_key=project_key,
                        range_start=range_start,
                        range_end=range_end,
                        error=str(exc),
                    ),
                    level=AuditLevel.ERROR,
                )
            raise

        result = to_target_sync_result(project_result)
        if result.error_count > 0:
            if audit_context is not None:
                emit_sync_ingestion_audit(
                    action=SyncIngestionEventAction.FULL_SYNC,
                    status=AuditEventStatus.FAIL,
                    audit_context=audit_context,
                    context=build_full_sync_audit_context(
                        project_key=project_key,
                        range_start=range_start,
                        range_end=range_end,
                        synced_count=result.synced_count,
                        error_count=result.error_count,
                        error="jira_issue_range_sync_error_count_detected",
                    ),
                    level=AuditLevel.ERROR,
                )
            raise RuntimeError(
                "jira_issue_range_sync_failed:"
                f" project_key={project_key},"
                f" range_start={range_start.isoformat()},"
                f" range_end={range_end.isoformat()},"
                f" error_count={result.error_count}"
            )

        if audit_context is not None:
            emit_sync_ingestion_audit(
                action=SyncIngestionEventAction.FULL_SYNC,
                status=AuditEventStatus.SUCCESS,
                audit_context=audit_context,
                context=build_full_sync_audit_context(
                    project_key=project_key,
                    range_start=range_start,
                    range_end=range_end,
                    synced_count=result.synced_count,
                    error_count=result.error_count,
                ),
            )
        return result

    async def collect_issue_identifiers(
        self,
        *,
        project_key: str,
        range_start: datetime,
        range_end: datetime,
    ) -> list[str]:
        """collect phase에서 expected_count 계산용 식별자 목록을 수집한다."""
        self._ensure_initialized()
        return await self.issue_sync.collect_issue_identifiers(
            project_key=project_key,
            range_start=range_start,
            range_end=range_end,
        )

    async def build_record_gap_report(
        self,
        *,
        project_key: str,
        sync_days: int | None = None,
        sync_from_dt: datetime | None = None,
    ) -> JiraRecordGapReport:
        """Full Sync 이후 누락 여부를 계산하는 gap report를 만든다."""
        self._ensure_initialized()
        since = sync_from_dt or self._resolve_sync_from_dt(sync_days)
        return await self.repair.build_record_gap_report(
            project_key=project_key,
            since=since,
        )

    async def retry_missing_records(
        self,
        *,
        project_key: str,
        sync_days: int | None = None,
        sync_from_dt: datetime | None = None,
        issue_ids: list[str] | None = None,
        epic_ids: list[str] | None = None,
    ) -> JiraRecordRetryResult:
        """운영/복구 경로에서 missing record 재시도를 수행한다."""
        self._ensure_initialized()
        return await self.repair.retry_missing_records(
            project_key=project_key,
            issue_ids=issue_ids,
            epic_ids=epic_ids,
        )

    async def delete_issue_documents(self, issue_keys: list[str]) -> int:
        """삭제 이벤트나 수동 복구에서 issue/epic 문서를 함께 제거한다."""
        self._ensure_initialized()
        return await self.repair.delete_issue_documents(issue_keys)

    async def incremental_sync(
        self,
        *,
        project_key: str,
        record_id: str,
        event_kind: str,
        since: datetime | None,
        audit_context: SyncAuditContext | None = None,
    ) -> dict[str, int | bool]:
        """Jira webhook 기반 incremental sync를 issue_sync에 위임한다."""
        self._ensure_initialized()
        return await self.issue_sync.incremental_sync(
            project_key=project_key,
            record_id=record_id,
            event_kind=event_kind,
            since=since,
            audit_context=audit_context,
            delete_documents=self.repair.delete_issue_documents,
        )
