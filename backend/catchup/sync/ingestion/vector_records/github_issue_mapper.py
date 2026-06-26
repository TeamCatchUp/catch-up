from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any

from langchain_core.documents import Document

from catchup.connectors.github.schemas import GithubIssue
from catchup.connectors.github.schemas import GithubIssueComment
from catchup.connectors.github.schemas import GithubLabel
from catchup.connectors.github.schemas import GithubMilestone
from catchup.connectors.github.schemas import GithubUser
from catchup.sync.ingestion.vector_records.github_issue import GithubIssueData
from catchup.sync.ingestion.vector_records.github_issue import GithubIssueDataPart
from catchup.sync.ingestion.vector_records.github_issue import GithubIssueLabelMetadata
from catchup.sync.ingestion.vector_records.github_issue import GithubIssueMetadata
from catchup.sync.ingestion.vector_records.github_issue import (
    GithubIssueMilestoneMetadata,
)
from catchup.sync.ingestion.vector_records.github_issue import GithubIssueUserMetadata
from catchup.sync.ingestion.vector_records.github_issue import GithubIssueVectorRecord


class GithubIssueV2RecordMapper:
    """Build v2 vector-store records from parsed GitHub Issue data."""

    def to_document(
        self,
        issue: GithubIssue,
        *,
        owner: str,
        repo: str,
        installation_id: int,
        content: str,
        synced_at: datetime | None = None,
    ) -> Document:
        return self.to_record(
            issue,
            owner=owner,
            repo=repo,
            installation_id=installation_id,
            content=content,
            embedding=[],
            synced_at=synced_at,
        ).to_document()

    def to_record(
        self,
        issue: GithubIssue,
        *,
        owner: str,
        repo: str,
        installation_id: int,
        content: str,
        embedding: list[float],
        synced_at: datetime | None = None,
    ) -> GithubIssueVectorRecord:
        full_name = f"{owner}/{repo}"
        record_id = str(issue.number)
        synced_at = synced_at or datetime.now(timezone.utc)
        parts = self._parts(issue)
        body = "\n\n".join(part.text for part in parts)

        return GithubIssueVectorRecord(
            langchain_id=f"github:issue:{full_name}:{record_id}",
            content=content,
            embedding=embedding,
            source="github",
            entity_type="issue",
            record_id=record_id,
            scope_type="installation",
            scope_id=str(installation_id),
            target_type="repository",
            target_id=full_name,
            target_name=full_name,
            internal_author_id=(
                issue.author.catchup_user_id if issue.author else None
            ),
            title=issue.title,
            body=body,
            data=GithubIssueData(parts=parts),
            url=issue.html_url,
            created_at=issue.created_at,
            updated_at=issue.updated_at,
            synced_at=synced_at,
            github_issue=GithubIssueMetadata(
                state=issue.state,
                state_reason=issue.state_reason,
                closed_at=issue.closed_at,
                author=self._user_metadata(issue.author),
                assignees=self._user_metadata_list(issue.assignees),
                labels=[self._label_metadata(label) for label in issue.labels],
                milestone=self._milestone_metadata(issue.milestone),
            ),
        )

    @classmethod
    def _parts(cls, issue: GithubIssue) -> list[GithubIssueDataPart]:
        part_inputs: list[tuple[str, str | None, dict[str, Any]]] = [
            ("issue_body", issue.body, {}),
        ]
        part_inputs.extend(
            ("issue_comment", comment.body, cls._comment_metadata(comment))
            for comment in issue.comments
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
    ) -> GithubIssueDataPart | None:
        normalized = (text or "").strip()
        if not normalized:
            return None
        return GithubIssueDataPart(
            type=part_type,
            text=normalized,
            metadata=_drop_none(metadata),
        )

    @classmethod
    def _comment_metadata(cls, comment: GithubIssueComment) -> dict[str, Any]:
        return _drop_none(
            {
                "id": comment.id,
                "author": cls._user_metadata(comment.author),
                "created_at": cls._isoformat(comment.created_at),
                "updated_at": cls._isoformat(comment.updated_at),
            }
        )

    @staticmethod
    def _user_metadata(user: GithubUser | None) -> GithubIssueUserMetadata | None:
        if user is None:
            return None
        return GithubIssueUserMetadata(
            external_user_id=user.login,
            internal_user_id=user.catchup_user_id,
        )

    @classmethod
    def _user_metadata_list(
        cls,
        users: list[GithubUser],
    ) -> list[GithubIssueUserMetadata]:
        return [metadata for user in users if (metadata := cls._user_metadata(user))]

    @staticmethod
    def _label_metadata(label: GithubLabel) -> GithubIssueLabelMetadata:
        return GithubIssueLabelMetadata(
            name=label.name,
            color=label.color,
            description=label.description,
        )

    @staticmethod
    def _milestone_metadata(
        milestone: GithubMilestone | None,
    ) -> GithubIssueMilestoneMetadata | None:
        if milestone is None:
            return None
        return GithubIssueMilestoneMetadata(
            number=milestone.number,
            title=milestone.title,
            state=milestone.state,
            due_on=milestone.due_on,
        )

    @staticmethod
    def _isoformat(value: datetime | None) -> str | None:
        return value.isoformat() if value else None


def _drop_none(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}
