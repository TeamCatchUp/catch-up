from __future__ import annotations

from datetime import datetime
from datetime import timezone

from langchain_core.documents import Document

from catchup.connectors.jira.schemas import JiraIssue
from catchup.sync.ingestion.vector_records.jira_issue import JiraEpicMetadata
from catchup.sync.ingestion.vector_records.jira_issue import JiraEpicVectorRecord
from catchup.sync.ingestion.vector_records.jira_issue import JiraIssueData
from catchup.sync.ingestion.vector_records.jira_issue_mapper import (
    JiraIssueV2RecordMapper,
)


class JiraEpicV2RecordMapper(JiraIssueV2RecordMapper):
    """Build v2 vector-store records from parsed Jira Epic data."""

    def to_document(
        self,
        issue: JiraIssue,
        *,
        cloud_id: str,
        content: str,
        synced_at: datetime | None = None,
    ) -> Document:
        return self.to_record(
            issue,
            cloud_id=cloud_id,
            content=content,
            embedding=[],
            synced_at=synced_at,
        ).to_document()

    def to_record(
        self,
        issue: JiraIssue,
        *,
        cloud_id: str,
        content: str,
        embedding: list[float],
        synced_at: datetime | None = None,
    ) -> JiraEpicVectorRecord:
        synced_at = synced_at or datetime.now(timezone.utc)
        parts = self._parts(issue)
        body = "\n\n".join(part.text for part in parts)

        return JiraEpicVectorRecord(
            langchain_id=f"jira:epic:{cloud_id}:{issue.project_key}:{issue.key}",
            content=content,
            embedding=embedding,
            source="jira",
            entity_type="epic",
            record_id=issue.key,
            scope_type="cloud",
            scope_id=cloud_id,
            target_type="project",
            target_id=issue.project_key,
            target_name=issue.project_name or issue.project_key,
            internal_author_id=(
                issue.reporter.catchup_user_id if issue.reporter else None
            ),
            title=issue.summary,
            body=body,
            data=JiraIssueData(parts=parts),
            url=issue.url,
            created_at=issue.created_at,
            updated_at=issue.updated_at,
            synced_at=synced_at,
            jira_epic=JiraEpicMetadata(
                epic_id=issue.id,
                issue_type=issue.issue_type,
                status=issue.status,
                status_category=issue.status_category,
                priority=issue.priority,
                resolution=issue.resolution,
                assignee=self._user_metadata(issue.assignee),
                reporter=self._user_metadata(issue.reporter),
                creator=self._user_metadata(issue.creator),
                resolved_at=issue.resolved_at,
                due_date=issue.due_date,
                parent_key=issue.parent_key,
                parent_name=issue.parent_name,
                subtask_keys=issue.subtask_keys,
                story_points=issue.story_points,
                components=issue.components,
                labels=issue.labels,
                fix_versions=issue.fix_versions,
                affects_versions=issue.affects_versions,
                time_spent_seconds=issue.time_spent_seconds,
            ),
        )
