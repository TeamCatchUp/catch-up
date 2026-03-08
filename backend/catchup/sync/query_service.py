from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import select

from catchup.connectors.slack.factory import create_slack_ingestion_service
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

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class SyncJobSnapshotResult:
    job_id: str
    connector: SyncConnector
    sync_type: str
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
    metrics: dict[str, int] = field(default_factory=dict)
    last_error: str | None = None


@dataclass(slots=True, frozen=True)
class SyncStreamEventResult:
    connector: SyncConnector
    job_id: str
    scope_id: str
    event_type: str
    sequence: int
    timestamp: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class SyncTargetResult:
    target_id: str
    display_name: str
    target_type: str
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
    sync_type: str
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

    def _event_status_to_stream_type(self, status: SyncEventStatus) -> str:
        if status == SyncEventStatus.PENDING:
            return "target_queued"
        if status == SyncEventStatus.IN_PROGRESS:
            return "target_started"
        if status == SyncEventStatus.RETRYING:
            return "target_requeued"
        if status == SyncEventStatus.SUCCESS:
            return "target_completed"
        return "target_failed"

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

    def _is_terminal_job_status(self, status_value: SyncJobStatus | None) -> bool:
        return status_value in {SyncJobStatus.SUCCESS, SyncJobStatus.FAILED}

    def _serialize_stream_event(self, result: SyncStreamEventResult) -> str:
        payload = {
            "connector": result.connector.value,
            "job_id": result.job_id,
            "scope_id": result.scope_id,
            "event_type": result.event_type,
            "sequence": result.sequence,
            "timestamp": result.timestamp,
            "payload": result.payload,
        }
        return json.dumps(payload, ensure_ascii=False)

    def _serialize_heartbeat(self, snapshot: SyncJobSnapshotResult) -> str:
        payload = {
            "connector": snapshot.connector.value,
            "job_id": snapshot.job_id,
            "scope_id": snapshot.scope_id,
            "event_type": "heartbeat",
            "sequence": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {"status": str(snapshot.status)},
        }
        return json.dumps(payload, ensure_ascii=False)

    def get_job_snapshot(self, job_id: str) -> SyncJobSnapshotResult | None:
        # DB에서 job + events를 읽어 snapshot으로 변환
        with SessionLocal() as db:
            job = get_job(db, job_id)
            if job is None:
                return None

            events = list_events_by_job(db, job_id=job_id, limit=100000)
            counts = self._summarize_events(events)

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

    def list_job_stream_events(
        self,
        job_id: str,
    ) -> tuple[SyncJobStatus | None, list[SyncStreamEventResult]]:
        # SSE 구성용 이벤트 목록을 sequence 순서로 생성
        with SessionLocal() as db:
            job = get_job(db, job_id)
            if job is None:
                return None, []

            events = list_events_by_job(db, job_id=job_id, limit=100000)
            stream_events: list[SyncStreamEventResult] = []
            sequence = 1

            for event in events:
                stream_events.append(
                    SyncStreamEventResult(
                        connector=job.connector,
                        job_id=job.job_id,
                        scope_id=str(job.scope_id),
                        event_type=self._event_status_to_stream_type(event.status),
                        sequence=sequence,
                        timestamp=self._to_iso(event.updated_at)
                        or datetime.now(timezone.utc).isoformat(),
                        payload={
                            "event_id": event.event_id,
                            "status": str(event.status),
                            "resource_type": event.resource_type,
                            "resource_id": event.resource_id,
                            "attempt": int(event.attempt),
                            "max_attempts": int(event.max_attempts),
                        },
                    )
                )
                sequence += 1

            if job.status in {SyncJobStatus.SUCCESS, SyncJobStatus.FAILED}:
                stream_events.append(
                    SyncStreamEventResult(
                        connector=job.connector,
                        job_id=job.job_id,
                        scope_id=str(job.scope_id),
                        event_type=(
                            "job_completed"
                            if job.status == SyncJobStatus.SUCCESS
                            else "job_failed"
                        ),
                        sequence=sequence,
                        timestamp=self._to_iso(job.succeeded_at or job.failed_at)
                        or datetime.now(timezone.utc).isoformat(),
                        payload={"status": str(job.status)},
                    )
                )

            return job.status, stream_events

    async def stream_job_events_sse(
        self,
        *,
        job_id: str,
        from_sequence: int,
        heartbeat_seconds: int,
    ) -> AsyncGenerator[str, None]:
        """
        SSE 조립을 QueryService에서 수행하여 Router를 thin 계층으로 유지한다.
        """
        next_seq = max(1, from_sequence)
        wait_seconds = max(0, heartbeat_seconds)

        while True:
            snapshot = self.get_job_snapshot(job_id)
            if snapshot is None:
                break

            job_status, stream_events = self.list_job_stream_events(job_id)
            new_items = [item for item in stream_events if item.sequence >= next_seq]
            if new_items:
                for item in new_items:
                    payload = self._serialize_stream_event(item)
                    yield f"data: {payload}\n\n"
                    next_seq = item.sequence + 1

                if self._is_terminal_job_status(job_status):
                    break
                continue

            if self._is_terminal_job_status(job_status):
                break

            yield f"data: {self._serialize_heartbeat(snapshot)}\n\n"
            await asyncio.sleep(wait_seconds)

    async def list_targets(
        self,
        *,
        connector: SyncConnector,
        scope_id: str,
    ) -> SyncTargetsResult:
        # Slack은 API로 실시간 조회한다.
        if connector == SyncConnector.SLACK:
            with SessionLocal() as db:
                slack_service = await create_slack_ingestion_service(db, scope_id)

                targets: list[SyncTargetResult] = []
                cursor: str | None = None

                while True:
                    response = await slack_service.client.list_conversations(
                        types="public_channel,private_channel,mpim,im",
                        cursor=cursor,
                    )

                    for channel in response.get("channels", []):
                        channel_id = channel.get("id")
                        if not channel_id:
                            continue

                        if channel.get("is_im"):
                            channel_kind = "dm"
                        elif channel.get("is_mpim"):
                            channel_kind = "mpim"
                        elif channel.get("is_private"):
                            channel_kind = "private"
                        else:
                            channel_kind = "public"

                        targets.append(
                            SyncTargetResult(
                                target_id=channel_id,
                                display_name=channel.get("name", channel_id),
                                target_type="channel",
                                is_accessible=bool(channel.get("is_member", False)),
                                metadata={
                                    "channel_kind": channel_kind,
                                    "is_private": bool(channel.get("is_private", False)),
                                    "member_count": channel.get("num_members"),
                                },
                            )
                        )

                    cursor = response.get("response_metadata", {}).get("next_cursor")
                    if not cursor:
                        break

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

        # GitHub/Jira/Confluence는 사전 적재된 metadata 테이블에서 조회한다.
        with SessionLocal() as db:
            if connector == SyncConnector.GITHUB:
                try:
                    installation_id = int(scope_id)
                except ValueError as exc:
                    raise ValueError(
                        f"invalid github scope_id (installation_id expected): {scope_id}"
                    ) from exc

                installation = (
                    db.query(GithubInstallation)
                    .filter(GithubInstallation.installation_id == installation_id)
                    .first()
                )
                if installation is None:
                    raise ValueError(f"github installation not found: {scope_id}")

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
            elif connector == SyncConnector.JIRA:
                token = (
                    db.query(AtlassianOAuthToken)
                    .filter(AtlassianOAuthToken.cloud_id == scope_id)
                    .first()
                )
                if token is None:
                    raise ValueError(f"jira cloud is not connected: {scope_id}")

                projects = (
                    db.query(JiraProject)
                    .filter(JiraProject.cloud_id == scope_id)
                    .order_by(JiraProject.project_key.asc())
                    .all()
                )
                targets = [
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
            elif connector == SyncConnector.CONFLUENCE:
                token = (
                    db.query(AtlassianOAuthToken)
                    .filter(AtlassianOAuthToken.cloud_id == scope_id)
                    .first()
                )
                if token is None:
                    raise ValueError(f"confluence cloud is not connected: {scope_id}")

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
            else:
                raise ValueError(f"unsupported connector for target listing: {connector}")

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


_sync_query_service = SyncQueryService()


def get_sync_query_service() -> SyncQueryService:
    return _sync_query_service
