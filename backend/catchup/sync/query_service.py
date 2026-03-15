from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from catchup.connectors.atlassian.exceptions import AtlassianTokenNotFoundError
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.connectors.atlassian.token_manager import AtlassianTokenManager
from catchup.connectors.confluence.metadata_service import ConfluenceMetadataService
from catchup.connectors.github.factory import create_github_ingestion_service
from catchup.connectors.jira.factory import create_jira_ingestion_service
from catchup.connectors.slack.factory import create_slack_metadata_service
from catchup.db.atlassian import oauth_repository as atlassian_oauth_repository
from catchup.db.engine import SessionLocal
from catchup.db.models import (
    AtlassianOAuthToken,
    ConfluenceSpace,
    GithubInstallation,
    GithubRepository,
    JiraProject,
    SyncConnector,
    SyncEventStatus,
    SyncJob,
    SyncJobStatus,
    SyncType,
)
from catchup.db.sync import get_job, list_events_by_job
from catchup.sync.common.exceptions import SyncInternalError
from catchup.sync.common.schemas import SyncTargetType


logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class SyncJobTargetSnapshotResult:
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
    completed_targets: int
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


class SyncQueryService:
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

    def _build_job_targets(
        self,
        events,
    ) -> list[SyncJobTargetSnapshotResult]:
        targets: list[SyncJobTargetSnapshotResult] = []

        for event in events:
            metadata = (
                event.resource_metadata if isinstance(event.resource_metadata, dict) else {}
            )
            target_id = str(event.resource_id)
            target_name = str(metadata.get("target_name") or target_id).strip() or target_id
            targets.append(
                SyncJobTargetSnapshotResult(
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

            events = list_events_by_job(db, job_id=job_id, limit=100000)
            counts = self._summarize_events(events)
            targets = self._build_job_targets(events)

            return SyncJobSnapshotResult(
                job_id=job.job_id,
                connector=job.connector,
                sync_type=str(job.sync_type),
                scope_id=str(job.scope_id),
                status=job.status,
                created_at=self._to_iso(job.created_at) or "",
                started_at=self._to_iso(job.started_at),
                completed_at=self._to_iso(job.succeeded_at or job.failed_at),
                total_targets=counts["total_targets"],
                completed_targets=counts["completed_targets"],
                targets=targets,
                metrics={
                    "synced_messages": 0,
                    "flushed_events": 0,
                    "dropped_targets": 0,
                    "dropped_events": 0,
                },
                last_error=None,
            )

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

            events = list_events_by_job(db, job_id=job.job_id, limit=100000)
            counts = self._summarize_events(events)

            return SyncScopeStatusResult(
                job_id=job.job_id,
                connector=job.connector,
                sync_type=str(job.sync_type),
                scope_id=str(job.scope_id),
                status=job.status,
                requested_at=self._to_iso(job.requested_at) or "",
                started_at=self._to_iso(job.started_at),
                completed_at=self._to_iso(job.succeeded_at or job.failed_at),
                total_targets=counts["total_targets"],
                queued_targets=counts["queued_targets"],
                processing_targets=counts["processing_targets"],
                completed_targets=counts["completed_targets"],
                failed_targets=counts["failed_targets"],
                requeued_targets=counts["requeued_targets"],
                metrics={
                    "synced_messages": 0,
                    "flushed_events": 0,
                    "dropped_targets": 0,
                    "dropped_events": 0,
                },
                last_error=None,
            )

    def _build_targets_result(
        self,
        *,
        connector: SyncConnector,
        scope_id: str,
        targets: list[SyncTargetResult],
    ) -> SyncTargetsResult:
        logger.info(
            "[SYNC][TARGETS][QUERY] Loaded targets: connector=%s, scope_id=%s, total_targets=%s",
            connector,
            scope_id,
            len(targets),
        )
        return SyncTargetsResult(
            connector=connector,
            scope_id=scope_id,
            total_targets=len(targets),
            targets=targets,
        )

    def _ensure_refresh_succeeded(
        self,
        *,
        connector: SyncConnector,
        scope_id: str,
        result: dict[str, dict[str, int]],
        sections: tuple[str, ...],
    ) -> None:
        failed_sections = [
            section
            for section in sections
            if int(result.get(section, {}).get("errors", 0)) > 0
        ]
        if failed_sections:
            raise SyncInternalError(
                f"{connector.value} target refresh failed",
                metadata={
                    "scope_id": scope_id,
                    "failed_sections": failed_sections,
                },
            )

    async def _list_github_targets(
        self,
        *,
        db,
        scope_id: str,
    ) -> SyncTargetsResult:
        try:
            installation_id = int(scope_id)
        except ValueError as exc:
            raise ValueError(f"github installation not found: {scope_id}") from exc

        installation = (
            db.query(GithubInstallation)
            .filter(GithubInstallation.installation_id == installation_id)
            .first()
        )
        if installation is None:
            raise ValueError(f"github installation not found: {scope_id}")

        service = await create_github_ingestion_service(db, installation_id)
        await service.sync_installation_metadata(
            db,
            auto_commit=False,
            raise_on_error=True,
        )

        repositories = (
            db.query(GithubRepository)
            .filter(GithubRepository.installation_id == installation_id)
            .order_by(GithubRepository.full_name.asc())
            .all()
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
        db,
        scope_id: str,
    ) -> SyncTargetsResult:
        def _load_jira_targets_sync() -> list[SyncTargetResult]:
            with SessionLocal() as session:
                projects = (
                    session.query(JiraProject)
                    .filter(JiraProject.cloud_id == scope_id)
                    .order_by(JiraProject.project_key.asc())
                    .all()
                )

            return [
                SyncTargetResult(
                    target_id=project.project_key,
                    display_name=project.project_name or project.project_key,
                    target_type="project",
                    is_accessible=True,
                    metadata={
                        "project_key": project.project_key,
                        "project_id": str(project.project_id),
                    },
                )
                for project in projects
                if project.project_key
            ]

        try:
            service = await create_jira_ingestion_service(cloud_id=scope_id)
        except SyncInternalError as exc:
            cause = exc.__cause__
            if isinstance(cause, AtlassianTokenNotFoundError):
                raise ValueError(f"jira cloud is not connected: {scope_id}") from exc
            raise

        refresh_result = await service.sync_metadata(
            raise_on_error=True,
        )
        self._ensure_refresh_succeeded(
            connector=SyncConnector.JIRA,
            scope_id=scope_id,
            result=refresh_result,
            sections=("projects",),
        )

        targets = await run_in_threadpool(_load_jira_targets_sync)
        return self._build_targets_result(
            connector=SyncConnector.JIRA,
            scope_id=scope_id,
            targets=targets,
        )

    async def _list_confluence_targets(
        self,
        *,
        db,
        scope_id: str,
    ) -> SyncTargetsResult:
        token = (
            db.query(AtlassianOAuthToken)
            .filter(AtlassianOAuthToken.cloud_id == scope_id)
            .first()
        )
        if token is None:
            raise ValueError(f"confluence cloud is not connected: {scope_id}")

        token_manager = AtlassianTokenManager(
            oauth_client=AtlassianOAuthClient(),
            oauth_repository=atlassian_oauth_repository,
        )
        metadata_service = ConfluenceMetadataService(token_manager)
        await metadata_service.sync_all(
            db,
            scope_id,
            auto_commit=False,
        )

        spaces = (
            db.query(ConfluenceSpace)
            .filter(ConfluenceSpace.cloud_id == scope_id)
            .order_by(ConfluenceSpace.space_key.asc())
            .all()
        )

        targets = [
            SyncTargetResult(
                target_id=space.space_key,
                display_name=space.space_name or space.space_key,
                target_type="space",
                is_accessible=True,
                metadata={
                    "space_key": space.space_key,
                    "space_id": str(space.space_id),
                },
            )
            for space in spaces
            if space.space_key
        ]
        return self._build_targets_result(
            connector=SyncConnector.CONFLUENCE,
            scope_id=scope_id,
            targets=targets,
        )

    async def _list_slack_targets(
        self,
        *,
        db,
        scope_id: str,
    ) -> SyncTargetsResult:
        metadata_service = await create_slack_metadata_service(db, scope_id)
        refresh_result = await metadata_service.sync_metadata(
            db,
            auto_commit=False,
            rollback_on_error=False,
            raise_on_error=True,
        )
        self._ensure_refresh_succeeded(
            connector=SyncConnector.SLACK,
            scope_id=scope_id,
            result=refresh_result,
            sections=("workspace", "users", "channels"),
        )

        channels = sorted(
            metadata_service.last_channels,
            key=lambda channel: channel.name,
        )

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

    async def list_targets(
        self,
        *,
        connector: SyncConnector,
        scope_id: str,
    ) -> SyncTargetsResult:
        with SessionLocal() as db:
            try:
                result: SyncTargetsResult
                if connector == SyncConnector.GITHUB:
                    result = await self._list_github_targets(db=db, scope_id=scope_id)
                elif connector == SyncConnector.JIRA:
                    result = await self._list_jira_targets(db=db, scope_id=scope_id)
                elif connector == SyncConnector.CONFLUENCE:
                    result = await self._list_confluence_targets(
                        db=db,
                        scope_id=scope_id,
                    )
                elif connector == SyncConnector.SLACK:
                    result = await self._list_slack_targets(db=db, scope_id=scope_id)
                else:
                    raise ValueError(f"unsupported connector for target listing: {connector}")

                db.commit()
                return result
            except Exception:
                db.rollback()
                raise


_sync_query_service = SyncQueryService()


def get_sync_query_service() -> SyncQueryService:
    return _sync_query_service
