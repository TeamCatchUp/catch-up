from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import cast
from sqlalchemy import column
from sqlalchemy import func
from sqlalchemy import literal
from sqlalchemy import select
from sqlalchemy import table
from sqlalchemy import tuple_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from catchup.db.models import ChannelTalkCredentials
from catchup.db.models import ChannelTalkDocumentCredentials
from catchup.db.models import ConfluenceSpace
from catchup.db.models import GithubRepository
from catchup.db.models import JiraProject
from catchup.db.models import SlackChannel
from catchup.db.models import SyncConnector
from catchup.db.models import SyncEvent
from catchup.db.models import SyncEventStatus
from catchup.db.models import SyncJob
from catchup.db.models import SyncType

_pg_embedding = table(
    "langchain_pg_embedding",
    column("cmetadata", JSONB),
).alias("e")

_CHANNEL_TALK_CHANNEL_TARGET_TYPE = "channel"
_CHANNEL_TALK_SPACE_TARGET_TYPE = "space"
_CHANNEL_TALK_TARGET_TYPES = frozenset(
    {
        _CHANNEL_TALK_CHANNEL_TARGET_TYPE,
        _CHANNEL_TALK_SPACE_TARGET_TYPE,
    }
)
_CHANNEL_TALK_DOCUMENT_API_VERIFIED = "api_verified"


@dataclass(slots=True, frozen=True)
class _SyncTargetRow:
    target_type: str
    scope_id: str
    target_id: str
    target_name: str
    event_id: str
    sync_status: str
    last_succeeded_at: datetime | None
    last_failed_at: datetime | None


@dataclass(slots=True, frozen=True)
class AdminConnectorTargetRangeRow:
    target_type: str | None
    scope_id: str
    target_id: str
    target_name: str
    event_id: str
    sync_status: str
    last_succeeded_at: datetime | None
    last_failed_at: datetime | None
    oldest_at: datetime | None
    latest_at: datetime | None


def _sort_targets(targets: list[_SyncTargetRow]) -> list[_SyncTargetRow]:
    return sorted(
        targets,
        key=lambda item: (
            item.target_name.lower(),
            item.target_type,
            item.scope_id,
            item.target_id,
        ),
    )


def _build_pending_target(
    *,
    target_type: object,
    scope_id: object,
    target_id: object,
    target_name: object,
) -> _SyncTargetRow:
    normalized_target_id = str(target_id)
    normalized_target_name = str(target_name or normalized_target_id)
    return _SyncTargetRow(
        target_type=str(target_type),
        scope_id=str(scope_id),
        target_id=normalized_target_id,
        target_name=normalized_target_name,
        event_id="",
        sync_status=SyncEventStatus.PENDING.value,
        last_succeeded_at=None,
        last_failed_at=None,
    )


def _get_time_fields(connector: SyncConnector) -> tuple[str, ...]:
    if connector == SyncConnector.GITHUB:
        return ("committed_at", "merged_at", "closed_at", "updated_at", "created_at", "synced_at")
    if connector == SyncConnector.JIRA:
        return ("resolved_at", "updated_at", "created_at", "synced_at")
    if connector in {
        SyncConnector.SLACK,
        SyncConnector.CONFLUENCE,
        SyncConnector.CHANNEL_TALK,
    }:
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
            SyncEvent.resource_type.label("target_type"),
            SyncEvent.resource_id.label("target_id"),
            target_name.label("target_name"),
            SyncEvent.event_id.label("event_id"),
            SyncEvent.status.label("sync_status"),
            SyncEvent.succeeded_at.label("last_succeeded_at"),
            SyncEvent.failed_at.label("last_failed_at"),
            func.row_number()
            .over(
                partition_by=(
                    SyncJob.scope_id,
                    SyncEvent.resource_type,
                    SyncEvent.resource_id,
                ),
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
        ranked_targets.c.target_type,
        ranked_targets.c.target_id,
        ranked_targets.c.target_name,
        ranked_targets.c.event_id,
        ranked_targets.c.sync_status,
        ranked_targets.c.last_succeeded_at,
        ranked_targets.c.last_failed_at,
    ).where(ranked_targets.c.row_number == 1)
    rows = db.execute(stmt).all()
    targets = []
    for row in rows:
        target_type = str(row.target_type)
        if (
            connector == SyncConnector.CHANNEL_TALK
            and target_type not in _CHANNEL_TALK_TARGET_TYPES
        ):
            continue
        targets.append(
            _SyncTargetRow(
                target_type=target_type,
                scope_id=str(row.scope_id),
                target_id=str(row.target_id),
                target_name=str(row.target_name),
                event_id=str(row.event_id or ""),
                sync_status=str(row.sync_status),
                last_succeeded_at=row.last_succeeded_at,
                last_failed_at=row.last_failed_at,
            )
        )
    return _sort_targets(targets)


def _list_github_connected_targets(db: Session) -> list[_SyncTargetRow]:
    rows = db.execute(
        select(
            GithubRepository.installation_id.label("scope_id"),
            GithubRepository.repo_id.label("target_id"),
            GithubRepository.full_name.label("target_name"),
        ).order_by(GithubRepository.full_name, GithubRepository.installation_id)
    ).all()
    return _sort_targets(
        [
            _build_pending_target(
                target_type="repository",
                scope_id=row.scope_id,
                target_id=row.target_id,
                target_name=row.target_name,
            )
            for row in rows
        ]
    )


def _list_jira_connected_targets(db: Session) -> list[_SyncTargetRow]:
    rows = db.execute(
        select(
            JiraProject.cloud_id.label("scope_id"),
            JiraProject.project_key.label("target_id"),
            JiraProject.project_name.label("target_name"),
        ).order_by(JiraProject.project_name, JiraProject.cloud_id, JiraProject.project_key)
    ).all()
    return _sort_targets(
        [
            _build_pending_target(
                target_type="project",
                scope_id=row.scope_id,
                target_id=row.target_id,
                target_name=row.target_name,
            )
            for row in rows
        ]
    )


def _list_slack_connected_targets(db: Session) -> list[_SyncTargetRow]:
    rows = db.execute(
        select(
            SlackChannel.team_id.label("scope_id"),
            SlackChannel.id.label("target_id"),
            SlackChannel.name.label("target_name"),
        ).order_by(SlackChannel.name, SlackChannel.team_id, SlackChannel.id)
    ).all()
    return _sort_targets(
        [
            _build_pending_target(
                target_type="channel",
                scope_id=row.scope_id,
                target_id=row.target_id,
                target_name=row.target_name,
            )
            for row in rows
        ]
    )


def _list_confluence_connected_targets(db: Session) -> list[_SyncTargetRow]:
    rows = db.execute(
        select(
            ConfluenceSpace.cloud_id.label("scope_id"),
            ConfluenceSpace.space_key.label("target_id"),
            ConfluenceSpace.space_name.label("target_name"),
        ).order_by(
            ConfluenceSpace.space_name,
            ConfluenceSpace.cloud_id,
            ConfluenceSpace.space_key,
        )
    ).all()
    return _sort_targets(
        [
            _build_pending_target(
                target_type="space",
                scope_id=row.scope_id,
                target_id=row.target_id,
                target_name=row.target_name,
            )
            for row in rows
        ]
    )


def _list_channel_talk_connected_targets(db: Session) -> list[_SyncTargetRow]:
    channel_rows = db.execute(
        select(
            ChannelTalkCredentials.channel_id.label("scope_id"),
            ChannelTalkCredentials.channel_id.label("target_id"),
            ChannelTalkCredentials.channel_name.label("target_name"),
        ).order_by(
            ChannelTalkCredentials.channel_name,
            ChannelTalkCredentials.channel_id,
        )
    ).all()
    space_rows = db.execute(
        select(
            ChannelTalkDocumentCredentials.channel_id.label("scope_id"),
            ChannelTalkDocumentCredentials.space_id.label("target_id"),
            ChannelTalkDocumentCredentials.space_name.label("target_name"),
        )
        .join(
            ChannelTalkCredentials,
            ChannelTalkCredentials.channel_id
            == ChannelTalkDocumentCredentials.channel_id,
        )
        .where(
            ChannelTalkDocumentCredentials.association_status
            == _CHANNEL_TALK_DOCUMENT_API_VERIFIED,
        )
        .order_by(
            ChannelTalkDocumentCredentials.space_name,
            ChannelTalkDocumentCredentials.channel_id,
            ChannelTalkDocumentCredentials.space_id,
        )
    ).all()
    targets = [
        _build_pending_target(
            target_type=_CHANNEL_TALK_CHANNEL_TARGET_TYPE,
            scope_id=row.scope_id,
            target_id=row.target_id,
            target_name=row.target_name,
        )
        for row in channel_rows
    ]
    targets.extend(
        _build_pending_target(
            target_type=_CHANNEL_TALK_SPACE_TARGET_TYPE,
            scope_id=row.scope_id,
            target_id=row.target_id,
            target_name=row.target_name,
        )
        for row in space_rows
    )
    return _sort_targets(targets)


def _list_connected_targets(
    db: Session,
    *,
    connector: SyncConnector,
) -> list[_SyncTargetRow]:
    if connector == SyncConnector.GITHUB:
        return _list_github_connected_targets(db)
    if connector == SyncConnector.JIRA:
        return _list_jira_connected_targets(db)
    if connector == SyncConnector.SLACK:
        return _list_slack_connected_targets(db)
    if connector == SyncConnector.CONFLUENCE:
        return _list_confluence_connected_targets(db)
    if connector == SyncConnector.CHANNEL_TALK:
        return _list_channel_talk_connected_targets(db)
    raise ValueError(f"unsupported connector: {connector}")


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


def _list_channel_talk_user_chat_embedding_ranges(
    db: Session,
    *,
    scope_target_pairs: list[tuple[str, str]],
) -> dict[tuple[str, str, str], tuple[datetime | None, datetime | None]]:
    if not scope_target_pairs:
        return {}

    time_fields = _get_time_fields(SyncConnector.CHANNEL_TALK)
    oldest_at, latest_at = _build_range_aggregates(time_fields)
    channel_key = _pg_embedding.c.cmetadata["user_chat_core"]["chat"]["channel_id"].astext
    stmt = (
        select(
            channel_key.label("scope_key"),
            channel_key.label("target_key"),
            oldest_at.label("oldest_at"),
            latest_at.label("latest_at"),
        )
        .where(
            _pg_embedding.c.cmetadata["source"].astext == SyncConnector.CHANNEL_TALK.value,
            _pg_embedding.c.cmetadata["entity_type"].astext == "user_chat",
            tuple_(channel_key, channel_key).in_(scope_target_pairs),
        )
        .group_by(channel_key)
    )
    rows = db.execute(stmt).all()
    return {
        (_CHANNEL_TALK_CHANNEL_TARGET_TYPE, str(row.scope_key), str(row.target_key)): (
            row.oldest_at,
            row.latest_at,
        )
        for row in rows
    }


def _list_channel_talk_document_article_embedding_ranges(
    db: Session,
    *,
    scope_target_pairs: list[tuple[str, str]],
) -> dict[tuple[str, str, str], tuple[datetime | None, datetime | None]]:
    if not scope_target_pairs:
        return {}

    time_fields = _get_time_fields(SyncConnector.CHANNEL_TALK)
    oldest_at, latest_at = _build_range_aggregates(time_fields)
    scope_key = _pg_embedding.c.cmetadata["document_article_core"]["space"]["channel_id"].astext
    target_key = _pg_embedding.c.cmetadata["document_article_core"]["space"]["space_id"].astext
    stmt = (
        select(
            scope_key.label("scope_key"),
            target_key.label("target_key"),
            oldest_at.label("oldest_at"),
            latest_at.label("latest_at"),
        )
        .where(
            _pg_embedding.c.cmetadata["source"].astext == SyncConnector.CHANNEL_TALK.value,
            _pg_embedding.c.cmetadata["entity_type"].astext == "document_article",
            tuple_(scope_key, target_key).in_(scope_target_pairs),
        )
        .group_by(scope_key, target_key)
    )
    rows = db.execute(stmt).all()
    return {
        (_CHANNEL_TALK_SPACE_TARGET_TYPE, str(row.scope_key), str(row.target_key)): (
            row.oldest_at,
            row.latest_at,
        )
        for row in rows
    }


def _list_channel_talk_embedding_ranges(
    db: Session,
    *,
    typed_scope_target_triples: list[tuple[str, str, str]],
) -> dict[tuple[str, str, str], tuple[datetime | None, datetime | None]]:
    user_chat_pairs = sorted(
        {
            (scope_id, target_id)
            for target_type, scope_id, target_id in typed_scope_target_triples
            if target_type == _CHANNEL_TALK_CHANNEL_TARGET_TYPE
        }
    )
    document_article_pairs = sorted(
        {
            (scope_id, target_id)
            for target_type, scope_id, target_id in typed_scope_target_triples
            if target_type == _CHANNEL_TALK_SPACE_TARGET_TYPE
        }
    )
    ranges = _list_channel_talk_user_chat_embedding_ranges(
        db,
        scope_target_pairs=user_chat_pairs,
    )
    ranges.update(
        _list_channel_talk_document_article_embedding_ranges(
            db,
            scope_target_pairs=document_article_pairs,
        )
    )
    return ranges


def _get_target_range_key(
    connector: SyncConnector,
    *,
    target_type: str,
    scope_id: str,
    target_id: str,
    target_name: str,
) -> str | tuple[str, str] | tuple[str, str, str]:
    if connector == SyncConnector.GITHUB:
        return target_name.lower()
    if connector == SyncConnector.JIRA:
        return target_id
    if connector == SyncConnector.SLACK:
        return (scope_id, target_id)
    if connector == SyncConnector.CONFLUENCE:
        return target_id
    if connector == SyncConnector.CHANNEL_TALK:
        return (target_type, scope_id, target_id)
    raise ValueError(f"unsupported connector: {connector}")


def _get_target_identity_key(target: _SyncTargetRow) -> tuple[str, str, str]:
    return (target.target_type, target.scope_id, target.target_id)


def _get_target_merge_key(
    connector: SyncConnector,
    target: _SyncTargetRow,
) -> tuple[str, str] | tuple[str, str, str]:
    if connector == SyncConnector.CHANNEL_TALK:
        return _get_target_identity_key(target)
    return (target.scope_id, target.target_id)


def _merge_targets(
    history_targets: list[_SyncTargetRow],
    connected_targets: list[_SyncTargetRow],
    *,
    connector: SyncConnector,
) -> list[_SyncTargetRow]:
    merged = {
        _get_target_merge_key(connector, target): target
        for target in history_targets
    }

    for target in connected_targets:
        key = _get_target_merge_key(connector, target)
        current = merged.get(key)
        if current is None:
            merged[key] = target
            continue

        if current.target_name == target.target_name or not target.target_name:
            continue

        merged[key] = _SyncTargetRow(
            target_type=current.target_type,
            scope_id=current.scope_id,
            target_id=current.target_id,
            target_name=target.target_name,
            event_id=current.event_id,
            sync_status=current.sync_status,
            last_succeeded_at=current.last_succeeded_at,
            last_failed_at=current.last_failed_at,
        )

    return _sort_targets(list(merged.values()))


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
    if connector == SyncConnector.CHANNEL_TALK:
        return _list_channel_talk_embedding_ranges(
            db,
            typed_scope_target_triples=sorted(
                {
                    (target.target_type, target.scope_id, target.target_id)
                    for target in targets
                }
            ),
        )
    raise ValueError(f"unsupported connector: {connector}")


def list_admin_connector_target_range_rows(
    db: Session,
    *,
    connector: SyncConnector,
) -> list[AdminConnectorTargetRangeRow]:
    history_targets = _list_sync_targets(db, connector=connector)
    connected_targets = _list_connected_targets(db, connector=connector)
    targets = _merge_targets(
        history_targets,
        connected_targets,
        connector=connector,
    )
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
                target_type=target.target_type,
                scope_id=target.scope_id,
                target_id=target.target_id,
                target_name=target.target_name,
            ),
            (None, None),
        )
        rows.append(
            AdminConnectorTargetRangeRow(
                target_type=(
                    target.target_type
                    if connector == SyncConnector.CHANNEL_TALK
                    else None
                ),
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
