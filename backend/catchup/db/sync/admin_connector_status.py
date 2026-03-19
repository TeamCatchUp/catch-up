from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import DateTime, cast, column, func, literal, select, table, tuple_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from catchup.db.models import SyncConnector, SyncEvent, SyncJob, SyncType

_pg_embedding = table(
    "langchain_pg_embedding",
    column("cmetadata", JSONB),
).alias("e")


@dataclass(slots=True, frozen=True)
class _SyncTargetRow:
    scope_id: str
    target_id: str
    target_name: str
    event_id: str
    sync_status: str
    last_succeeded_at: datetime | None
    last_failed_at: datetime | None


@dataclass(slots=True, frozen=True)
class AdminConnectorTargetRangeRow:
    scope_id: str
    target_id: str
    target_name: str
    event_id: str
    sync_status: str
    last_succeeded_at: datetime | None
    last_failed_at: datetime | None
    oldest_at: datetime | None
    latest_at: datetime | None


def _get_time_fields(connector: SyncConnector) -> tuple[str, ...]:
    if connector == SyncConnector.GITHUB:
        return ("committed_at", "merged_at", "closed_at", "updated_at", "created_at", "synced_at")
    if connector == SyncConnector.JIRA:
        return ("resolved_at", "updated_at", "created_at", "synced_at")
    if connector == SyncConnector.SLACK:
        return ("updated_at", "created_at", "synced_at")
    if connector == SyncConnector.CONFLUENCE:
        return ("updated_at", "created_at", "synced_at")
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
            SyncEvent.event_id.label("event_id"),
            SyncEvent.status.label("sync_status"),
            SyncEvent.succeeded_at.label("last_succeeded_at"),
            SyncEvent.failed_at.label("last_failed_at"),
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
        ranked_targets.c.event_id,
        ranked_targets.c.sync_status,
        ranked_targets.c.last_succeeded_at,
        ranked_targets.c.last_failed_at,
    ).where(ranked_targets.c.row_number == 1)
    rows = db.execute(stmt).all()
    targets = [
        _SyncTargetRow(
            scope_id=str(row.scope_id),
            target_id=str(row.target_id),
            target_name=str(row.target_name),
            event_id=str(row.event_id),
            sync_status=str(row.sync_status),
            last_succeeded_at=row.last_succeeded_at,
            last_failed_at=row.last_failed_at,
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


def _list_github_embedding_ranges(
    db: Session,
    *,
    target_names: list[str],
) -> dict[str, tuple[datetime | None, datetime | None]]:
    if not target_names:
        return {}

    time_fields = _get_time_fields(SyncConnector.GITHUB)
    oldest_at, latest_at = _build_range_aggregates(time_fields)
    target_key = func.lower(
        func.coalesce(
            _pg_embedding.c.cmetadata["full_name"].astext,
            _pg_embedding.c.cmetadata["owner"].astext
            + literal("/")
            + _pg_embedding.c.cmetadata["repo"].astext,
        )
    )
    stmt = (
        select(
            target_key.label("target_key"),
            oldest_at.label("oldest_at"),
            latest_at.label("latest_at"),
        )
        .select_from(_pg_embedding)
        .where(
            _pg_embedding.c.cmetadata["source"].astext == SyncConnector.GITHUB.value,
            target_key.in_([target_name.lower() for target_name in target_names]),
        )
        .group_by(target_key)
    )
    rows = db.execute(stmt).all()
    return {
        str(row.target_key): (row.oldest_at, row.latest_at)
        for row in rows
    }


def _list_jira_embedding_ranges(
    db: Session,
    *,
    target_ids: list[str],
) -> dict[str, tuple[datetime | None, datetime | None]]:
    if not target_ids:
        return {}

    time_fields = _get_time_fields(SyncConnector.JIRA)
    oldest_at, latest_at = _build_range_aggregates(time_fields)
    target_key = _pg_embedding.c.cmetadata["project_key"].astext
    stmt = (
        select(
            target_key.label("target_key"),
            oldest_at.label("oldest_at"),
            latest_at.label("latest_at"),
        )
        .where(
            _pg_embedding.c.cmetadata["source"].astext == SyncConnector.JIRA.value,
            target_key.in_(target_ids),
        )
        .group_by(target_key)
    )
    rows = db.execute(stmt).all()
    return {
        str(row.target_key): (row.oldest_at, row.latest_at)
        for row in rows
    }


def _list_slack_embedding_ranges(
    db: Session,
    *,
    scope_target_pairs: list[tuple[str, str]],
) -> dict[tuple[str, str], tuple[datetime | None, datetime | None]]:
    if not scope_target_pairs:
        return {}

    time_fields = _get_time_fields(SyncConnector.SLACK)
    oldest_at, latest_at = _build_range_aggregates(time_fields)
    scope_key = _pg_embedding.c.cmetadata["team_id"].astext
    target_key = _pg_embedding.c.cmetadata["channel_id"].astext
    stmt = (
        select(
            scope_key.label("scope_key"),
            target_key.label("target_key"),
            oldest_at.label("oldest_at"),
            latest_at.label("latest_at"),
        )
        .where(
            _pg_embedding.c.cmetadata["source"].astext == SyncConnector.SLACK.value,
            tuple_(scope_key, target_key).in_(scope_target_pairs),
        )
        .group_by(scope_key, target_key)
    )
    rows = db.execute(stmt).all()
    return {
        (str(row.scope_key), str(row.target_key)): (row.oldest_at, row.latest_at)
        for row in rows
    }


def _list_confluence_embedding_ranges(
    db: Session,
    *,
    target_ids: list[str],
) -> dict[str, tuple[datetime | None, datetime | None]]:
    if not target_ids:
        return {}

    time_fields = _get_time_fields(SyncConnector.CONFLUENCE)
    oldest_at, latest_at = _build_range_aggregates(time_fields)
    target_key = _pg_embedding.c.cmetadata["space_key"].astext
    stmt = (
        select(
            target_key.label("target_key"),
            oldest_at.label("oldest_at"),
            latest_at.label("latest_at"),
        )
        .where(
            _pg_embedding.c.cmetadata["source"].astext == SyncConnector.CONFLUENCE.value,
            target_key.in_(target_ids),
        )
        .group_by(target_key)
    )
    rows = db.execute(stmt).all()
    return {
        str(row.target_key): (row.oldest_at, row.latest_at)
        for row in rows
    }


def _get_target_range_key(
    connector: SyncConnector,
    *,
    scope_id: str,
    target_id: str,
    target_name: str,
) -> str | tuple[str, str]:
    if connector == SyncConnector.GITHUB:
        return target_name.lower()
    if connector == SyncConnector.JIRA:
        return target_id
    if connector == SyncConnector.SLACK:
        return (scope_id, target_id)
    if connector == SyncConnector.CONFLUENCE:
        return target_id
    raise ValueError(f"unsupported connector: {connector}")


def _list_embedding_ranges_by_target(
    db: Session,
    *,
    connector: SyncConnector,
    targets: list[_SyncTargetRow],
) -> dict[str | tuple[str, str], tuple[datetime | None, datetime | None]]:
    if connector == SyncConnector.GITHUB:
        return _list_github_embedding_ranges(
            db,
            target_names=sorted({target.target_name for target in targets}),
        )
    if connector == SyncConnector.JIRA:
        return _list_jira_embedding_ranges(
            db,
            target_ids=sorted({target.target_id for target in targets}),
        )
    if connector == SyncConnector.SLACK:
        return _list_slack_embedding_ranges(
            db,
            scope_target_pairs=sorted({(target.scope_id, target.target_id) for target in targets}),
        )
    if connector == SyncConnector.CONFLUENCE:
        return _list_confluence_embedding_ranges(
            db,
            target_ids=sorted({target.target_id for target in targets}),
        )
    raise ValueError(f"unsupported connector: {connector}")


def list_admin_connector_target_range_rows(
    db: Session,
    *,
    connector: SyncConnector,
) -> list[AdminConnectorTargetRangeRow]:
    targets = _list_sync_targets(db, connector=connector)
    embedding_ranges = _list_embedding_ranges_by_target(
        db,
        connector=connector,
        targets=targets,
    )
    rows: list[AdminConnectorTargetRangeRow] = []

    for target in targets:
        oldest_at, latest_at = embedding_ranges.get(
            _get_target_range_key(
                connector,
                scope_id=target.scope_id,
                target_id=target.target_id,
                target_name=target.target_name,
            ),
            (None, None),
        )
        rows.append(
            AdminConnectorTargetRangeRow(
                scope_id=target.scope_id,
                target_id=target.target_id,
                target_name=target.target_name,
                event_id=target.event_id,
                sync_status=target.sync_status,
                last_succeeded_at=target.last_succeeded_at,
                last_failed_at=target.last_failed_at,
                oldest_at=oldest_at,
                latest_at=latest_at,
            )
        )

    return rows
