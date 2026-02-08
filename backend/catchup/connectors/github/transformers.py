"""
GitHub Transformer

GitHub API 응답을 LangChain Document로 변환.

Document 구조:
- id: github:{entity_type}:{owner/repo}:{identifier}
- page_content: 사람이 읽기 쉬운 형태의 텍스트
- metadata: 필터링 및 Graph 연계용 메타데이터
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any

from langchain_core.documents import Document

from catchup.connectors.base import clean_markdown
from catchup.connectors.github.schemas import (
    GitHubUser,
    GitHubLabel,
    GitHubMilestone,
    GitHubReaction,
    GitHubIssue,
    GitHubIssueComment,
    GitHubPullRequest,
    GitHubPRReview,
    GitHubPRComment,
    GitHubPRCommitInfo,
    GitHubCommit,
    GitHubCommitFile,
    GitHubRepository,
    PRFileContext,
    PRComment,
)

logger = logging.getLogger(__name__)


# ============================================================
# 관계 추출 패턴
# ============================================================

# PR body에서 Issue 연결 추출 (closes #123, fixes #456 등)
CLOSING_PATTERNS = [
    re.compile(
        r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)",
        re.IGNORECASE
    ),
    # cross-repo 참조: closes owner/repo#123
    re.compile(
        r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+([\w-]+/[\w.-]+)#(\d+)",
        re.IGNORECASE
    ),
]

# 단순 참조 (#123)
REFERENCE_PATTERN = re.compile(r"(?<![/\w])#(\d+)(?!\d)")


class GitHubTransformer:
    """
    GitHub API 응답을 LangChain Document로 변환하는 트랜스포머

    변환 흐름:
        API Response (dict) → parse_*() → Schema → transform_*() → Document
    """

    def __init__(self, user_cache: dict[str, GitHubUser] | None = None):
        """
        Args:
            user_cache: 사용자 ID -> GitHubUser 매핑 (멘션 변환용)
        """
        self.user_cache = user_cache or {}

    # ============================================================
    # Issue 파싱 및 변환
    # ============================================================

    def parse_issue(
        self,
        data: dict[str, Any],
        comments: list[dict[str, Any]] | None = None,
    ) -> GitHubIssue:
        """
        API 응답을 GitHubIssue 스키마로 파싱

        Args:
            data: GitHub Issues API 응답
            comments: Issue comments API 응답

        Returns:
            GitHubIssue 스키마 객체
        """
        # 작성자
        author = None
        if data.get("user"):
            author = GitHubUser(
                id=data["user"]["id"],
                login=data["user"]["login"],
                avatar_url=data["user"].get("avatar_url"),
                html_url=data["user"].get("html_url"),
            )

        # 담당자 목록
        assignees = []
        for assignee in data.get("assignees", []):
            assignees.append(GitHubUser(
                id=assignee["id"],
                login=assignee["login"],
                avatar_url=assignee.get("avatar_url"),
            ))

        # 라벨
        labels = []
        for label in data.get("labels", []):
            labels.append(GitHubLabel(
                id=label["id"],
                name=label["name"],
                color=label.get("color"),
                description=label.get("description"),
            ))

        # 마일스톤
        milestone = None
        if data.get("milestone"):
            ms = data["milestone"]
            milestone = GitHubMilestone(
                id=ms["id"],
                number=ms["number"],
                title=ms["title"],
                state=ms["state"],
                description=ms.get("description"),
                due_on=self._parse_datetime(ms.get("due_on")),
            )

        # 리액션
        reactions = None
        if data.get("reactions"):
            r = data["reactions"]
            reactions = GitHubReaction(
                total_count=r.get("total_count", 0),
                **{"+1": r.get("+1", 0), "-1": r.get("-1", 0)},
                laugh=r.get("laugh", 0),
                hooray=r.get("hooray", 0),
                confused=r.get("confused", 0),
                heart=r.get("heart", 0),
                rocket=r.get("rocket", 0),
                eyes=r.get("eyes", 0),
            )

        # 코멘트 파싱
        parsed_comments = []
        for comment in (comments or []):
            comment_author = None
            if comment.get("user"):
                comment_author = GitHubUser(
                    id=comment["user"]["id"],
                    login=comment["user"]["login"],
                    avatar_url=comment["user"].get("avatar_url"),
                )
            parsed_comments.append(GitHubIssueComment(
                id=comment["id"],
                author=comment_author,
                body=comment.get("body", ""),
                created_at=self._parse_datetime(comment["created_at"]),
                updated_at=self._parse_datetime(comment.get("updated_at")),
            ))

        # body에서 관계 추출
        body = data.get("body") or ""
        linked_prs = self._extract_linked_issues(body)  # PR 참조도 동일한 형식
        referenced = self._extract_referenced_issues(body)

        return GitHubIssue(
            number=data["number"],
            id=data["id"],
            node_id=data.get("node_id"),
            url=data["url"],
            html_url=data["html_url"],
            title=data["title"],
            body=body,
            state=data["state"],
            state_reason=data.get("state_reason"),
            author=author,
            assignees=assignees,
            labels=labels,
            milestone=milestone,
            created_at=self._parse_datetime(data["created_at"]),
            updated_at=self._parse_datetime(data["updated_at"]),
            closed_at=self._parse_datetime(data.get("closed_at")),
            comments_count=data.get("comments", 0),
            comments=parsed_comments,
            reactions=reactions,
            linked_pr_numbers=linked_prs,
            referenced_issues=referenced,
        )

    def transform_issue(
        self,
        issue: GitHubIssue,
        owner: str,
        repo: str,
        installation_id: int,
    ) -> Document:
        """
        GitHubIssue를 LangChain Document로 변환

        Args:
            issue: 파싱된 Issue 스키마
            owner: Repository owner
            repo: Repository name
            installation_id: GitHub App Installation ID

        Returns:
            LangChain Document
        """
        doc_id = f"github:issue:{owner}/{repo}:{issue.number}"
        page_content = self._build_issue_content(issue)
        metadata = self._build_issue_metadata(issue, owner, repo, installation_id)

        return Document(
            id=doc_id,
            page_content=page_content,
            metadata=metadata,
        )

    def _build_issue_content(self, issue: GitHubIssue) -> str:
        """Issue page_content 생성"""
        lines = []

        # 제목
        lines.append(f"[Issue #{issue.number}] {issue.title}")
        lines.append("")

        # 상태 정보
        status_parts = [f"Status: {issue.state}"]
        if issue.labels:
            label_names = ", ".join(l.name for l in issue.labels)
            status_parts.append(f"Labels: {label_names}")
        lines.append(" | ".join(status_parts))

        # 담당자 정보
        people_parts = []
        if issue.assignees:
            assignee_names = ", ".join(f"@{a.login}" for a in issue.assignees)
            people_parts.append(f"Assigned to: {assignee_names}")
        if issue.author:
            people_parts.append(f"Reported by: @{issue.author.login}")
        if people_parts:
            lines.append(" | ".join(people_parts))

        # 마일스톤 및 생성일
        meta_parts = []
        if issue.milestone:
            meta_parts.append(f"Milestone: {issue.milestone.title}")
        meta_parts.append(f"Created: {issue.created_at.strftime('%Y-%m-%d')}")
        lines.append(" | ".join(meta_parts))

        lines.append("")

        # 본문
        if issue.body:
            lines.append("Description:")
            lines.append(clean_markdown(issue.body))
            lines.append("")

        # 최근 토론
        if issue.comments:
            lines.append(f"Recent Discussion ({len(issue.comments)}):")
            for comment in issue.comments[:5]:  # 최근 5개만
                author_name = comment.author.login if comment.author else "unknown"
                date_str = comment.created_at.strftime("%Y-%m-%d %H:%M")
                lines.append(f"[{date_str} @{author_name}]: {comment.body}")
            lines.append("")

        # 관련 항목
        related = []
        if issue.linked_pr_numbers:
            for pr_num in issue.linked_pr_numbers:
                related.append(f"- Referenced in PR #{pr_num}")
        if issue.referenced_issues:
            for ref_num in issue.referenced_issues:
                related.append(f"- References Issue #{ref_num}")
        if related:
            lines.append("Related:")
            lines.extend(related)

        return "\n".join(lines)

    def _build_issue_metadata(
        self,
        issue: GitHubIssue,
        owner: str,
        repo: str,
        installation_id: int,
    ) -> dict[str, Any]:
        """Issue metadata 생성"""
        return {
            # 공통 필수
            "source": "github",
            "entity_type": "issue",
            "url": issue.html_url,
            "summary": issue.title,

            # GitHub 식별
            "installation_id": installation_id,
            "owner": owner,
            "repo": repo,
            "full_name": f"{owner}/{repo}",
            "number": issue.number,
            "issue_id": issue.id,

            # 시간
            "created_at": issue.created_at.isoformat(),
            "updated_at": issue.updated_at.isoformat(),
            "closed_at": issue.closed_at.isoformat() if issue.closed_at else None,
            "synced_at": datetime.now(timezone.utc).isoformat(),

            # 필터링용
            "state": issue.state,
            "state_reason": issue.state_reason,
            "author": issue.author.login if issue.author else None,
            "assignees": [a.login for a in issue.assignees],
            "labels": [l.name for l in issue.labels],
            "milestone": issue.milestone.title if issue.milestone else None,
            "comments_count": issue.comments_count,

            # Graph 연계용 관계 정보
            "linked_prs": issue.linked_pr_numbers,
            "referenced_issues": issue.referenced_issues,
        }

    # ============================================================
    # Pull Request 파싱 및 변환
    # ============================================================

    def parse_pull_request(
        self,
        data: dict[str, Any],
        reviews: list[dict[str, Any]] | None = None,
        comments: list[dict[str, Any]] | None = None,
        commits: list[dict[str, Any]] | None = None,
    ) -> GitHubPullRequest:
        """
        API 응답을 GitHubPullRequest 스키마로 파싱

        Args:
            data: GitHub Pulls List API 응답
            reviews: PR reviews API 응답
            comments: PR review comments API 응답 (인라인 코멘트)
            commits: PR commits API 응답

        Returns:
            GitHubPullRequest 스키마 객체
        """
        # 작성자
        author = None
        if data.get("user"):
            author = GitHubUser(
                id=data["user"]["id"],
                login=data["user"]["login"],
                avatar_url=data["user"].get("avatar_url"),
                html_url=data["user"].get("html_url"),
            )

        # 담당자 목록
        assignees = []
        for assignee in data.get("assignees", []):
            assignees.append(GitHubUser(
                id=assignee["id"],
                login=assignee["login"],
                avatar_url=assignee.get("avatar_url"),
            ))

        # 리뷰어 목록
        reviewers = []
        for reviewer in data.get("requested_reviewers", []):
            reviewers.append(GitHubUser(
                id=reviewer["id"],
                login=reviewer["login"],
                avatar_url=reviewer.get("avatar_url"),
            ))

        # 라벨
        labels = []
        for label in data.get("labels", []):
            labels.append(GitHubLabel(
                id=label["id"],
                name=label["name"],
                color=label.get("color"),
                description=label.get("description"),
            ))

        # 마일스톤
        milestone = None
        if data.get("milestone"):
            ms = data["milestone"]
            milestone = GitHubMilestone(
                id=ms["id"],
                number=ms["number"],
                title=ms["title"],
                state=ms["state"],
                description=ms.get("description"),
                due_on=self._parse_datetime(ms.get("due_on")),
            )

        # 리뷰 파싱
        parsed_reviews = []
        for review in (reviews or []):
            review_author = None
            if review.get("user"):
                review_author = GitHubUser(
                    id=review["user"]["id"],
                    login=review["user"]["login"],
                    avatar_url=review["user"].get("avatar_url"),
                )
            parsed_reviews.append(GitHubPRReview(
                id=review["id"],
                author=review_author,
                state=review.get("state", "PENDING"),
                body=review.get("body"),
                submitted_at=self._parse_datetime(review.get("submitted_at")),
            ))

        # 리뷰 코멘트 파싱 (인라인 코멘트)
        parsed_comments = []
        for comment in (comments or []):
            comment_author = None
            if comment.get("user"):
                comment_author = GitHubUser(
                    id=comment["user"]["id"],
                    login=comment["user"]["login"],
                    avatar_url=comment["user"].get("avatar_url"),
                )
            parsed_comments.append(GitHubPRComment(
                id=comment["id"],
                author=comment_author,
                body=comment.get("body", ""),
                path=comment.get("path"),
                line=comment.get("line"),
                original_line=comment.get("original_line"),
                diff_hunk=comment.get("diff_hunk"),
                created_at=self._parse_datetime(comment["created_at"]),
                updated_at=self._parse_datetime(comment.get("updated_at")),
            ))

        # 커밋 파싱
        parsed_commits = []
        for commit in (commits or []):
            commit_data = commit.get("commit", {})
            author_data = commit_data.get("author", {})
            committer_data = commit_data.get("committer", {})

            # GitHub 계정 연결된 author
            author_login = None
            if commit.get("author"):
                author_login = commit["author"].get("login")

            parsed_commits.append(GitHubPRCommitInfo(
                sha=commit["sha"],
                message=commit_data.get("message", ""),
                author_name=author_data.get("name"),
                author_login=author_login,
                committed_at=self._parse_datetime(committer_data.get("date")),
            ))

        # body에서 관계 추출
        body = data.get("body") or ""
        linked_issues = self._extract_closing_issues(body)

        # 브랜치 정보
        base = data.get("base", {})
        head = data.get("head", {})

        return GitHubPullRequest(
            number=data["number"],
            id=data["id"],
            node_id=data.get("node_id"),
            url=data["url"],
            html_url=data["html_url"],
            title=data["title"],
            body=body,
            state=data["state"],
            draft=data.get("draft", False),
            merged=data.get("merged", False),
            base_ref=base.get("ref", ""),
            head_ref=head.get("ref", ""),
            base_sha=base.get("sha"),
            head_sha=head.get("sha"),
            author=author,
            assignees=assignees,
            requested_reviewers=reviewers,
            labels=labels,
            milestone=milestone,
            created_at=self._parse_datetime(data["created_at"]),
            updated_at=self._parse_datetime(data["updated_at"]),
            merged_at=self._parse_datetime(data.get("merged_at")),
            closed_at=self._parse_datetime(data.get("closed_at")),
            additions=data.get("additions", 0),
            deletions=data.get("deletions", 0),
            changed_files=data.get("changed_files", 0),
            commits_count=data.get("commits", 0),
            reviews=parsed_reviews,
            comments=parsed_comments,
            commits=parsed_commits,
            linked_issue_numbers=linked_issues,
        )

    def transform_pull_request(
        self,
        pr: GitHubPullRequest,
        owner: str,
        repo: str,
        installation_id: int,
    ) -> Document:
        """
        GitHubPullRequest를 LangChain Document로 변환

        Args:
            pr: 파싱된 PR 스키마
            owner: Repository owner
            repo: Repository name
            installation_id: GitHub App Installation ID

        Returns:
            LangChain Document
        """
        doc_id = f"github:pr:{owner}/{repo}:{pr.number}"
        page_content = self._build_pr_content(pr)
        metadata = self._build_pr_metadata(pr, owner, repo, installation_id)

        return Document(
            id=doc_id,
            page_content=page_content,
            metadata=metadata,
        )

    def _build_pr_content(self, pr: GitHubPullRequest) -> str:
        """PR page_content 생성"""
        lines = []

        # 제목
        lines.append(f"[PR #{pr.number}] {pr.title}")
        lines.append("")

        # 상태 정보
        state = "merged" if pr.merged else pr.state
        status_parts = [f"Status: {state}"]
        if pr.author:
            status_parts.append(f"Author: @{pr.author.login}")
        lines.append(" | ".join(status_parts))

        # 브랜치 정보
        lines.append(f"Base: {pr.base_ref} <- Head: {pr.head_ref}")

        # 라벨 및 리뷰어
        meta_parts = []
        if pr.labels:
            label_names = ", ".join(l.name for l in pr.labels)
            meta_parts.append(f"Labels: {label_names}")
        if pr.requested_reviewers:
            reviewer_names = ", ".join(f"@{r.login}" for r in pr.requested_reviewers)
            meta_parts.append(f"Reviewers: {reviewer_names}")
        if meta_parts:
            lines.append(" | ".join(meta_parts))

        lines.append("")

        # 본문
        if pr.body:
            lines.append("Description:")
            lines.append(clean_markdown(pr.body))
            lines.append("")

        # 코드 변경 통계
        lines.append(f"Changes: +{pr.additions} -{pr.deletions} ({pr.changed_files} files, {len(pr.commits)} commits)")

        # 연결된 Issue
        if pr.linked_issue_numbers:
            closes = ", ".join(f"#{n}" for n in pr.linked_issue_numbers)
            lines.append(f"Closes: {closes}")

        lines.append("")

        # 커밋 목록
        if pr.commits:
            lines.append(f"Commits ({len(pr.commits)}):")
            for commit in pr.commits[:10]:  # 최대 10개
                short_sha = commit.sha[:7]
                # 커밋 메시지 첫 줄만
                message_first_line = commit.message.split("\n")[0] if commit.message else ""
                author = commit.author_login or commit.author_name or "unknown"
                lines.append(f"- [{short_sha}] {message_first_line} (@{author})")
            if len(pr.commits) > 10:
                lines.append(f"  ... and {len(pr.commits) - 10} more commits")
            lines.append("")

        # 리뷰 정보
        if pr.reviews:
            lines.append("Reviews:")
            for review in pr.reviews:
                author_name = review.author.login if review.author else "unknown"
                date_str = review.submitted_at.strftime("%Y-%m-%d") if review.submitted_at else "pending"
                lines.append(f"[{review.state} @{author_name} at {date_str}]")
                if review.body:
                    lines.append(review.body)
                lines.append("")

        # 리뷰 코멘트 (인라인 코멘트 - 코드 리뷰)
        if pr.comments:
            lines.append(f"Code Review Comments ({len(pr.comments)}):")
            lines.append("")
            for comment in pr.comments:
                author_name = comment.author.login if comment.author else "unknown"
                date_str = comment.created_at.strftime("%Y-%m-%d") if comment.created_at else ""

                # 파일 및 라인 정보
                location_info = ""
                if comment.path:
                    location_info = f"{comment.path}"
                    if comment.line:
                        location_info += f":{comment.line}"
                    elif comment.original_line:
                        location_info += f":{comment.original_line}"

                lines.append(f"--- @{author_name} ({date_str}) on {location_info} ---")

                # diff_hunk에서 변경 라인 정보 추출 (코드 전체 대신 요약)
                if comment.diff_hunk:
                    hunk_summary = self._summarize_diff_hunk(comment.diff_hunk)
                    if hunk_summary:
                        lines.append(f"[{hunk_summary}]")

                # 코멘트 본문 (전체)
                if comment.body:
                    lines.append(comment.body)

                lines.append("")

        return "\n".join(lines)

    def _build_pr_metadata(
        self,
        pr: GitHubPullRequest,
        owner: str,
        repo: str,
        installation_id: int,
    ) -> dict[str, Any]:
        """PR metadata 생성"""
        # 리뷰 상태 결정
        review_state = None
        if pr.reviews:
            states = [r.state for r in pr.reviews if r.state != "PENDING"]
            if "APPROVED" in states:
                review_state = "approved"
            elif "CHANGES_REQUESTED" in states:
                review_state = "changes_requested"
            elif states:
                review_state = "commented"
            else:
                review_state = "pending"

        return {
            # 공통 필수
            "source": "github",
            "entity_type": "pr",
            "url": pr.html_url,
            "summary": pr.title,

            # GitHub 식별
            "installation_id": installation_id,
            "owner": owner,
            "repo": repo,
            "full_name": f"{owner}/{repo}",
            "number": pr.number,
            "pr_id": pr.id,

            # 시간
            "created_at": pr.created_at.isoformat(),
            "updated_at": pr.updated_at.isoformat(),
            "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
            "closed_at": pr.closed_at.isoformat() if pr.closed_at else None,
            "synced_at": datetime.now(timezone.utc).isoformat(),

            # 필터링용
            "state": "merged" if pr.merged else pr.state,
            "draft": pr.draft,
            "merged": pr.merged,
            "base_ref": pr.base_ref,
            "head_ref": pr.head_ref,
            "author": pr.author.login if pr.author else None,
            "assignees": [a.login for a in pr.assignees],
            "reviewers": [r.login for r in pr.requested_reviewers],
            "labels": [l.name for l in pr.labels],
            "milestone": pr.milestone.title if pr.milestone else None,

            # 코드 변경 통계
            "additions": pr.additions,
            "deletions": pr.deletions,
            "changed_files": pr.changed_files,
            "commits_count": len(pr.commits),
            "comments_count": len(pr.comments),

            # 리뷰 상태
            "review_state": review_state,

            # Graph 연계용 관계 정보
            "linked_issue_numbers": pr.linked_issue_numbers,
            "commit_shas": [c.sha for c in pr.commits],  # Graph DB 연결용
        }

    # ============================================================
    # Commit 파싱 및 변환
    # ============================================================

    def parse_commit(
        self,
        data: dict[str, Any],
        pr_number: int | None = None,
    ) -> GitHubCommit:
        """
        API 응답을 GitHubCommit 스키마로 파싱

        Args:
            data: GitHub Commits API 응답
            pr_number: 연결된 PR 번호 (있는 경우)

        Returns:
            GitHubCommit 스키마 객체
        """
        commit_data = data.get("commit", {})
        author_data = commit_data.get("author", {})
        committer_data = commit_data.get("committer", {})

        # GitHub 계정 연결된 author
        author = None
        if data.get("author"):
            author = GitHubUser(
                id=data["author"]["id"],
                login=data["author"]["login"],
                avatar_url=data["author"].get("avatar_url"),
            )

        # GitHub 계정 연결된 committer
        committer = None
        if data.get("committer"):
            committer = GitHubUser(
                id=data["committer"]["id"],
                login=data["committer"]["login"],
                avatar_url=data["committer"].get("avatar_url"),
            )

        # 통계
        stats = data.get("stats", {})

        # 파일 변경
        files = []
        for file in data.get("files", []):
            files.append(GitHubCommitFile(
                filename=file["filename"],
                status=file["status"],
                additions=file.get("additions", 0),
                deletions=file.get("deletions", 0),
                changes=file.get("changes", 0),
                patch=file.get("patch"),
                previous_filename=file.get("previous_filename"),
            ))

        # 부모 커밋
        parent_shas = [p["sha"] for p in data.get("parents", [])]

        return GitHubCommit(
            sha=data["sha"],
            url=data["url"],
            html_url=data["html_url"],
            message=commit_data.get("message", ""),
            author=author,
            author_name=author_data.get("name"),
            author_email=author_data.get("email"),
            committer=committer,
            committer_name=committer_data.get("name"),
            committer_email=committer_data.get("email"),
            committed_at=self._parse_datetime(author_data.get("date")),
            additions=stats.get("additions", 0),
            deletions=stats.get("deletions", 0),
            total_changes=stats.get("total", 0),
            files=files,
            pr_number=pr_number,
            parent_shas=parent_shas,
        )

    def transform_commit(
        self,
        commit: GitHubCommit,
        owner: str,
        repo: str,
        installation_id: int,
    ) -> Document:
        """
        GitHubCommit를 LangChain Document로 변환

        Args:
            commit: 파싱된 Commit 스키마
            owner: Repository owner
            repo: Repository name
            installation_id: GitHub App Installation ID

        Returns:
            LangChain Document
        """
        short_sha = commit.sha[:7]
        doc_id = f"github:commit:{owner}/{repo}:{short_sha}"
        page_content = self._build_commit_content(commit)
        metadata = self._build_commit_metadata(commit, owner, repo, installation_id)

        return Document(
            id=doc_id,
            page_content=page_content,
            metadata=metadata,
        )

    def _build_commit_content(self, commit: GitHubCommit) -> str:
        """Commit page_content 생성"""
        lines = []
        short_sha = commit.sha[:7]

        # 제목 (커밋 메시지 첫 줄)
        message_lines = commit.message.split("\n")
        title = message_lines[0] if message_lines else "No message"
        lines.append(f"[Commit {short_sha}] {title}")
        lines.append("")

        # 작성자 정보
        author_str = commit.author.login if commit.author else commit.author_name or "unknown"
        if commit.author_email:
            author_str += f" <{commit.author_email}>"
        lines.append(f"Author: {author_str}")
        lines.append(f"Date: {commit.committed_at.strftime('%Y-%m-%d %H:%M')}")

        # PR 연결
        if commit.pr_number:
            lines.append(f"PR: #{commit.pr_number}")

        lines.append("")

        # 전체 메시지
        if len(message_lines) > 1:
            lines.append("Message:")
            lines.append(commit.message)
            lines.append("")

        # 변경 통계
        lines.append(f"Changes: +{commit.additions} -{commit.deletions} ({len(commit.files)} files)")

        # 변경된 파일
        if commit.files:
            lines.append("")
            lines.append("Files:")
            for file in commit.files[:20]:  # 최대 20개
                lines.append(f"- {file.filename} (+{file.additions}/-{file.deletions})")

        return "\n".join(lines)

    def _build_commit_metadata(
        self,
        commit: GitHubCommit,
        owner: str,
        repo: str,
        installation_id: int,
    ) -> dict[str, Any]:
        """Commit metadata 생성"""
        return {
            # 공통 필수
            "source": "github",
            "entity_type": "commit",
            "url": commit.html_url,
            "summary": commit.message.split("\n")[0] if commit.message else "",

            # GitHub 식별
            "installation_id": installation_id,
            "owner": owner,
            "repo": repo,
            "full_name": f"{owner}/{repo}",
            "sha": commit.sha,
            "short_sha": commit.sha[:7],

            # 시간
            "committed_at": commit.committed_at.isoformat(),
            "synced_at": datetime.now(timezone.utc).isoformat(),

            # 작성자
            "author": commit.author.login if commit.author else None,
            "author_name": commit.author_name,
            "author_email": commit.author_email,
            "committer": commit.committer.login if commit.committer else None,

            # 통계
            "additions": commit.additions,
            "deletions": commit.deletions,
            "files_changed": len(commit.files),

            # Graph 연계용 관계 정보
            "pr_number": commit.pr_number,
            "parent_shas": commit.parent_shas,
        }

    # ============================================================
    # 유틸리티 메서드
    # ============================================================

    def _parse_datetime(self, value: str | datetime | None) -> datetime | None:
        """ISO 8601 문자열 또는 datetime 객체를 datetime으로 변환"""
        if value is None:
            return None
        # 이미 datetime 객체인 경우 그대로 반환
        if isinstance(value, datetime):
            return value
        # 문자열인 경우 파싱
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (ValueError, AttributeError, TypeError):
            return None

    def _to_int(self, value: Any, default: int = 0) -> int:
        """값을 정수로 변환"""
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def _extract_closing_issues(self, text: str) -> list[int]:
        """
        텍스트에서 closes/fixes/resolves #123 패턴 추출

        Args:
            text: PR body 텍스트

        Returns:
            연결된 Issue 번호 리스트
        """
        issues = []
        for pattern in CLOSING_PATTERNS:
            for match in pattern.finditer(text):
                groups = match.groups()
                if len(groups) == 1:
                    # #123 형태
                    issues.append(int(groups[0]))
                elif len(groups) == 2:
                    # owner/repo#123 형태 (cross-repo, 현재는 숫자만 추출)
                    issues.append(int(groups[1]))
        return list(set(issues))

    def _extract_linked_issues(self, text: str) -> list[int]:
        """
        텍스트에서 closes/fixes 패턴으로 연결된 Issue 추출
        (Issue body에서 PR 참조 추출 시 사용)
        """
        return self._extract_closing_issues(text)

    def _extract_referenced_issues(self, text: str) -> list[int]:
        """
        텍스트에서 단순 #123 참조 추출

        Args:
            text: Issue/PR body 텍스트

        Returns:
            참조된 Issue 번호 리스트
        """
        # closes/fixes로 연결된 것 제외
        closing = set(self._extract_closing_issues(text))

        referenced = []
        for match in REFERENCE_PATTERN.finditer(text):
            num = int(match.group(1))
            if num not in closing:
                referenced.append(num)

        return list(set(referenced))

    def _summarize_diff_hunk(self, diff_hunk: str) -> str | None:
        """
        diff_hunk에서 변경된 라인 정보 요약 추출

        diff_hunk 헤더 형식: @@ -start,count +start,count @@
        예: @@ -40,6 +40,8 @@ 는 원본 40번 라인부터 6줄, 새 파일 40번 라인부터 8줄

        Args:
            diff_hunk: Git diff hunk 문자열

        Returns:
            요약 문자열 (예: "lines 40-46, +2 added") 또는 None
        """
        if not diff_hunk:
            return None

        # diff hunk 헤더 파싱: @@ -old_start,old_count +new_start,new_count @@
        hunk_header_pattern = re.compile(
            r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@"
        )
        match = hunk_header_pattern.search(diff_hunk)
        if not match:
            return None

        old_start = int(match.group(1))
        old_count = int(match.group(2)) if match.group(2) else 1
        new_start = int(match.group(3))
        new_count = int(match.group(4)) if match.group(4) else 1

        # 변경 라인 범위 계산
        old_end = old_start + old_count - 1 if old_count > 0 else old_start
        new_end = new_start + new_count - 1 if new_count > 0 else new_start

        # 추가/삭제된 라인 수 계산
        added = new_count - old_count if new_count > old_count else 0
        deleted = old_count - new_count if old_count > new_count else 0

        # 요약 문자열 생성
        parts = []

        # 라인 범위
        if old_count > 0:
            if old_start == old_end:
                parts.append(f"line {old_start}")
            else:
                parts.append(f"lines {old_start}-{old_end}")

        # 변경 내용
        changes = []
        if added > 0:
            changes.append(f"+{added} added")
        if deleted > 0:
            changes.append(f"-{deleted} deleted")
        if added == 0 and deleted == 0 and old_count > 0:
            changes.append("modified")

        if changes:
            parts.append(", ".join(changes))

        return ", ".join(parts) if parts else None
