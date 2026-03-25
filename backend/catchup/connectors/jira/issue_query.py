"""Jira issue sync에서 공유하는 pure helper 모듈."""

from datetime import datetime
from datetime import timezone
from typing import Any

from catchup.connectors.jira.results import JiraRecordGapItem
from catchup.connectors.jira.transformers import normalize_issue_type
from catchup.sync.common.schemas import TargetSyncResult


def extract_record_ids_from_doc_ids(doc_ids: list[str]) -> list[str]:
    """Document에서 Record ID만 추출"""
    record_ids: list[str] = []
    for doc_id in doc_ids:
        if not doc_id or ":" not in doc_id:
            continue
        record_ids.append(doc_id.rsplit(":", 1)[-1])
    return record_ids


def sort_record_ids(record_ids: set[str]) -> list[str]:
    return sorted(record_ids)


def build_gap_item(
    *,
    record_type: str,
    expected_ids: list[str],
    stored_ids: list[str],
    stored_count: int,
) -> JiraRecordGapItem:
    missing_ids = sorted(set(expected_ids) - set(stored_ids))
    return JiraRecordGapItem(
        record_type=record_type,
        expected_count=len(expected_ids),
        stored_count=stored_count,
        missing_count=len(missing_ids),
        missing_ids=missing_ids,
    )


def classify_record_type(issue_data: dict[str, Any]) -> str:
    issue_type = normalize_issue_type(
        issue_data.get("fields", {}).get("issuetype", {}).get("name", ""),
    )
    return "epic" if issue_type.lower() == "epic" else "issue"


def format_issue_jql_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def build_issue_since_jql(
    *,
    project_key: str,
    since: datetime | None = None,
) -> str:
    jql_parts = [f'project = "{project_key}"']
    if since is not None:
        jql_parts.insert(
            0,
            f'updated >= "{format_issue_jql_datetime(since)}"',
        )
    return " AND ".join(jql_parts) + " ORDER BY updated DESC"


def build_issue_range_jql(
    *,
    project_key: str,
    range_start: datetime,
    range_end: datetime,
) -> str:
    if range_start >= range_end:
        raise ValueError("jira issue range_start must be earlier than range_end")

    jql_parts = [
        f'project = "{project_key}"',
        f'updated >= "{format_issue_jql_datetime(range_start)}"',
        f'updated < "{format_issue_jql_datetime(range_end)}"',
    ]
    return " AND ".join(jql_parts) + " ORDER BY updated DESC"


def build_issue_sync_jql(
    *,
    project_key: str,
    since: datetime | None = None,
    range_start: datetime | None = None,
    range_end: datetime | None = None,
) -> str:
    """Full/Inremental이 공유하는 Issue Sync 진입점"""
    has_range = range_start is not None or range_end is not None
    if has_range:
        if range_start is None or range_end is None:
            raise ValueError("jira issue range_start and range_end must be provided")
        return build_issue_range_jql(
            project_key=project_key,
            range_start=range_start,
            range_end=range_end,
        )

    return build_issue_since_jql(
        project_key=project_key,
        since=since,
    )


def to_target_sync_result(results: dict[str, int]) -> TargetSyncResult:
    issue_synced = int(results.get("issues", 0))
    epic_synced = int(results.get("epics", 0))
    error_count = int(results.get("errors", 0))
    return TargetSyncResult(
        synced_count=issue_synced + epic_synced,
        error_count=error_count,
    )


def build_full_sync_audit_context(
    *,
    project_key: str,
    range_start: datetime,
    range_end: datetime,
    synced_count: int | None = None,
    error_count: int | None = None,
    error: str | None = None,
) -> str:
    parts = [
        f"project_key={project_key}",
        f"range_start={range_start.isoformat()}",
        f"range_end={range_end.isoformat()}",
    ]
    if synced_count is not None:
        parts.append(f"synced_count={synced_count}")
    if error_count is not None:
        parts.append(f"error_count={error_count}")
    if error:
        parts.append(f"error={error}")
    return ",".join(parts)
