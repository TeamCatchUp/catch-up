"""
Github Transformer

Github API 응답을 LangChain Document로 변환.

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
    GithubUser,
    GithubIssue,
    GithubIssueComment,
    GithubPullRequest,
    GithubPRReview,
    GithubPRComment,
    GithubPRCommitInfo,
    GithubCommit,
    GithubCommitFile,
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


class GithubTransformer:
    """
    Github API 응답을 LangChain Document로 변환하는 트랜스포머

    변환 흐름:
        API Response (dict) → parse_*() → Schema → transform_*() → Document
    """

    def __init__(self):
        pass

    # ============================================================
    # Issue 파싱 및 변환
    # ============================================================

    def parse_issue(
        self,
        data: dict[str, Any],
        comments: list[dict[str, Any]] | None = None,
    ) -> GithubIssue:
        """
        API 응답을 GithubIssue 스키마로 파싱

        Args:
            data: GraphQL Issue 노드

        Returns:
            GithubIssue 스키마 객체
        """
        # User 파싱 (GraphQL Actor → GithubUser)
        author = self._parse_graphql_user(data.get("author"))

        # Assignees 파싱
        assignees = []
        assignees_nodes = (data.get("assignees", {}).get("nodes") or [])
        for node in assignees_nodes:
            user = self._parse_graphql_user(node)
            if user:
                assignees.append(user)

        # Comments 파싱 (GraphQL 중첩 구조)
        comments = []
        comments_nodes = (data.get("comments", {}).get("nodes") or [])
        for comment_node in comments_nodes:
            comment_author = self._parse_graphql_user(comment_node.get("author"))

            comments.append(GithubIssueComment(
                author=comment_author,
                body=comment_node.get("body", ""),
                created_at=self._parse_datetime(comment_node.get("createdAt")),
                updated_at=self._parse_datetime(comment_node.get("updatedAt")),
            ))

        # GraphQL state 정규화 (OPEN/CLOSED → open/closed)
        raw_state = data.get("state", "OPEN")
        state = raw_state.lower()

        return GithubIssue(
            number=data["number"],
            html_url=data.get("url", ""),
            title=data.get("title", ""),
            body=data.get("body"),
            state=state,
            state_reason=data.get("stateReason"),
            author=author,
            assignees=assignees,
            created_at=self._parse_datetime(data.get("createdAt")),
            updated_at=self._parse_datetime(data.get("updatedAt")),
            closed_at=self._parse_datetime(data.get("closedAt")),
            comments_count=len(comments),
            comments=comments,
        )

    def transform_issue(
        self,
        issue: GithubIssue,
        owner: str,
        repo: str,
        installation_id: int,
    ) -> Document:
        """
        GithubIssue를 LangChain Document로 변환

        Args:
            issue: 파싱된 Issue 스키마
            owner: Repository owner
            repo: Repository name
            installation_id: Github App Installation ID

        Returns:
            LangChain Document
        """
        doc_id = f"github:issue:{owner}/{repo}:{issue.number}"

        # semantic_content: 임베딩용 (의미 중심 텍스트)
        semantic_content = self._build_issue_semantic_content(issue)

        # contextual_content: LLM 답변 생성용 (기존 포맷)
        contextual_content = self._build_issue_contextual_content(issue)

        metadata = self._build_issue_metadata(issue, owner, repo, installation_id)
        metadata["contextual_content"] = contextual_content

        return Document(
            id=doc_id,
            page_content=semantic_content,
            metadata=metadata,
        )

    def _build_issue_semantic_content(self, issue: GithubIssue) -> str:
        """
        Issue용 semantic_content 생성 (의미 중심)

        포함: title, body, comments(본문만)
        제외: 메타데이터(Status, Labels, Assignees 등), 포맷 마커
        """
        parts = []

        # 1. Title
        if issue.title:
            parts.append(issue.title)

        # 2. Body
        if issue.body:
            parts.append(clean_markdown(issue.body))

        # 3. Comments (본문만, author 제외)
        for comment in issue.comments:
            if comment.body:
                parts.append(comment.body)

        return "\n\n".join(parts)

    def _build_issue_contextual_content(self, issue: GithubIssue) -> str:
        """Issue contextual_content 생성 - LLM 답변 생성용"""
        lines = []
        display = self._display_name

        # 제목
        lines.append(f"[Issue #{issue.number}] {issue.title}")
        lines.append("")

        # 상태 정보
        lines.append(f"Status: {issue.state}")

        # 담당자 정보
        people_parts = []
        if issue.assignees:
            assignee_names = ", ".join(display(a) for a in issue.assignees)
            people_parts.append(f"Assigned to: {assignee_names}")
        if issue.author:
            people_parts.append(f"Reported by: {display(issue.author)}")
        if people_parts:
            lines.append(" | ".join(people_parts))

        # 생성일
        lines.append(f"Created: {issue.created_at.strftime('%Y-%m-%d')}")

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
                author_name = display(comment.author)
                date_str = comment.created_at.strftime("%Y-%m-%d %H:%M")
                lines.append(f"[{date_str} {author_name}]: {comment.body}")
            lines.append("")

        return "\n".join(lines)

    def _build_issue_metadata(
        self,
        issue: GithubIssue,
        owner: str,
        repo: str,
        installation_id: int,
    ) -> dict[str, Any]:
        """Issue metadata 생성 (간소화 - PR과 동일한 패턴)"""

        def _user_info(user: GithubUser) -> dict[str, str | None]:
            return {"login": user.login, "name": user.name, "email": user.email}

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
            "number": issue.number,

            # 시간
            "created_at": issue.created_at.isoformat(),
            "updated_at": issue.updated_at.isoformat(),
            "closed_at": issue.closed_at.isoformat() if issue.closed_at else None,
            "synced_at": datetime.now(timezone.utc).isoformat(),

            # 필터링용
            "state": issue.state,
            "state_reason": issue.state_reason,
            "author": _user_info(issue.author) if issue.author else None,
            "author_display": self._display_name(issue.author),
            "assignees": [_user_info(a) for a in issue.assignees],
            "assignee_displays": [self._display_name(a) for a in issue.assignees],
            "comments_count": issue.comments_count,
            # Note: closed_by는 GitHub GraphQL API에서 지원하지 않음 (PR만 지원)
        }

    # ============================================================
    # Pull Request 파싱 및 변환
    # ============================================================

    def parse_pull_request(
        self,
        data: dict[str, Any],
    ) -> GithubPullRequest:
        """
        GraphQL Response Node를 GithubPullRequest로 파싱

        Args:
            data: GraphQL PR Node

        Returns:
            GithubPullRequest 스키마 객체
        """
        author = self._parse_graphql_user(data.get("author"))
        merged_by = self._parse_graphql_user(data.get("mergedBy"))

        assignees = [
            user for node in (data.get("assignees", {}).get("nodes") or [])
            if (user := self._parse_graphql_user(node)) is not None
        ]

        reviewers = []
        for node in (data.get("reviewRequests", {}).get("nodes") or []):
            reviewer = self._parse_graphql_user(
                node.get("requestedReviewer") if node else None
            )
            if reviewer:
                reviewers.append(reviewer)

        # 리뷰 파싱
        parsed_reviews = []
        for node in (data.get("reviews", {}).get("nodes") or []):
            if not node:
                continue
            parsed_reviews.append(GithubPRReview(
                author=self._parse_graphql_user(node.get("author")),
                state=node.get("state"),
                body=node.get("body"),
                submitted_at=self._parse_datetime(node.get("submittedAt")),
            ))

        # 리뷰 코멘트 파싱 (reviewThreads → comments)
        parsed_comments = []
        for thread in (data.get("reviewThreads", {}).get("nodes") or []):
            if not thread:
                continue
            for comment_node in (thread.get("comments", {}).get("nodes") or []):
                if not comment_node:
                    continue
                parsed_comments.append(GithubPRComment(
                    author=self._parse_graphql_user(comment_node.get("author")),
                    body=comment_node.get("body", ""),
                    path=comment_node.get("path"),
                    line=comment_node.get("line"),
                    original_line=comment_node.get("originalLine"),
                    diff_hunk=comment_node.get("diffHunk"),
                    created_at=self._parse_datetime(comment_node.get("createdAt")),
                    updated_at=self._parse_datetime(comment_node.get("updatedAt")),
                ))

        # 커밋 파싱
        parsed_commits = []
        for node in (data.get("commits", {}).get("nodes") or []):
            if not node:
                continue
            commit = node.get("commit", {})
            commit_author = commit.get("author", {})
            parsed_commits.append(GithubPRCommitInfo(
                sha=commit.get("oid", ""),
                message=commit.get("message", ""),
                author_name=commit_author.get("name"),
                author_login=(commit_author.get("user") or {}).get("login"),
                committed_at=self._parse_datetime(commit.get("committedDate")),
            ))

        # GraphQL state: OPEN/CLOSED/MERGED → open/closed
        raw_state = data.get("state", "OPEN")
        state = raw_state.lower() if raw_state in ("OPEN", "CLOSED") else "closed"

        return GithubPullRequest(
            number=data.get("number", 0),
            url=data.get("url", ""),
            html_url=data.get("url", ""),
            title=data.get("title", ""),
            body=data.get("body"),
            state=state,
            merged=data.get("merged", False),
            base_ref=data.get("baseRefName", ""),
            head_ref=data.get("headRefName", ""),
            author=author,
            assignees=assignees,
            reviewers=reviewers,
            merged_by=merged_by,
            created_at=self._parse_datetime(data.get("createdAt")),
            updated_at=self._parse_datetime(data.get("updatedAt")),
            merged_at=self._parse_datetime(data.get("mergedAt")),
            closed_at=self._parse_datetime(data.get("closedAt")),
            changed_files=data.get("changedFiles", 0),
            commits_count=len(parsed_commits),
            reviews=parsed_reviews,
            comments=parsed_comments,
            commits=parsed_commits,
        )

    def transform_pull_request(
        self,
        pr: GithubPullRequest,
        owner: str,
        repo: str,
        installation_id: int,
    ) -> Document:
        """
        GithubPullRequest를 LangChain Document로 변환

        Args:
            pr: 파싱된 PR 스키마
            owner: Repository owner
            repo: Repository name
            installation_id: GitHub App Installation ID

        Returns:
            LangChain Document
        """
        doc_id = f"github:pr:{owner}/{repo}:{pr.number}"

        # semantic_content: 임베딩용 (의미 중심 텍스트)
        semantic_content = self._build_pr_semantic_content(pr)

        # contextual_content: LLM 답변 생성용 (기존 포맷)
        contextual_content = self._build_pr_contextual_content(pr)

        metadata = self._build_pr_metadata(pr, owner, repo, installation_id)
        metadata["contextual_content"] = contextual_content

        return Document(
            id=doc_id,
            page_content=semantic_content,
            metadata=metadata,
        )

    def _build_pr_semantic_content(self, pr: GithubPullRequest) -> str:
        """
        PR용 semantic_content 생성 (의미 중심)

        포함: title, body, commits(메시지만), reviews(본문만), comments(본문만)
        제외: 메타데이터(Status, Author, Branch, Labels 등), 포맷 마커
        """
        parts = []

        # 1. Title
        if pr.title:
            parts.append(pr.title)

        # 2. Body
        if pr.body:
            parts.append(clean_markdown(pr.body))

        # 3. Commits (메시지만)
        for commit in pr.commits:
            if commit.message:
                parts.append(commit.message)

        # 4. Reviews (본문만, author 제외)
        for review in pr.reviews:
            if review.body:
                parts.append(review.body)

        # 5. Comments (본문만, author 제외)
        for comment in pr.comments:
            if comment.body:
                parts.append(comment.body)

        return "\n\n".join(parts)

    def _build_pr_contextual_content(self, pr: GithubPullRequest) -> str:
        """PR contextual_content 생성 - LLM 답변 생성용"""
        lines = []
        display = self._display_name

        # 제목
        lines.append(f"[PR #{pr.number}] {pr.title}")
        lines.append("")

        # 상태 정보
        state = "merged" if pr.merged else pr.state
        status_parts = [f"Status: {state}"]
        if pr.author:
            status_parts.append(f"Author: {display(pr.author)}")
        lines.append(" | ".join(status_parts))

        # 브랜치 정보
        lines.append(f"Base: {pr.base_ref} <- Head: {pr.head_ref}")

        # 리뷰어
        if pr.reviewers:
            reviewer_names = ", ".join(display(r) for r in pr.reviewers)
            lines.append(f"Reviewers: {reviewer_names}")

        lines.append("")

        # 본문
        if pr.body:
            lines.append("Description:")
            lines.append(clean_markdown(pr.body))
            lines.append("")

        # 코드 변경 통계
        lines.append(f"Changes: {pr.changed_files} files, {len(pr.commits)} commits")
        lines.append("")

        # 커밋 목록
        if pr.commits:
            lines.append(f"Commits ({len(pr.commits)}):")
            for commit in pr.commits[:10]:  # 최대 10개
                short_sha = commit.sha[:7]
                message_first_line = commit.message.split("\n")[0] if commit.message else ""
                author = commit.author_name or commit.author_login or "unknown"
                lines.append(f"- [{short_sha}] {message_first_line} ({author})")
            if len(pr.commits) > 10:
                lines.append(f"  ... and {len(pr.commits) - 10} more commits")
            lines.append("")

        # 리뷰 정보
        if pr.reviews:
            lines.append("Reviews:")
            for review in pr.reviews:
                author_name = display(review.author)
                date_str = review.submitted_at.strftime("%Y-%m-%d") if review.submitted_at else "pending"
                lines.append(f"[{review.state} {author_name} at {date_str}]")
                if review.body:
                    lines.append(review.body)
                lines.append("")

        # 리뷰 코멘트 (인라인 코멘트 - 코드 리뷰)
        if pr.comments:
            lines.append(f"Code Review Comments ({len(pr.comments)}):")
            lines.append("")
            for comment in pr.comments:
                author_name = display(comment.author)
                date_str = comment.created_at.strftime("%Y-%m-%d") if comment.created_at else ""

                location_info = ""
                if comment.path:
                    location_info = f"{comment.path}"
                    if comment.line:
                        location_info += f":{comment.line}"
                    elif comment.original_line:
                        location_info += f":{comment.original_line}"

                lines.append(f"--- {author_name} ({date_str}) on {location_info} ---")

                if comment.diff_hunk:
                    hunk_summary = self._summarize_diff_hunk(comment.diff_hunk)
                    if hunk_summary:
                        lines.append(f"[{hunk_summary}]")

                if comment.body:
                    lines.append(comment.body)

                lines.append("")

        return "\n".join(lines)

    def _build_pr_metadata(
        self,
        pr: GithubPullRequest,
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

        def _user_info(user: GithubUser) -> dict[str, str | None]:
            return {"login": user.login, "name": user.name, "email": user.email}

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
            "number": pr.number,

            # 시간
            "created_at": pr.created_at.isoformat(),
            "updated_at": pr.updated_at.isoformat(),
            "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
            "closed_at": pr.closed_at.isoformat() if pr.closed_at else None,
            "synced_at": datetime.now(timezone.utc).isoformat(),

            # 필터링용
            "state": "merged" if pr.merged else pr.state,
            "merged": pr.merged,
            "base_ref": pr.base_ref,
            "head_ref": pr.head_ref,
            "author": _user_info(pr.author) if pr.author else None,
            "author_display": self._display_name(pr.author),
            "assignees": [_user_info(a) for a in pr.assignees],
            "assignee_displays": [self._display_name(a) for a in pr.assignees],
            "reviewers": [_user_info(r) for r in pr.reviewers],
            "reviewer_displays": [self._display_name(r) for r in pr.reviewers],
            "merged_by": _user_info(pr.merged_by) if pr.merged_by else None,
            "merged_by_display": self._display_name(pr.merged_by),

            # 코드 변경 통계
            "changed_files": pr.changed_files,
            "commits_count": len(pr.commits),
            "comments_count": len(pr.comments),

            # 리뷰 상태
            "review_state": review_state,

            # Graph 연계용
            "commit_shas": [c.sha for c in pr.commits],
        }

    # ============================================================
    # Commit 파싱 및 변환
    # ============================================================

    def parse_commit(
        self,
        data: dict[str, Any],
        pr_number: int | None = None,
    ) -> GithubCommit:
        """
        API 응답을 GithubCommit 스키마로 파싱

        Args:
            data: GitHub Commits API 응답
            pr_number: 연결된 PR 번호 (있는 경우)

        Returns:
            GithubCommit 스키마 객체
        """
        commit_data = data.get("commit", {})
        author_data = commit_data.get("author", {})
        committer_data = commit_data.get("committer", {})

        # GitHub 계정 연결된 author
        author = None
        if data.get("author"):
            author = GithubUser(
                id=data["author"]["id"],
                login=data["author"]["login"],
                avatar_url=data["author"].get("avatar_url"),
            )

        # GitHub 계정 연결된 committer
        committer = None
        if data.get("committer"):
            committer = GithubUser(
                id=data["committer"]["id"],
                login=data["committer"]["login"],
                avatar_url=data["committer"].get("avatar_url"),
            )

        # 통계
        stats = data.get("stats", {})

        # 파일 변경
        files = []
        for file in data.get("files", []):
            files.append(GithubCommitFile(
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

        return GithubCommit(
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
        commit: GithubCommit,
        owner: str,
        repo: str,
        installation_id: int,
    ) -> Document:
        """
        GithubCommit를 LangChain Document로 변환

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

        # semantic_content: 임베딩용 (의미 중심 텍스트)
        semantic_content = self._build_commit_semantic_content(commit)

        # contextual_content: LLM 답변 생성용 (기존 포맷)
        contextual_content = self._build_commit_contextual_content(commit)

        metadata = self._build_commit_metadata(commit, owner, repo, installation_id)
        metadata["contextual_content"] = contextual_content

        return Document(
            id=doc_id,
            page_content=semantic_content,
            metadata=metadata,
        )

    def _build_commit_semantic_content(self, commit: GithubCommit) -> str:
        """
        Commit용 semantic_content 생성 (의미 중심)

        포함: message
        제외: 메타데이터(Author, Date, PR, Changes stats 등), 포맷 마커
        """
        return commit.message if commit.message else ""

    def _build_commit_contextual_content(self, commit: GithubCommit) -> str:
        """Commit contextual_content 생성 - LLM 답변 생성용"""
        lines = []
        short_sha = commit.sha[:7]

        # 제목 (커밋 메시지 첫 줄)
        message_lines = commit.message.split("\n")
        title = message_lines[0] if message_lines else "No message"
        lines.append(f"[Commit {short_sha}] {title}")
        lines.append("")

        # 작성자 정보
        author_str = (
            (commit.author.name or commit.author.login) if commit.author else None
        )
        if not author_str:
            author_str = commit.author_name or commit.author_login or "unknown"
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
        commit: GithubCommit,
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
            "author_display": (commit.author.name or commit.author.login) if commit.author else (commit.author_name or commit.author_login),
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

    def _display_name(self, user: GithubUser | None) -> str:
        """실명 우선 표시용 헬퍼"""
        if not user:
            return "unknown"
        return user.name or user.login or "unknown"

    def _parse_graphql_user(self, data: dict[str, Any] | None) -> GithubUser | None:
        """GraphQL User/Actor 노드를 GithubUser로 변환"""
        if not data or not data.get("login"):
            return None
        return GithubUser(
            id=0,
            login=data["login"],
            name=data.get("name"),
            email=data.get("email"),
            avatar_url=data.get("avatarUrl"),
        )

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
