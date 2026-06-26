from __future__ import annotations

from datetime import datetime
from datetime import timezone

from catchup.connectors.github.schemas import GithubIssueComment
from catchup.connectors.github.schemas import GithubLabel
from catchup.connectors.github.schemas import GithubMilestone
from catchup.connectors.github.schemas import GithubPRComment
from catchup.connectors.github.schemas import GithubPRCommitInfo
from catchup.connectors.github.schemas import GithubPRReview
from catchup.connectors.github.schemas import GithubPullRequest
from catchup.connectors.github.schemas import GithubUser
from catchup.sync.ingestion.document_builders.github import GithubTransformer
from catchup.sync.ingestion.vector_records import GithubPrV2RecordMapper


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def test_github_pr_parser_preserves_v2_part_source_fields() -> None:
    pr = GithubTransformer().parse_pull_request(
        {
            "number": 724,
            "url": "https://github.com/TeamCatchUp/CatchUp/pull/724",
            "title": "[CAM-37] refactor backend prompt pipeline",
            "body": "Refactor prompt pipeline.",
            "state": "MERGED",
            "merged": True,
            "baseRefName": "develop",
            "headRefName": "feature/pr-v2",
            "author": {
                "__typename": "User",
                "databaseId": 1,
                "login": "ba2slk",
                "name": "팀원C",
                "email": "ba2slk@example.com",
                "avatarUrl": "https://github.com/ba2slk.png",
                "url": "https://github.com/ba2slk",
            },
            "mergedBy": None,
            "assignees": {"nodes": []},
            "reviewRequests": {"nodes": []},
            "labels": {
                "nodes": [
                    {
                        "name": "refactor",
                        "color": "a2eeef",
                        "description": "cleanup",
                    }
                ]
            },
            "milestone": {
                "number": 37,
                "title": "Prompt Work",
                "state": "OPEN",
                "dueOn": "2026-06-30T00:00:00Z",
            },
            "isDraft": False,
            "reviewDecision": "APPROVED",
            "additions": 120,
            "deletions": 50,
            "changedFiles": 38,
            "createdAt": "2026-05-19T20:13:01Z",
            "updatedAt": "2026-05-19T20:19:53Z",
            "mergedAt": "2026-05-19T20:13:11Z",
            "closedAt": "2026-05-19T20:13:11Z",
            "comments": {
                "nodes": [
                    {
                        "databaseId": 200,
                        "author": {"__typename": "Bot", "login": "github-actions"},
                        "body": "Conversation comment body.",
                        "createdAt": "2026-05-19T20:14:30Z",
                        "updatedAt": "2026-05-19T20:14:45Z",
                    }
                ]
            },
            "reviews": {
                "nodes": [
                    {
                        "databaseId": 300,
                        "author": {"__typename": "User", "login": "reviewer"},
                        "state": "APPROVED",
                        "body": "Looks good.",
                        "submittedAt": "2026-05-19T20:15:00Z",
                    }
                ]
            },
            "reviewThreads": {
                "nodes": [
                    {
                        "comments": {
                            "nodes": [
                                {
                                    "databaseId": 301,
                                    "author": {
                                        "__typename": "User",
                                        "login": "reviewer",
                                    },
                                    "body": "This instruction is duplicated.",
                                    "path": "backend/file.py",
                                    "line": 9,
                                    "originalLine": 8,
                                    "outdated": False,
                                    "diffHunk": "@@ -7,6 +7,7 @@",
                                    "createdAt": "2026-05-19T20:16:00Z",
                                    "updatedAt": "2026-05-19T20:16:30Z",
                                }
                            ]
                        }
                    }
                ]
            },
            "commits": {
                "nodes": [
                    {
                        "commit": {
                            "oid": "abcdef123456",
                            "message": "test(backend): add prompt rendering tests",
                            "author": {
                                "name": "팀원C",
                                "email": "ba2slk@example.com",
                                "user": {
                                    "__typename": "User",
                                    "databaseId": 1,
                                    "login": "ba2slk",
                                    "name": "팀원C",
                                    "email": "ba2slk@example.com",
                                    "avatarUrl": "https://github.com/ba2slk.png",
                                    "url": "https://github.com/ba2slk",
                                },
                            },
                            "committedDate": "2026-05-19T20:14:00Z",
                        }
                    }
                ]
            },
        }
    )

    assert pr.state == "closed"
    assert pr.review_decision == "APPROVED"
    assert pr.additions == 120
    assert pr.deletions == 50
    assert pr.author and pr.author.type == "User"
    assert pr.issue_comments[0].id == 200
    assert pr.issue_comments[0].author and pr.issue_comments[0].author.type == "Bot"
    assert pr.reviews[0].id == 300
    assert pr.comments[0].id == 301
    assert pr.comments[0].path == "backend/file.py"
    assert pr.comments[0].line == 9
    assert pr.comments[0].outdated is False
    assert pr.commits[0].author and pr.commits[0].author.login == "ba2slk"
    assert pr.labels[0].name == "refactor"
    assert pr.milestone and pr.milestone.title == "Prompt Work"


def test_github_pr_v2_mapper_builds_record_from_parsed_pr() -> None:
    pr = GithubPullRequest(
        number=724,
        url="https://api.github.com/repos/TeamCatchUp/CatchUp/pulls/724",
        html_url="https://github.com/TeamCatchUp/CatchUp/pull/724",
        title="[CAM-37] refactor backend prompt pipeline",
        body="Refactor prompt pipeline with clearer XML sections.",
        state="closed",
        merged=True,
        base_ref="develop",
        head_ref="refactor/backend/CAM-37-xml-based-prompt-engineering",
        author=GithubUser(
            id=1,
            login="ba2slk",
            name="팀원C",
            email="ba2slk@example.com",
            avatar_url="https://github.com/ba2slk.png",
            html_url="https://github.com/ba2slk",
            type="User",
            catchup_user_id="usr_github_ba2slk",
        ),
        assignees=[
            GithubUser(
                id=2,
                login="maintainer",
                name="Maintainer",
                avatar_url="https://github.com/maintainer.png",
                catchup_user_id="usr_github_maintainer",
            )
        ],
        reviewers=[
            GithubUser(
                id=3,
                login="reviewer",
                name="Reviewer",
                avatar_url="https://github.com/reviewer.png",
                catchup_user_id=None,
            )
        ],
        merged_by=GithubUser(
            id=1,
            login="ba2slk",
            name="팀원C",
            avatar_url="https://github.com/ba2slk.png",
            catchup_user_id="usr_github_ba2slk",
        ),
        created_at=_dt("2026-05-19T20:13:01+00:00"),
        updated_at=_dt("2026-05-19T20:19:53+00:00"),
        merged_at=_dt("2026-05-19T20:13:11+00:00"),
        closed_at=_dt("2026-05-19T20:13:11+00:00"),
        changed_files=38,
        additions=120,
        deletions=50,
        is_draft=False,
        review_decision="APPROVED",
        labels=[GithubLabel(name="refactor", color="a2eeef", description=None)],
        milestone=GithubMilestone(number=37, title="Prompt Work", state="OPEN"),
        commits_count=1,
        issue_comments=[
            GithubIssueComment(
                id=200,
                author=GithubUser(id=4, login="commenter", name="Commenter"),
                body="Conversation comment body.",
                created_at=_dt("2026-05-19T20:14:30+00:00"),
                updated_at=_dt("2026-05-19T20:14:45+00:00"),
            )
        ],
        reviews=[
            GithubPRReview(
                id=300,
                author=GithubUser(
                    id=3,
                    login="reviewer",
                    name="Reviewer",
                    catchup_user_id=None,
                ),
                state="APPROVED",
                body="Looks good.",
                submitted_at=_dt("2026-05-19T20:15:00+00:00"),
            ),
            GithubPRReview(
                id=302,
                author=GithubUser(
                    id=3,
                    login="reviewer",
                    name="Reviewer",
                    catchup_user_id=None,
                ),
                state="COMMENTED",
                body="  ",
                submitted_at=_dt("2026-05-19T20:15:30+00:00"),
            )
        ],
        comments=[
            GithubPRComment(
                id=301,
                author=GithubUser(
                    id=3,
                    login="reviewer",
                    name="Reviewer",
                    catchup_user_id=None,
                ),
                body="This instruction is duplicated.",
                path="backend/catchup/prompts/rag/agent_limit_extraction.j2",
                line=9,
                original_line=8,
                outdated=False,
                diff_hunk="@@ -7,6 +7,7 @@",
                created_at=_dt("2026-05-19T20:16:00+00:00"),
                updated_at=_dt("2026-05-19T20:16:30+00:00"),
            )
        ],
        commits=[
            GithubPRCommitInfo(
                sha="abcdef123456",
                message="test(backend): add prompt rendering tests",
                author=GithubUser(
                    id=1,
                    login="ba2slk",
                    name="팀원C",
                    catchup_user_id="usr_github_ba2slk",
                ),
                author_name="팀원C",
                author_login="ba2slk",
                committed_at=_dt("2026-05-19T20:14:00+00:00"),
            )
        ],
    )

    record = GithubPrV2RecordMapper().to_record(
        pr,
        owner="TeamCatchUp",
        repo="CatchUp",
        installation_id=118342815,
        content="LLM summarized pull request content",
        embedding=[0.0123, -0.0456, 0.0789],
        synced_at=_dt("2026-06-10T03:00:00+00:00"),
    )
    values = record.to_db_values()

    assert values["langchain_id"] == "github:pr:TeamCatchUp/CatchUp:724"
    assert values["content"] == "LLM summarized pull request content"
    assert values["embedding"] == [0.0123, -0.0456, 0.0789]
    assert values["record_id"] == "724"
    assert values["scope_type"] == "installation"
    assert values["scope_id"] == "118342815"
    assert values["target_type"] == "repository"
    assert values["target_id"] == "TeamCatchUp/CatchUp"
    assert values["target_name"] == "TeamCatchUp/CatchUp"
    assert values["internal_author_id"] == "usr_github_ba2slk"
    assert values["body"] == (
        "Refactor prompt pipeline with clearer XML sections.\n\n"
        "test(backend): add prompt rendering tests\n\n"
        "Conversation comment body.\n\n"
        "Looks good.\n\n"
        "This instruction is duplicated."
    )
    assert "Code Review Comments" not in values["body"]
    assert "backend/catchup/prompts" not in values["body"]
    assert "[APPROVED" not in values["body"]
    assert [part["type"] for part in values["data"]["parts"]] == [
        "pr_body",
        "commit",
        "issue_comment",
        "review",
        "review_comment",
    ]
    commit_metadata = values["data"]["parts"][1]["metadata"]
    assert commit_metadata["oid"] == "abcdef123456"
    assert commit_metadata["author"]["internal_user_id"] == "usr_github_ba2slk"
    issue_comment_metadata = values["data"]["parts"][2]["metadata"]
    assert issue_comment_metadata["id"] == 200
    assert issue_comment_metadata["author"]["internal_user_id"] is None
    review_metadata = values["data"]["parts"][3]["metadata"]
    assert review_metadata["id"] == 300
    assert review_metadata["state"] == "APPROVED"
    review_comment_metadata = values["data"]["parts"][4]["metadata"]
    assert review_comment_metadata["id"] == 301
    assert review_comment_metadata["path"] == (
        "backend/catchup/prompts/rag/agent_limit_extraction.j2"
    )
    assert review_comment_metadata["line"] == 9
    assert review_comment_metadata["original_line"] == 8

    metadata = values["langchain_metadata"]
    assert set(metadata) == {"github_pr"}
    assert "contextual_content" not in metadata

    github_pr = metadata["github_pr"]
    assert github_pr["state"] == "merged"
    assert github_pr["review_decision"] == "APPROVED"
    assert github_pr["changed_files"] == 38
    assert github_pr["additions"] == 120
    assert github_pr["deletions"] == 50
    assert github_pr["author"] == {
        "external_user_id": "ba2slk",
        "internal_user_id": "usr_github_ba2slk",
    }
    assert github_pr["assignees"][0]["internal_user_id"] == "usr_github_maintainer"
    assert github_pr["requested_reviewers"][0]["internal_user_id"] is None
    assert len(github_pr["review_authors"]) == 1
    assert github_pr["review_authors"][0]["external_user_id"] == "reviewer"
    assert github_pr["review_authors"][0]["internal_user_id"] is None
    assert github_pr["merged_by"]["internal_user_id"] == "usr_github_ba2slk"
    assert github_pr["labels"] == [
        {"name": "refactor", "color": "a2eeef", "description": None}
    ]
    assert github_pr["milestone"]["title"] == "Prompt Work"
    for forbidden_field in (
        "merged",
        "commits_count",
        "comments_count",
        "commit_shas",
        "author_display",
        "assignee_displays",
        "reviewer_displays",
        "merged_by_display",
        "review_state",
    ):
        assert forbidden_field not in github_pr

    document = GithubPrV2RecordMapper().to_document(
        pr,
        owner="TeamCatchUp",
        repo="CatchUp",
        installation_id=118342815,
        content="LLM summarized pull request content",
        synced_at=_dt("2026-06-10T03:00:00+00:00"),
    )

    assert document.id == "github:pr:TeamCatchUp/CatchUp:724"
    assert document.page_content == "LLM summarized pull request content"
    assert document.metadata["scope_id"] == "118342815"
    assert document.metadata["target_id"] == "TeamCatchUp/CatchUp"
    assert document.metadata["github_pr"]["state"] == "merged"
