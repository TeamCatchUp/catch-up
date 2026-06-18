from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any

from langchain_core.documents import Document

from catchup.connectors.jira.schemas import JiraAttachment
from catchup.connectors.jira.schemas import JiraComment
from catchup.connectors.jira.schemas import JiraInlineAttachment
from catchup.connectors.jira.schemas import JiraIssue
from catchup.connectors.jira.schemas import JiraLinkedIssue
from catchup.connectors.jira.schemas import JiraSprintInfo
from catchup.connectors.jira.schemas import JiraUser
from catchup.sync.ingestion.vector_records.jira_issue import JiraIssueData
from catchup.sync.ingestion.vector_records.jira_issue import JiraIssueDataPart
from catchup.sync.ingestion.vector_records.jira_issue import JiraIssueMetadata
from catchup.sync.ingestion.vector_records.jira_issue import JiraIssueSprintMetadata
from catchup.sync.ingestion.vector_records.jira_issue import JiraIssueUserMetadata
from catchup.sync.ingestion.vector_records.jira_issue import JiraIssueVectorRecord


class JiraIssueV2RecordMapper:
    """Build v2 vector-store records from parsed Jira Issue data."""

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
    ) -> JiraIssueVectorRecord:
        synced_at = synced_at or datetime.now(timezone.utc)
        parts = self._parts(issue)
        body = "\n\n".join(part.text for part in parts)
        internal_author_id = (
            issue.assignee.catchup_user_id if issue.assignee else None
        )

        return JiraIssueVectorRecord(
            langchain_id=f"jira:issue:{cloud_id}:{issue.project_key}:{issue.key}",
            content=content,
            embedding=embedding,
            source="jira",
            entity_type="issue",
            record_id=issue.key,
            scope_type="cloud",
            scope_id=cloud_id,
            target_type="project",
            target_id=issue.project_key,
            target_name=issue.project_name or issue.project_key,
            internal_author_id=internal_author_id,
            title=issue.summary,
            body=body,
            data=JiraIssueData(parts=parts),
            url=issue.url,
            created_at=issue.created_at,
            updated_at=issue.updated_at,
            synced_at=synced_at,
            jira_issue=JiraIssueMetadata(
                issue_id=issue.id,
                type=issue.issue_type,
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
                sprint=self._sprint_metadata(issue.sprint),
                story_points=issue.story_points,
                components=issue.components,
                labels=issue.labels,
                fix_versions=issue.fix_versions,
                affects_versions=issue.affects_versions,
                time_spent_seconds=issue.time_spent_seconds,
            ),
        )

    @classmethod
    def _parts(cls, issue: JiraIssue) -> list[JiraIssueDataPart]:
        part_inputs: list[tuple[str, str | None, dict[str, Any]]] = [
            (
                "issue_description",
                issue.description,
                {
                    "created_at": cls._isoformat(issue.created_at),
                    "updated_at": cls._isoformat(issue.updated_at),
                },
            ),
        ]
        part_inputs.extend(
            (
                "issue_comment",
                comment.body,
                cls._comment_metadata(comment),
            )
            for comment in issue.comments
        )
        part_inputs.extend(
            (
                "linked_issue",
                cls._linked_issue_text(linked_issue),
                cls._linked_issue_metadata(linked_issue),
            )
            for linked_issue in issue.linked_issues
        )
        part_inputs.extend(
            (
                "attachment",
                cls._attachment_text(attachment),
                cls._attachment_metadata(attachment),
            )
            for attachment in issue.attachments
        )
        for comment in issue.comments:
            part_inputs.extend(
                (
                    "inline_attachment",
                    cls._inline_attachment_text(attachment),
                    cls._inline_attachment_metadata(attachment, comment),
                )
                for attachment in comment.inline_attachments
            )
        return [
            part
            for part_type, text, metadata in part_inputs
            if (part := cls._build_part(part_type, text, metadata)) is not None
        ]

    @staticmethod
    def _build_part(
        part_type: str,
        text: str | None,
        metadata: dict[str, Any],
    ) -> JiraIssueDataPart | None:
        normalized = (text or "").strip()
        if not normalized:
            return None
        normalized_metadata = _drop_none(metadata)
        if "comment_id" in metadata:
            normalized_metadata["comment_id"] = metadata["comment_id"]
        return JiraIssueDataPart(
            type=part_type,
            text=normalized,
            metadata=normalized_metadata,
        )

    @classmethod
    def _comment_metadata(cls, comment: JiraComment) -> dict[str, Any]:
        return _drop_none(
            {
                "id": comment.id,
                "author": cls._user_metadata(comment.author_user)
                or cls._user_metadata_from_values(
                    account_id=comment.author_account_id,
                    display_name=comment.author,
                ),
                "created_at": cls._isoformat(comment.created),
                "updated_at": cls._isoformat(comment.updated),
                "visibility": comment.visibility,
                "mentions": [
                    _drop_none(
                        {
                            "account_id": mention.account_id,
                            "display_name": mention.display_name,
                            "text": mention.text,
                        }
                    )
                    for mention in comment.mentions
                ],
                "inline_attachment_count": len(comment.inline_attachments),
            }
        )

    @staticmethod
    def _linked_issue_text(linked_issue: JiraLinkedIssue) -> str:
        parts = [linked_issue.key]
        if linked_issue.summary:
            parts.append(linked_issue.summary)
        if linked_issue.status:
            parts.append(f"Status: {linked_issue.status}")
        return " - ".join(parts)

    @staticmethod
    def _linked_issue_metadata(linked_issue: JiraLinkedIssue) -> dict[str, Any]:
        return _drop_none(
            {
                "id": linked_issue.id,
                "key": linked_issue.key,
                "summary": linked_issue.summary,
                "status": linked_issue.status,
                "issue_type": linked_issue.issue_type,
                "priority": linked_issue.priority,
                "link_type": linked_issue.link_type,
                "direction": linked_issue.direction,
                "url": linked_issue.url,
            }
        )

    @staticmethod
    def _attachment_text(attachment: JiraAttachment) -> str:
        parts = [attachment.filename]
        if attachment.mime_type:
            parts.append(attachment.mime_type)
        return " - ".join(part for part in parts if part)

    @classmethod
    def _attachment_metadata(cls, attachment: JiraAttachment) -> dict[str, Any]:
        metadata = _drop_none(
            {
                "id": attachment.id,
                "filename": attachment.filename,
                "author": cls._user_metadata(attachment.author_user)
                or cls._user_metadata_from_values(
                    account_id=attachment.author_account_id,
                    display_name=attachment.author,
                ),
                "mime_type": attachment.mime_type,
                "url": attachment.url,
                "thumbnail_url": attachment.thumbnail_url,
                "created_at": cls._isoformat(attachment.created),
                "size": attachment.size,
            }
        )
        metadata["comment_id"] = None
        return metadata

    @staticmethod
    def _inline_attachment_text(attachment: JiraInlineAttachment) -> str:
        return (
            attachment.filename
            or attachment.alt
            or attachment.url
            or f"media:{attachment.id}"
        )

    @classmethod
    def _inline_attachment_metadata(
        cls,
        attachment: JiraInlineAttachment,
        comment: JiraComment,
    ) -> dict[str, Any]:
        return _drop_none(
            {
                "id": attachment.id,
                "collection": attachment.collection,
                "media_type": attachment.type,
                "alt": attachment.alt,
                "filename": attachment.filename,
                "url": attachment.url,
                "comment_id": comment.id,
                "comment_author": cls._user_metadata(comment.author_user)
                or cls._user_metadata_from_values(
                    account_id=comment.author_account_id,
                    display_name=comment.author,
                ),
            }
        )

    @staticmethod
    def _user_metadata(user: JiraUser | None) -> JiraIssueUserMetadata | None:
        if user is None:
            return None
        if not any(
            (
                user.account_id,
                user.display_name,
                user.email_address,
                user.avatar_url,
                user.catchup_user_id,
            )
        ):
            return None
        return JiraIssueUserMetadata(
            account_id=user.account_id,
            display_name=user.display_name,
            email_address=user.email_address,
            avatar_url=user.avatar_url,
            catchup_user_id=user.catchup_user_id,
        )

    @staticmethod
    def _user_metadata_from_values(
        *,
        account_id: str | None,
        display_name: str | None,
    ) -> JiraIssueUserMetadata | None:
        if not any((account_id, display_name)):
            return None
        return JiraIssueUserMetadata(
            account_id=account_id,
            display_name=display_name,
        )

    @staticmethod
    def _sprint_metadata(
        sprint: JiraSprintInfo | None,
    ) -> JiraIssueSprintMetadata | None:
        if sprint is None:
            return None
        return JiraIssueSprintMetadata(
            id=sprint.id,
            name=sprint.name,
            state=sprint.state,
        )

    @staticmethod
    def _isoformat(value: datetime | None) -> str | None:
        return value.isoformat() if value else None


def _drop_none(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}
