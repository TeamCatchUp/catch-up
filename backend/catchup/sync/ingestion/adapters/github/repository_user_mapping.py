from __future__ import annotations

from sqlalchemy.orm import Session

from catchup.connectors.github.schemas import GithubIssue
from catchup.connectors.github.schemas import GithubPullRequest
from catchup.connectors.github.schemas import GithubUser
from catchup.db.models import SourceType
from catchup.db.user_source_mapping import (
    find_premapped_name_by_external_user_identifier,
)
from catchup.db.user_source_mapping import find_premapped_names_by_source_type
from catchup.db.user_source_mapping import find_user_id_by_source_mapping


class GithubRepositoryUserMapper:
    """Apply CatchUp user mappings to parsed GitHub repository records."""

    def __init__(self) -> None:
        self._github_name_cache: dict[str, str | None] = {}
        self._github_user_id_cache: dict[str, str | None] = {}

    def resolve_real_name(self, db: Session, login: str | None) -> str | None:
        if not login:
            return None

        if login in self._github_name_cache:
            return self._github_name_cache[login]

        resolved_name = find_premapped_name_by_external_user_identifier(
            db=db,
            source_type=SourceType.GITHUB,
            external_user_identifier=login,
        )
        self._github_name_cache[login] = resolved_name
        return resolved_name

    def resolve_catchup_user_id(self, db: Session, login: str | None) -> str | None:
        if not login:
            return None

        if login in self._github_user_id_cache:
            return self._github_user_id_cache[login]

        user_id = find_user_id_by_source_mapping(
            db=db,
            source_type=SourceType.GITHUB,
            external_user_identifier=login,
        )
        resolved_id = str(user_id) if user_id is not None else None
        self._github_user_id_cache[login] = resolved_id
        return resolved_id

    def preload_premapped_names(self, db: Session) -> int:
        premapped = find_premapped_names_by_source_type(db, SourceType.GITHUB)
        self._github_name_cache = {
            login: name
            for login, name in premapped.items()
            if login
        }
        return len(self._github_name_cache)

    def apply_user(self, db: Session, user: GithubUser | None) -> GithubUser | None:
        if user is None:
            return None

        mapped_name = self.resolve_real_name(db, user.login)
        catchup_user_id = self.resolve_catchup_user_id(db, user.login)
        updates: dict[str, str] = {}
        if mapped_name:
            updates["name"] = mapped_name
        if catchup_user_id:
            updates["catchup_user_id"] = catchup_user_id
        if not updates:
            return user
        return user.model_copy(update=updates)

    def apply_issue(self, db: Session, issue: GithubIssue) -> GithubIssue:
        comments = [
            comment.model_copy(
                update={"author": self.apply_user(db, comment.author)}
            )
            for comment in issue.comments
        ]
        return issue.model_copy(
            update={
                "author": self.apply_user(db, issue.author),
                "assignees": [
                    self.apply_user(db, assignee)
                    for assignee in issue.assignees
                ],
                "comments": comments,
            }
        )

    def apply_pull_request(
        self,
        db: Session,
        pr: GithubPullRequest,
    ) -> GithubPullRequest:
        issue_comments = [
            comment.model_copy(
                update={"author": self.apply_user(db, comment.author)}
            )
            for comment in pr.issue_comments
        ]
        comments = [
            comment.model_copy(
                update={"author": self.apply_user(db, comment.author)}
            )
            for comment in pr.comments
        ]
        reviews = [
            review.model_copy(
                update={"author": self.apply_user(db, review.author)}
            )
            for review in pr.reviews
        ]

        commits = []
        for commit in pr.commits:
            commit_author_name = self.resolve_real_name(db, commit.author_login)
            commit_author = self.apply_user(db, commit.author)
            updates = {}
            if commit_author_name and commit.author_name != commit_author_name:
                updates["author_name"] = commit_author_name
            if commit_author is not commit.author:
                updates["author"] = commit_author
            commits.append(commit.model_copy(update=updates) if updates else commit)

        return pr.model_copy(
            update={
                "author": self.apply_user(db, pr.author),
                "assignees": [
                    self.apply_user(db, assignee)
                    for assignee in pr.assignees
                ],
                "reviewers": [
                    self.apply_user(db, reviewer)
                    for reviewer in pr.reviewers
                ],
                "merged_by": self.apply_user(db, pr.merged_by),
                "reviews": reviews,
                "issue_comments": issue_comments,
                "comments": comments,
                "commits": commits,
            }
        )
