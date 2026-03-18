from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging

from sqlalchemy import DateTime, String, cast, column, func, literal, select, table
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from catchup.db.models import GithubRepository, SyncConnector, SyncEvent, SyncJob, SyncType

logger = logging.getLogger(__name__)

_pg_embedding = table(
    "langchain_pg_embedding",
    column("cmetadata", JSONB),
).alias("e")


@dataclass(slots=True, frozen=True)
class _SyncTargetRow:
    scope_id: str
    target_id: str
    target_name: str


@dataclass(slots=True, frozen=True)
class AdminConnectorTargetRangeRow:
    scope_id: str
    target_id: str
    target_name: str
    oldest_at: datetime | None
    latest_at: datetime | None


def _get_time_fields(connector: SyncConnector) -> tuple[str, ...]:
    if connector == SyncConnector.GITHUB:
        return ("created_at", "committed_at", "merged_at", "closed_at", "synced_at")
    if connector == SyncConnector.JIRA:
        return ("created_at", "updated_at", "resolved_at", "synced_at")
    if connector == SyncConnector.SLACK:
        return ("created_at", "updated_at", "synced_at")
    if connector == SyncConnector.CONFLUENCE:
        return ("created_at", "updated_at", "synced_at")
    raise ValueError(f"unsupported connector: {connector}")


def _list_sync_targets(
    db: Session,
    *,
    connector: SyncConnector,
) -> list[_SyncTargetRow]:
    target_name = func.coalesce(
        SyncEvent.resource_metadata["target_name"].astext,
        SyncEvent.resource_id,
    )
    ranked_targets = (
        select(
            SyncJob.scope_id.label("scope_id"),
            SyncEvent.resource_id.label("target_id"),
            target_name.label("target_name"),
            func.row_number()
            .over(
                partition_by=(SyncJob.scope_id, SyncEvent.resource_id),
                order_by=(SyncJob.requested_at.desc(), SyncEvent.created_at.desc()),
            )
            .label("row_number"),
        )
        .join(SyncJob, SyncJob.job_id == SyncEvent.job_id)
        .where(
            SyncEvent.connector == connector,
            SyncJob.connector == connector,
            SyncJob.sync_type == SyncType.FULL,
        )
        .subquery()
    )
    stmt = select(
        ranked_targets.c.scope_id,
        ranked_targets.c.target_id,
        ranked_targets.c.target_name,
    ).where(ranked_targets.c.row_number == 1)
    rows = db.execute(stmt).all()
    targets = [
        _SyncTargetRow(
            scope_id=str(row.scope_id),
            target_id=str(row.target_id),
            target_name=str(row.target_name),
        )
        for row in rows
    ]
    return sorted(
        targets,
        key=lambda item: (item.target_name.lower(), item.scope_id, item.target_id),
    )


def _build_range_aggregates(
    time_fields: tuple[str, ...],
) -> tuple[object, object]:
    time_expr = cast(
        func.coalesce(*(_pg_embedding.c.cmetadata[field].astext for field in time_fields)),
        DateTime(timezone=True),
    )
    return func.min(time_expr), func.max(time_expr)


def _get_embedding_range_by_github_target(
    db: Session,
    *,
    scope_id: str,
    target_id: str,
) -> tuple[datetime | None, datetime | None]:
    time_fields = _get_time_fields(SyncConnector.GITHUB)
    oldest_at, latest_at = _build_range_aggregates(time_fields)
    embedding_full_name = func.coalesce(
        _pg_embedding.c.cmetadata["full_name"].astext,
        _pg_embedding.c.cmetadata["owner"].astext
        + literal("/")
        + _pg_embedding.c.cmetadata["repo"].astext,
    )
    stmt = (
        select(
            oldest_at.label("oldest_at"),
            latest_at.label("latest_at"),
        )
        .select_from(_pg_embedding)
        .join(
            GithubRepository,
            cast(GithubRepository.repo_id, String) == target_id,
        )
        .where(
            cast(GithubRepository.installation_id, String) == scope_id,
            _pg_embedding.c.cmetadata["source"].astext == SyncConnector.GITHUB.value,
            _pg_embedding.c.cmetadata["installation_id"].astext == scope_id,
            embedding_full_name == GithubRepository.full_name,
        )
    )
    row = db.execute(stmt).first()
    return (row.oldest_at, row.latest_at) if row else (None, None)


def _get_embedding_range_by_jira_target(
    db: Session,
    *,
    target_id: str,
) -> tuple[datetime | None, datetime | None]:
    time_fields = _get_time_fields(SyncConnector.JIRA)
    oldest_at, latest_at = _build_range_aggregates(time_fields)
    stmt = select(
        oldest_at.label("oldest_at"),
        latest_at.label("latest_at"),
    ).where(
        _pg_embedding.c.cmetadata["source"].astext == SyncConnector.JIRA.value,
        _pg_embedding.c.cmetadata["project_key"].astext == target_id,
    )
    row = db.execute(stmt).first()
    return (row.oldest_at, row.latest_at) if row else (None, None)


def _get_embedding_range_by_slack_target(
    db: Session,
    *,
    scope_id: str,
    target_id: str,
) -> tuple[datetime | None, datetime | None]:
    time_fields = _get_time_fields(SyncConnector.SLACK)
    oldest_at, latest_at = _build_range_aggregates(time_fields)
    stmt = select(
        oldest_at.label("oldest_at"),
        latest_at.label("latest_at"),
    ).where(
        _pg_embedding.c.cmetadata["source"].astext == SyncConnector.SLACK.value,
        _pg_embedding.c.cmetadata["team_id"].astext == scope_id,
        _pg_embedding.c.cmetadata["channel_id"].astext == target_id,
    )
    row = db.execute(stmt).first()
    return (row.oldest_at, row.latest_at) if row else (None, None)


def _get_embedding_range_by_confluence_target(
    db: Session,
    *,
    target_id: str,
) -> tuple[datetime | None, datetime | None]:
    time_fields = _get_time_fields(SyncConnector.CONFLUENCE)
    oldest_at, latest_at = _build_range_aggregates(time_fields)
    stmt = select(
        oldest_at.label("oldest_at"),
        latest_at.label("latest_at"),
    ).where(
        _pg_embedding.c.cmetadata["source"].astext == SyncConnector.CONFLUENCE.value,
        _pg_embedding.c.cmetadata["space_key"].astext == target_id,
    )
    row = db.execute(stmt).first()
    return (row.oldest_at, row.latest_at) if row else (None, None)


def _get_embedding_range_by_target(
    db: Session,
    *,
    connector: SyncConnector,
    scope_id: str,
    target_id: str,
) -> tuple[datetime | None, datetime | None]:
    try:
        if connector == SyncConnector.GITHUB:
            return _get_embedding_range_by_github_target(
                db,
                scope_id=scope_id,
                target_id=target_id,
            )
        if connector == SyncConnector.JIRA:
            return _get_embedding_range_by_jira_target(
                db,
                target_id=target_id,
            )
        if connector == SyncConnector.SLACK:
            return _get_embedding_range_by_slack_target(
                db,
                scope_id=scope_id,
                target_id=target_id,
            )
        if connector == SyncConnector.CONFLUENCE:
            return _get_embedding_range_by_confluence_target(
                db,
                target_id=target_id,
            )
        raise ValueError(f"unsupported connector: {connector}")
    except Exception as exc:
        logger.warning(
            "[%s][STATUS] Failed to fetch embedding range: scope_id=%s, target_id=%s, error=%s",
            connector.value.upper(),
            scope_id,
            target_id,
            exc,
        )
        return None, None


def list_admin_connector_target_range_rows(
    db: Session,
    *,
    connector: SyncConnector,
) -> list[AdminConnectorTargetRangeRow]:
    targets = _list_sync_targets(db, connector=connector)
    rows: list[AdminConnectorTargetRangeRow] = []

    for target in targets:
        oldest_at, latest_at = _get_embedding_range_by_target(
            db,
            connector=connector,
            scope_id=target.scope_id,
            target_id=target.target_id,
        )
        rows.append(
            AdminConnectorTargetRangeRow(
                scope_id=target.scope_id,
                target_id=target.target_id,
                target_name=target.target_name,
                oldest_at=oldest_at,
                latest_at=latest_at,
            )
        )

    return rows
