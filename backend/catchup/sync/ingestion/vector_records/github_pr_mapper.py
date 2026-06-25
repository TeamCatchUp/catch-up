from __future__ import annotations

from datetime import datetime
from datetime import timezone
from itertools import chain
from typing import Any

from langchain_core.documents import Document

from catchup.connectors.github.schemas import GithubIssueComment
from catchup.connectors.github.schemas import GithubLabel
from catchup.connectors.github.schemas import GithubMilestone
from catchup.connectors.github.schemas import GithubPRComment
from catchup.connectors.github.schemas import GithubPRCommitInfo
from catchup.connectors.github.schemas import GithubPRReview
from catchup.connectors.github.schemas import GithubPullRequest
from catchup.connectors.github.schemas import GithubUser
from catchup.sync.ingestion.vector_records.github_pr import GithubPrData
from catchup.sync.ingestion.vector_records.github_pr import GithubPrDataPart
from catchup.sync.ingestion.vector_records.github_pr import GithubPrLabelMetadata
from catchup.sync.ingestion.vector_records.github_pr import GithubPrMetadata
from catchup.sync.ingestion.vector_records.github_pr import GithubPrMilestoneMetadata
from catchup.sync.ingestion.vector_records.github_pr import GithubPrUserMetadata
from catchup.sync.ingestion.vector_records.github_pr import GithubPrVectorRecord


class GithubPrV2RecordMapper:
    """Build v2 vector-store records from parsed GitHub PR data."""

    def to_document(
        self,
        pr: GithubPullRequest,
        *,
        owner: str,
        repo: str,
        installation_id: int,
        content: str,
        synced_at: datetime | None = None,
    ) -> Document:
        return self.to_record(
            pr,
            owner=owner,
            repo=repo,
            installation_id=installation_id,
            content=content,
            embedding=[],
            synced_at=synced_at,
        ).to_document()

    def to_record(
        self,
        pr: GithubPullRequest,
        *,
        owner: str,
        repo: str,
        installation_id: int,
        content: str,
        embedding: list[float],
        synced_at: datetime | None = None,
    ) -> GithubPrVectorRecord:
        full_name = f"{owner}/{repo}"
        record_id = str(pr.number)
        synced_at = synced_at or datetime.now(timezone.utc)
        parts = self._parts(pr)
        body = "\n\n".join(part.text for part in parts)

        return GithubPrVectorRecord(
            langchain_id=f"github:pr:{full_name}:{record_id}",
            content=content,
            embedding=embedding,
            source="github",
            entity_type="pr",
            record_id=record_id,
            scope_type="installation",
            scope_id=str(installation_id),
            target_type="repository",
            target_id=full_name,
            target_name=full_name,
            internal_author_id=pr.author.catchup_user_id if pr.author else None,
            title=pr.title,
            body=body,
            data=GithubPrData(parts=parts),
            url=pr.html_url,
            created_at=pr.created_at,
            updated_at=pr.updated_at,
            synced_at=synced_at,
            github_pr=GithubPrMetadata(
                state="merged" if pr.merged else pr.state,
                merged_at=pr.merged_at,
                closed_at=pr.closed_at,
                base_ref=pr.base_ref,
                head_ref=pr.head_ref,
                is_draft=pr.is_draft,
                review_decision=pr.review_decision,
                changed_files=pr.changed_files,
                additions=pr.additions,
                deletions=pr.deletions,
                author=self._user_metadata(pr.author),
                merged_by=self._user_metadata(pr.merged_by),
                assignees=self._user_metadata_list(pr.assignees),
                requested_reviewers=self._user_metadata_list(pr.reviewers),
                review_authors=self._review_authors(pr),
                labels=[self._label_metadata(label) for label in pr.labels],
                milestone=self._milestone_metadata(pr.milestone),
            ),
        )

    @classmethod
    def _parts(cls, pr: GithubPullRequest) -> list[GithubPrDataPart]:
        part_inputs: list[tuple[str, str | None, dict[str, Any]]] = [
            ("pr_body", pr.body, {}),
        ]
        part_inputs.extend(
            ("commit", commit.message, cls._commit_metadata(commit))
            for commit in pr.commits
        )
        part_inputs.extend(
            ("issue_comment", comment.body, cls._issue_comment_metadata(comment))
            for comment in pr.issue_comments
        )
        part_inputs.extend(
            ("review", review.body, cls._review_metadata(review))
            for review in pr.reviews
        )
        part_inputs.extend(
            ("review_comment", comment.body, cls._review_comment_metadata(comment))
            for comment in pr.comments
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
    ) -> GithubPrDataPart | None:
        normalized = (text or "").strip()
        if not normalized:
            return None
        return GithubPrDataPart(
            type=part_type,
            text=normalized,
            metadata=_drop_none(metadata),
        )

    @classmethod
    def _commit_metadata(cls, commit: GithubPRCommitInfo) -> dict[str, Any]:
        return {
            "oid": commit.sha,
            "author": cls._commit_author_metadata(commit),
            "committed_at": cls._isoformat(commit.committed_at),
        }

    @classmethod
    def _issue_comment_metadata(cls, comment: GithubIssueComment) -> dict[str, Any]:
        return _drop_none(
            {
                "id": comment.id,
                "author": cls._user_metadata(comment.author),
                "created_at": cls._isoformat(comment.created_at),
                "updated_at": cls._isoformat(comment.updated_at),
            }
        )

    @classmethod
    def _review_metadata(cls, review: GithubPRReview) -> dict[str, Any]:
        return _drop_none(
            {
                "id": review.id,
                "state": review.state,
                "author": cls._user_metadata(review.author),
                "submitted_at": cls._isoformat(review.submitted_at),
            }
        )

    @classmethod
    def _review_comment_metadata(cls, comment: GithubPRComment) -> dict[str, Any]:
        return _drop_none(
            {
                "id": comment.id,
                "author": cls._user_metadata(comment.author),
                "path": comment.path,
                "line": comment.line,
                "original_line": comment.original_line,
                "outdated": comment.outdated,
                "created_at": cls._isoformat(comment.created_at),
                "updated_at": cls._isoformat(comment.updated_at),
            }
        )

    @classmethod
    def _commit_author_metadata(
        cls,
        commit: GithubPRCommitInfo,
    ) -> GithubPrUserMetadata | dict[str, Any] | None:
        if commit.author:
            return cls._user_metadata(commit.author)
        if not commit.author_login and not commit.author_name:
            return None
        return _drop_none(
            {
                "login": commit.author_login or commit.author_name,
                "name": commit.author_name,
                "catchup_user_id": None,
            }
        )

    @staticmethod
    def _user_metadata(user: GithubUser | None) -> GithubPrUserMetadata | None:
        if user is None:
            return None
        return GithubPrUserMetadata(
            login=user.login,
            name=user.name,
            email=user.email,
            avatar_url=user.avatar_url,
            type=user.type,
            url=user.html_url,
            catchup_user_id=user.catchup_user_id,
        )

    @classmethod
    def _user_metadata_list(
        cls,
        users: list[GithubUser],
    ) -> list[GithubPrUserMetadata]:
        return [metadata for user in users if (metadata := cls._user_metadata(user))]

    @classmethod
    def _review_authors(cls, pr: GithubPullRequest) -> list[GithubPrUserMetadata]:
        seen: set[str] = set()
        authors: list[GithubPrUserMetadata] = []
        users = chain(
            (review.author for review in pr.reviews),
            (comment.author for comment in pr.comments),
        )
        for user in users:
            metadata = cls._user_metadata(user)
            if metadata is None or metadata.login in seen:
                continue
            seen.add(metadata.login)
            authors.append(metadata)
        return authors

    @staticmethod
    def _label_metadata(label: GithubLabel) -> GithubPrLabelMetadata:
        return GithubPrLabelMetadata(
            name=label.name,
            color=label.color,
            description=label.description,
        )

    @staticmethod
    def _milestone_metadata(
        milestone: GithubMilestone | None,
    ) -> GithubPrMilestoneMetadata | None:
        if milestone is None:
            return None
        return GithubPrMilestoneMetadata(
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
