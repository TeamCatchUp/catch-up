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
from catchup.connectors.confluence.metadata_service import (
    ConfluenceMetadataService,
    ConfluenceMetadataSnapshot,
)
from catchup.connectors.github.factory import create_github_ingestion_service
from catchup.connectors.github.service import GithubIngestionService, GithubMetadataSnapshot
from catchup.connectors.jira.factory import create_jira_ingestion_service
from catchup.connectors.slack.factory import create_slack_metadata_service
from catchup.connectors.slack.metadata_service import (
    SlackMetadataService,
    SlackMetadataSnapshot,
)
from catchup.db.atlassian import oauth_repository as atlassian_oauth_repository
from catchup.db.engine import SessionLocal
from catchup.db.models import (
    AtlassianOAuthToken,
    JiraProject,
    SyncConnector,
    SyncEventStatus,
    SyncJob,
    SyncJobStatus,
    SyncType,
)
from catchup.db.sync import SyncEventSummary, get_job, list_events_by_job, summarize_events_by_job
from catchup.sync.common.exceptions import SyncInternalError
from catchup.sync.common.schemas import SyncTargetType


logger = logging.getLogger(__name__)

def _load_jira_targets_sync(scope_id: str) -> list[SyncTargetResult]:
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


def _load_confluence_token_sync(scope_id: str) -> AtlassianOAuthToken | None:
    with SessionLocal() as session:
        return (
            session.query(AtlassianOAuthToken)
            .filter(AtlassianOAuthToken.cloud_id == scope_id)
            .first()
        )


def _persist_slack_snapshot_sync(
    service: SlackMetadataService,
    snapshot: SlackMetadataSnapshot,
) -> None:
    with SessionLocal() as session:
        try:
            service.persist_snapshot(
                session,
                snapshot,
                auto_commit=False,
            )
            session.commit()
        except Exception:
            session.rollback()
            raise


def _persist_github_snapshot_sync(
    service: GithubIngestionService,
    snapshot: GithubMetadataSnapshot,
) -> None:
    with SessionLocal() as session:
        try:
            service.persist_installation_snapshot(
                session,
                snapshot,
                auto_commit=False,
            )
            session.commit()
        except Exception:
            session.rollback()
            raise


def _persist_confluence_snapshot_sync(
    service: ConfluenceMetadataService,
    cloud_id: str,
    snapshot: ConfluenceMetadataSnapshot,
) -> None:
    with SessionLocal() as session:
        try:
            service.persist_snapshot(
                session,
                cloud_id,
                snapshot,
                auto_commit=False,
            )
            session.commit()
        except Exception:
            session.rollback()
            raise


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
            1
            for event in events
            if event.status == SyncEventStatus.SUCCESS
        )
        failed_targets = sum(
            1
            for event in events
            if event.status == SyncEventStatus.FAILED
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
            if event.status == SyncEventStatus.FAILED and event.publish_error
        ]
        if not candidates:
            return None

        candidates.sort(
            key=lambda event: event.failed_at or event.updated_at or event.requested_at,
            reverse=True,
        )
        return str(candidates[0].publish_error)

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
        scope_id: str,
    ) -> SyncTargetsResult:
        try:
            installation_id = int(scope_id)
        except ValueError as exc:
            raise ValueError(f"github installation not found: {scope_id}") from exc

        service = await create_github_ingestion_service(
            installation_id=installation_id,
        )
        snapshot, _ = await service.collect_installation_metadata(
            raise_on_error=True,
        )
        await run_in_threadpool(
            _persist_github_snapshot_sync,
            service,
            snapshot,
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
            for repo in snapshot.repositories
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

        targets = await run_in_threadpool(_load_jira_targets_sync, scope_id)
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
        token = await run_in_threadpool(_load_confluence_token_sync, scope_id)
        if token is None:
            raise ValueError(f"confluence cloud is not connected: {scope_id}")

        token_manager = AtlassianTokenManager(
            oauth_client=AtlassianOAuthClient(),
            oauth_repository=atlassian_oauth_repository,
        )
        metadata_service = ConfluenceMetadataService(token_manager)
        snapshot = await metadata_service.collect_snapshot(
            scope_id,
            granted_scopes=set((token.scopes or "").split()),
        )
        if snapshot is not None:
            await run_in_threadpool(
                _persist_confluence_snapshot_sync,
                metadata_service,
                scope_id,
                snapshot,
            )

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
            for space in ([] if snapshot is None else snapshot.spaces)
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
        # 리팩토링: query path도 session-free metadata service API를 사용한다.
        metadata_service = await create_slack_metadata_service(team_id=scope_id)
        snapshot, refresh_result = await metadata_service.collect_snapshot(
            raise_on_error=True,
        )
        self._ensure_refresh_succeeded(
            connector=SyncConnector.SLACK,
            scope_id=scope_id,
            result=refresh_result,
            sections=("workspace", "users", "channels"),
        )
        await run_in_threadpool(
            _persist_slack_snapshot_sync,
            metadata_service,
            snapshot,
        )

        channels = sorted(
            snapshot.channels,
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
        if connector == SyncConnector.GITHUB:
            return await self._list_github_targets(scope_id=scope_id)
        if connector == SyncConnector.JIRA:
            return await self._list_jira_targets(scope_id=scope_id)
        if connector == SyncConnector.CONFLUENCE:
            return await self._list_confluence_targets(scope_id=scope_id)
        if connector == SyncConnector.SLACK:
            return await self._list_slack_targets(scope_id=scope_id)

        raise ValueError(f"unsupported connector for target listing: {connector}")


_sync_query_service = SyncQueryService()


def get_sync_query_service() -> SyncQueryService:
    return _sync_query_service
