from __future__ import annotations

import asyncio
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
from typing import Any

import structlog
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.connectors.atlassian.token_manager import AtlassianTokenManager
from catchup.connectors.atlassian.token_manager import AtlassianTokenProvider
from catchup.connectors.channel_talk.full_sync_helper import (
    is_verified_channel_talk_document_connection,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    load_channel_talk_connection,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    load_channel_talk_document_connection,
)
from catchup.connectors.channel_talk.full_sync_helper import (
    require_channel_talk_channel_id,
)
from catchup.connectors.channel_talk.full_sync_target_contract import (
    ChannelTalkFullSyncTargetPlan,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord,
)
from catchup.connectors.confluence.metadata_service import ConfluenceMetadataService
from catchup.connectors.github.auth import get_github_app_service
from catchup.connectors.github.client import GitHubApiClient
from catchup.connectors.github.service import _convert_repos_to_dto
from catchup.connectors.jira.client import JiraApiClient
from catchup.connectors.slack.factory import create_slack_metadata_service
from catchup.db.atlassian import oauth_repository as atlassian_oauth_repository
from catchup.db.engine import SessionLocal
from catchup.db.github import domain_repository as github_entities
from catchup.db.github.installation_repository import (
    get_installation_by_installation_id,
)
from catchup.db.jira import domain_repository as jira_entities
from catchup.db.models import AtlassianOAuthToken
from catchup.db.models import SyncConnector
from catchup.db.models import SyncEventStatus
from catchup.db.models import SyncJob
from catchup.db.models import SyncJobStatus
from catchup.db.models import SyncType
from catchup.db.sync import SyncEventSummary
from catchup.db.sync import get_job
from catchup.db.sync import list_events_by_job
from catchup.db.sync import summarize_events_by_job
from catchup.sync.common.schemas import SyncTargetType

logger = structlog.get_logger(__name__)


def _load_github_installation_db(installation_id: int):
    with SessionLocal() as db:
        return get_installation_by_installation_id(db, installation_id)


def _load_jira_token_db(scope_id: str) -> AtlassianOAuthToken | None:
    with SessionLocal() as db:
        return atlassian_oauth_repository.get_token_by_cloud_id(db, scope_id)


def _load_confluence_token_db(scope_id: str) -> AtlassianOAuthToken | None:
    with SessionLocal() as db:
        return (
            db.query(AtlassianOAuthToken)
            .filter(AtlassianOAuthToken.cloud_id == scope_id)
            .first()
        )


def _persist_github_repositories_db(
    installation_id: int,
    repositories: list[Any],
) -> None:
    with SessionLocal() as db:
        try:
            github_entities.sync_repositories_snapshot(
                db,
                installation_id,
                repositories,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise


def _persist_jira_projects_db(
    cloud_id: str,
    projects: list[dict[str, Any]],
) -> None:
    with SessionLocal() as db:
        try:
            jira_entities.sync_projects_snapshot(
                db,
                cloud_id,
                projects,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise


@dataclass(slots=True, frozen=True)
class SyncJobTargetSnapshotResult:
    target_type: SyncTargetType
    target_id: str
    target_name: str
    status: SyncEventStatus


@dataclass(slots=True, frozen=True)
class SyncJobSnapshotResult:
    job_id: str
    connector: SyncConnector
    sync_type: SyncType
    scope_id: str
    status: SyncJobStatus
    created_at: str
    started_at: str | None
    completed_at: str | None
    total_targets: int
    queued_targets: int
    processing_targets: int
    completed_targets: int
    failed_targets: int
    requeued_targets: int
    targets: list[SyncJobTargetSnapshotResult] = field(default_factory=list)
    metrics: dict[str, int] = field(default_factory=dict)
    last_error: str | None = None


@dataclass(slots=True, frozen=True)
class SyncTargetResult:
    target_id: str
    display_name: str
    target_type: SyncTargetType
    is_accessible: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class SyncTargetsResult:
    connector: SyncConnector
    scope_id: str
    total_targets: int
    targets: list[SyncTargetResult] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class SyncScopeStatusResult:
    job_id: str
    connector: SyncConnector
    sync_type: SyncType
    scope_id: str
    status: SyncJobStatus
    requested_at: str
    started_at: str | None
    completed_at: str | None
    total_targets: int
    queued_targets: int
    processing_targets: int
    completed_targets: int
    failed_targets: int
    requeued_targets: int
    metrics: dict[str, int] = field(default_factory=dict)
    last_error: str | None = None


@dataclass(slots=True, frozen=True)
class SyncJobSummaryResult:
    total_targets: int
    queued_targets: int
    processing_targets: int
    completed_targets: int
    failed_targets: int
    requeued_targets: int
    metrics: dict[str, int] = field(default_factory=dict)
    last_error: str | None = None


class SyncQueryService:
    def __init__(self) -> None:
        self._inflight_targets: dict[
            tuple[SyncConnector, str],
            asyncio.Task[SyncTargetsResult],
        ] = {}
        self._inflight_targets_lock = asyncio.Lock()

    def _to_iso(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.astimezone(timezone.utc).isoformat()

    def _summarize_events(self, events) -> dict[str, int]:
        queued_targets = sum(
            1
            for event in events
            if event.status in {SyncEventStatus.PENDING, SyncEventStatus.RETRYING}
        )
        processing_targets = sum(
            1 for event in events if event.status == SyncEventStatus.IN_PROGRESS
        )
        completed_targets = sum(
            1 for event in events if event.status == SyncEventStatus.SUCCESS
        )
        failed_targets = sum(
            1 for event in events if event.status == SyncEventStatus.FAILED
        )

        return {
            "total_targets": len(events),
            "queued_targets": queued_targets,
            "processing_targets": processing_targets,
            "completed_targets": completed_targets,
            "failed_targets": failed_targets,
            "requeued_targets": sum(int(event.attempt) for event in events),
        }

    def _build_metrics(self, events) -> dict[str, int]:
        return {
            "embedding_tokens_used": sum(
                int(event.embedding_tokens_used or 0) for event in events
            ),
            "summary_tokens_used": sum(
                int(event.summary_tokens_used or 0) for event in events
            ),
        }

    def _build_last_error(self, events) -> str | None:
        candidates = [
            event
            for event in events
            if event.status == SyncEventStatus.FAILED
            and (event.last_error or event.publish_error)
        ]
        if not candidates:
            return None

        candidates.sort(
            key=lambda event: event.failed_at or event.updated_at or event.requested_at,
            reverse=True,
        )
        return str(candidates[0].last_error or candidates[0].publish_error)

    def _build_job_summary(self, events) -> SyncJobSummaryResult:
        counts = self._summarize_events(events)
        return SyncJobSummaryResult(
            total_targets=counts["total_targets"],
            queued_targets=counts["queued_targets"],
            processing_targets=counts["processing_targets"],
            completed_targets=counts["completed_targets"],
            failed_targets=counts["failed_targets"],
            requeued_targets=counts["requeued_targets"],
            metrics=self._build_metrics(events),
            last_error=self._build_last_error(events),
        )

    def _to_job_summary_result(self, summary: SyncEventSummary) -> SyncJobSummaryResult:
        return SyncJobSummaryResult(
            total_targets=summary.total_targets,
            queued_targets=summary.queued_targets,
            processing_targets=summary.processing_targets,
            completed_targets=summary.completed_targets,
            failed_targets=summary.failed_targets,
            requeued_targets=summary.requeued_targets,
            metrics={
                "embedding_tokens_used": summary.embedding_tokens_used,
                "summary_tokens_used": summary.summary_tokens_used,
            },
            last_error=summary.last_error,
        )

    def _build_job_targets(
        self,
        events,
    ) -> list[SyncJobTargetSnapshotResult]:
        targets: list[SyncJobTargetSnapshotResult] = []

        for event in events:
            metadata = (
                event.resource_metadata
                if isinstance(event.resource_metadata, dict)
                else {}
            )
            target_id = str(event.resource_id)
            target_name = (
                str(metadata.get("target_name") or target_id).strip() or target_id
            )
            targets.append(
                SyncJobTargetSnapshotResult(
                    target_type=SyncTargetType(event.resource_type),
                    target_id=target_id,
                    target_name=target_name,
                    status=event.status,
                )
            )

        return targets

    def get_job_snapshot(self, job_id: str) -> SyncJobSnapshotResult | None:
        # DB에서 job + events를 읽어 snapshot으로 변환
        with SessionLocal() as db:
            job = get_job(db, job_id)
            if job is None:
                return None

            events = list_events_by_job(db, job_id=job_id, limit=None)
            summary = self._build_job_summary(events)
            targets = self._build_job_targets(events)

            return SyncJobSnapshotResult(
                job_id=job.job_id,
                connector=job.connector,
                sync_type=job.sync_type,
                scope_id=str(job.scope_id),
                status=job.status,
                created_at=self._to_iso(job.created_at) or "",
                started_at=self._to_iso(job.started_at),
                completed_at=self._to_iso(job.succeeded_at or job.failed_at),
                total_targets=summary.total_targets,
                queued_targets=summary.queued_targets,
                processing_targets=summary.processing_targets,
                completed_targets=summary.completed_targets,
                failed_targets=summary.failed_targets,
                requeued_targets=summary.requeued_targets,
                targets=targets,
                metrics=summary.metrics,
                last_error=summary.last_error,
            )

    async def get_job_snapshot_async(
        self,
        job_id: str,
    ) -> SyncJobSnapshotResult | None:
        return await run_in_threadpool(self.get_job_snapshot, job_id)

    def get_scope_latest_full_status(
        self,
        *,
        connector: SyncConnector,
        scope_id: str,
    ) -> SyncScopeStatusResult | None:
        with SessionLocal() as db:
            stmt = (
                select(SyncJob)
                .where(
                    SyncJob.connector == connector,
                    SyncJob.scope_id == scope_id,
                    SyncJob.sync_type == SyncType.FULL,
                )
                .order_by(SyncJob.requested_at.desc())
                .limit(1)
            )
            job = db.execute(stmt).scalar_one_or_none()
            if job is None:
                return None

            summary = self._to_job_summary_result(
                summarize_events_by_job(db, job_id=job.job_id)
            )

            return SyncScopeStatusResult(
                job_id=job.job_id,
                connector=job.connector,
                sync_type=job.sync_type,
                scope_id=str(job.scope_id),
                status=job.status,
                requested_at=self._to_iso(job.requested_at) or "",
                started_at=self._to_iso(job.started_at),
                completed_at=self._to_iso(job.succeeded_at or job.failed_at),
                total_targets=summary.total_targets,
                queued_targets=summary.queued_targets,
                processing_targets=summary.processing_targets,
                completed_targets=summary.completed_targets,
                failed_targets=summary.failed_targets,
                requeued_targets=summary.requeued_targets,
                metrics=summary.metrics,
                last_error=summary.last_error,
            )

    async def get_scope_latest_full_status_async(
        self,
        *,
        connector: SyncConnector,
        scope_id: str,
    ) -> SyncScopeStatusResult | None:
        return await run_in_threadpool(
            self.get_scope_latest_full_status,
            connector=connector,
            scope_id=scope_id,
        )

    def _build_targets_result(
        self,
        *,
        connector: SyncConnector,
        scope_id: str,
        targets: list[SyncTargetResult],
    ) -> SyncTargetsResult:
        # 모든 connector의 target listing 응답을 같은 envelope로 맞춘다.
        # 이 targets 배열이 Full Sync 요청의 입력 후보 목록이 된다.
        logger.info(
            "sync_targets_loaded",
            connector=connector.value,
            scope_id=scope_id,
            total_targets=len(targets),
        )
        return SyncTargetsResult(
            connector=connector,
            scope_id=scope_id,
            total_targets=len(targets),
            targets=targets,
        )

    async def _list_github_targets(
        self,
        *,
        scope_id: str,
    ) -> SyncTargetsResult:
        # GitHub는 scope_id가 installation_id이고 target_id는 repository id다.
        try:
            installation_id = int(scope_id)
        except ValueError as exc:
            raise ValueError(f"github installation not found: {scope_id}") from exc

        installation = await run_in_threadpool(
            _load_github_installation_db,
            installation_id,
        )
        if installation is None:
            raise ValueError(f"github installation not found: {scope_id}")

        access_token = await get_github_app_service().get_installation_access_token(
            installation_id,
        )
        client = GitHubApiClient(access_token)
        repositories = _convert_repos_to_dto(
            await client.list_installation_repos(),
        )
        # listing 시점에 최신 repo snapshot을 저장해 두면 full sync resolver가
        # 사용자가 고른 repository id를 DB row와 빠르게 대조할 수 있다.
        await run_in_threadpool(
            _persist_github_repositories_db,
            installation_id,
            repositories,
        )

        targets = [
            SyncTargetResult(
                target_id=str(repo.repo_id),
                display_name=repo.full_name,
                target_type="repository",
                is_accessible=True,
                metadata={
                    "repository_full_name": repo.full_name,
                    "installation_id": str(installation_id),
                },
            )
            for repo in repositories
        ]
        return self._build_targets_result(
            connector=SyncConnector.GITHUB,
            scope_id=scope_id,
            targets=targets,
        )

    async def _list_jira_targets(
        self,
        *,
        scope_id: str,
    ) -> SyncTargetsResult:
        # Jira는 scope_id가 cloud_id이고 target_id는 project_key다.
        token = await run_in_threadpool(_load_jira_token_db, scope_id)
        if token is None:
            raise ValueError(f"jira cloud is not connected: {scope_id}")

        token_manager = AtlassianTokenManager(
            oauth_client=AtlassianOAuthClient(),
            oauth_repository=atlassian_oauth_repository,
        )
        client = JiraApiClient(
            scope_id,
            AtlassianTokenProvider(token_manager),
        )
        raw_projects = await client.get_all_projects()
        site_url = (token.site_url or "").rstrip("/")

        # API 응답을 target listing과 DB snapshot 양쪽 형태로 동시에 변환한다.
        # Full Sync 요청은 target_id/project_key만 다시 보내면 된다.
        project_rows: list[dict[str, Any]] = []
        targets: list[SyncTargetResult] = []
        for raw_project in raw_projects:
            project_key = str(raw_project.get("key") or "").strip()
            if not project_key:
                continue

            project_id = str(raw_project.get("id") or "")
            project_name = (
                str(raw_project.get("name") or project_key).strip() or project_key
            )
            lead = raw_project.get("lead")
            lead_data = lead if isinstance(lead, dict) else {}

            project_rows.append(
                {
                    "cloud_id": scope_id,
                    "project_key": project_key,
                    "project_id": project_id,
                    "project_name": project_name,
                    "description": raw_project.get("description"),
                    "project_type": raw_project.get("projectTypeKey"),
                    "lead_account_id": lead_data.get("accountId"),
                    "lead_display_name": lead_data.get("displayName"),
                    "url": f"{site_url}/projects/{project_key}" if site_url else None,
                }
            )
            targets.append(
                SyncTargetResult(
                    target_id=project_key,
                    display_name=project_name,
                    target_type="project",
                    is_accessible=True,
                    metadata={
                        "project_key": project_key,
                        "project_id": project_id,
                    },
                )
            )
        targets.sort(key=lambda item: item.target_id)

        await run_in_threadpool(
            _persist_jira_projects_db,
            scope_id,
            project_rows,
        )
        return self._build_targets_result(
            connector=SyncConnector.JIRA,
            scope_id=scope_id,
            targets=targets,
        )

    async def _list_confluence_targets(
        self,
        *,
        scope_id: str,
    ) -> SyncTargetsResult:
        # Confluence는 scope_id가 cloud_id이고 target_id는 space_key다.
        token = await run_in_threadpool(_load_confluence_token_db, scope_id)
        if token is None:
            raise ValueError(f"confluence cloud is not connected: {scope_id}")

        token_manager = AtlassianTokenManager(
            oauth_client=AtlassianOAuthClient(),
            oauth_repository=atlassian_oauth_repository,
        )
        metadata_service = ConfluenceMetadataService(token_manager)
        spaces = await metadata_service.sync_space_snapshot(
            scope_id,
            granted_scopes=set((token.scopes or "").split()),
        )

        # sync_space_snapshot이 DB snapshot까지 갱신하므로 resolver는 이후
        # target_id(space_key)를 저장된 space row와 매칭한다.
        targets = [
            SyncTargetResult(
                target_id=space["space_key"],
                display_name=space["space_name"] or space["space_key"],
                target_type="space",
                is_accessible=True,
                metadata={
                    "space_key": space["space_key"],
                    "space_id": str(space["space_id"]),
                },
            )
            for space in ([] if spaces is None else spaces)
            if space["space_key"]
        ]
        return self._build_targets_result(
            connector=SyncConnector.CONFLUENCE,
            scope_id=scope_id,
            targets=targets,
        )

    async def _list_slack_targets(
        self,
        *,
        scope_id: str,
    ) -> SyncTargetsResult:
        # Slack은 scope_id가 team_id이고 target_id는 channel id다.
        metadata_service = await create_slack_metadata_service(team_id=scope_id)
        channels = await metadata_service.sync_target_channels()

        channels = sorted(channels, key=lambda channel: channel.name)

        targets = [
            SyncTargetResult(
                target_id=channel.id,
                display_name=channel.name or channel.id,
                target_type="channel",
                is_accessible=bool(channel.is_member),
                metadata={
                    "channel_kind": str(channel.channel_type),
                    "is_private": bool(channel.is_private),
                    "is_member": bool(channel.is_member),
                    "member_count": int(channel.member_count),
                },
            )
            for channel in channels
        ]
        return self._build_targets_result(
            connector=SyncConnector.SLACK,
            scope_id=scope_id,
            targets=targets,
        )

    async def _list_channel_talk_targets(
        self,
        *,
        scope_id: str,
    ) -> SyncTargetsResult:
        channel_id = require_channel_talk_channel_id(
            scope_id,
            empty_message="scope_id is required",
        )

        connection_result, document_connection_result = await asyncio.gather(
            run_in_threadpool(
                load_channel_talk_connection,
                channel_id,
            ),
            run_in_threadpool(
                load_channel_talk_document_connection,
                channel_id,
            ),
        )

        connection = self._require_channel_talk_connection(
            connection_result,
            channel_id=channel_id,
        )

        channel_plan = ChannelTalkFullSyncTargetPlan.channel(
            channel_id=connection.channel_id,
            channel_name=connection.channel_name,
        )
        targets = [self._build_channel_talk_target_result(channel_plan)]
        document_target = self._build_optional_document_space_target(
            document_connection_result,
            channel_id=channel_id,
        )
        if document_target is not None:
            targets.append(document_target)

        return self._build_targets_result(
            connector=SyncConnector.CHANNEL_TALK,
            scope_id=channel_id,
            targets=targets,
        )

    @staticmethod
    def _require_channel_talk_connection(
        connection: ChannelTalkCredentialsRecord | None,
        *,
        channel_id: str,
    ) -> ChannelTalkCredentialsRecord:
        if connection is None:
            raise ValueError("channel_talk is not connected for the requested channel")
        if connection.channel_id != channel_id:
            raise ValueError(
                "Stored Channel Talk credentials do not match the requested channel"
            )
        return connection

    @staticmethod
    def _build_channel_talk_target_result(
        plan: ChannelTalkFullSyncTargetPlan,
    ) -> SyncTargetResult:
        return SyncTargetResult(
            target_id=plan.target_id,
            display_name=plan.target_name,
            target_type=SyncTargetType(plan.target_type),
            is_accessible=True,
            metadata=plan.to_metadata(),
        )

    @classmethod
    def _build_optional_document_space_target(
        cls,
        document_connection: ChannelTalkDocumentCredentialsRecord | None,
        *,
        channel_id: str,
    ) -> SyncTargetResult | None:
        if document_connection is None:
            return None
        if not is_verified_channel_talk_document_connection(
            document_connection,
            channel_id=channel_id,
        ):
            logger.info(
                "channel_talk_document_target_skipped",
                channel_id=channel_id,
                document_channel_id=document_connection.channel_id,
                association_status=document_connection.association_status,
            )
            return None
        plan = ChannelTalkFullSyncTargetPlan.document_space(
            channel_id=channel_id,
            space_id=document_connection.space_id,
            space_name=document_connection.space_name,
        )
        return cls._build_channel_talk_target_result(plan)

    async def list_targets(
        self,
        *,
        connector: SyncConnector,
        scope_id: str | None,
    ) -> SyncTargetsResult:

        key = (connector, scope_id or "")

        async with self._inflight_targets_lock:
            task = self._inflight_targets.get(key)
            if task is None:
                task = asyncio.create_task(
                    self._list_targets_realtime(
                        connector=connector,
                        scope_id=scope_id,
                    )
                )
                self._inflight_targets[key] = task

        try:
            return await task
        finally:
            if task.done():
                async with self._inflight_targets_lock:
                    if self._inflight_targets.get(key) is task:
                        self._inflight_targets.pop(key, None)

    async def _list_targets_realtime(
        self,
        *,
        connector: SyncConnector,
        scope_id: str | None,
    ) -> SyncTargetsResult:

        normalized_scope_id = (scope_id or "").strip()
        if not normalized_scope_id:
            raise ValueError("scope_id is required")

        listers = {
            SyncConnector.GITHUB: self._list_github_targets,
            SyncConnector.JIRA: self._list_jira_targets,
            SyncConnector.CONFLUENCE: self._list_confluence_targets,
            SyncConnector.SLACK: self._list_slack_targets,
            SyncConnector.CHANNEL_TALK: self._list_channel_talk_targets,
        }
        lister = listers.get(connector)
        if lister is None:
            raise ValueError(f"unsupported connector for target listing: {connector}")
        return await lister(scope_id=normalized_scope_id)


_sync_query_service = SyncQueryService()


def get_sync_query_service() -> SyncQueryService:
    return _sync_query_service
