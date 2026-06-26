from __future__ import annotations

from datetime import datetime
from datetime import timezone

from catchup.connectors.github.schemas import GithubIssue
from catchup.connectors.github.schemas import GithubIssueComment
from catchup.connectors.github.schemas import GithubLabel
from catchup.connectors.github.schemas import GithubMilestone
from catchup.connectors.github.schemas import GithubUser
from catchup.sync.ingestion.document_builders.github import GithubTransformer
from catchup.sync.ingestion.vector_records import GithubIssueV2RecordMapper


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def test_github_issue_parser_preserves_v2_source_fields() -> None:
    issue = GithubTransformer().parse_issue(
        {
            "number": 812,
            "url": "https://github.com/TeamCatchUp/CatchUp/issues/812",
            "title": "Migrate GitHub issue records to v2",
            "body": "Issue body.",
            "state": "OPEN",
            "stateReason": None,
            "author": {
                "__typename": "User",
                "databaseId": 1,
                "login": "ba2slk",
                "name": "TeamMemberC",
                "email": "ba2slk@example.com",
                "avatarUrl": "https://github.com/ba2slk.png",
                "url": "https://github.com/ba2slk",
            },
            "assignees": {
                "nodes": [
                    {
                        "__typename": "User",
                        "databaseId": 2,
                        "login": "maintainer",
                        "name": "Maintainer",
                    }
                ]
            },
            "labels": {
                "nodes": [
                    {
                        "name": "migration",
                        "color": "0e8a16",
                        "description": "data migration",
                    }
                ]
            },
            "milestone": {
                "number": 7,
                "title": "GitHub v2",
                "state": "OPEN",
                "dueOn": "2026-06-30T00:00:00Z",
            },
            "comments": {
                "totalCount": 51,
                "nodes": [
                    {
                        "id": "IC_kwDOIssueComment",
                        "author": {
                            "__typename": "User",
                            "databaseId": 3,
                            "login": "commenter",
                        },
                        "body": "Please keep v1 metadata stable.",
                        "createdAt": "2026-06-01T10:00:00Z",
                        "updatedAt": "2026-06-01T10:05:00Z",
                    }
                ],
            },
            "createdAt": "2026-06-01T09:00:00Z",
            "updatedAt": "2026-06-01T11:00:00Z",
            "closedAt": None,
        }
    )

    assert issue.state == "open"
    assert issue.author and issue.author.type == "User"
    assert issue.assignees[0].login == "maintainer"
    assert issue.labels[0].name == "migration"
    assert issue.milestone and issue.milestone.title == "GitHub v2"
    assert issue.comments_count == 51
    assert issue.comments[0].id == "IC_kwDOIssueComment"
    assert issue.comments[0].author and issue.comments[0].author.login == "commenter"


def test_github_issue_v2_mapper_builds_record_from_parsed_issue() -> None:
    issue = GithubIssue(
        number=812,
        html_url="https://github.com/TeamCatchUp/CatchUp/issues/812",
        title="Migrate GitHub issue records to v2",
        body="Issue body for migration.",
        state="open",
        state_reason=None,
        author=GithubUser(
            id=1,
            login="ba2slk",
            name="TeamMemberC",
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
                catchup_user_id="usr_github_maintainer",
            )
        ],
        labels=[GithubLabel(name="migration", color="0e8a16", description=None)],
        milestone=GithubMilestone(
            number=7,
            title="GitHub v2",
            state="OPEN",
            due_on=_dt("2026-06-30T00:00:00+00:00"),
        ),
        created_at=_dt("2026-06-01T09:00:00+00:00"),
        updated_at=_dt("2026-06-01T11:00:00+00:00"),
        comments_count=1,
        comments=[
            GithubIssueComment(
                id="IC_kwDOIssueComment",
                author=GithubUser(id=3, login="commenter", name="Commenter"),
                body="Please keep v1 metadata stable.",
                created_at=_dt("2026-06-01T10:00:00+00:00"),
                updated_at=_dt("2026-06-01T10:05:00+00:00"),
            )
        ],
    )

    record = GithubIssueV2RecordMapper().to_record(
        issue,
        owner="TeamCatchUp",
        repo="CatchUp",
        installation_id=118342815,
        content="summarized issue content",
        embedding=[0.0123, -0.0456, 0.0789],
        synced_at=_dt("2026-06-10T03:00:00+00:00"),
    )
    values = record.to_db_values()

    assert values["langchain_id"] == "github:issue:TeamCatchUp/CatchUp:812"
    assert values["content"] == "summarized issue content"
    assert values["entity_type"] == "issue"
    assert values["record_id"] == "812"
    assert values["scope_type"] == "installation"
    assert values["scope_id"] == "118342815"
    assert values["target_type"] == "repository"
    assert values["target_id"] == "TeamCatchUp/CatchUp"
    assert values["target_name"] == "TeamCatchUp/CatchUp"
    assert values["internal_author_id"] == "usr_github_ba2slk"
    assert values["body"] == (
        "Issue body for migration.\n\nPlease keep v1 metadata stable."
    )
    assert [part["type"] for part in values["data"]["parts"]] == [
        "issue_body",
        "issue_comment",
    ]
    assert values["data"]["parts"][1]["metadata"]["id"] == "IC_kwDOIssueComment"
    assert (
        values["data"]["parts"][1]["metadata"]["author"]["external_user_id"]
        == "commenter"
    )

    metadata = values["langchain_metadata"]
    assert set(metadata) == {"github_issue"}
    assert "contextual_content" not in metadata

    github_issue = metadata["github_issue"]
    assert github_issue["state"] == "open"
    assert github_issue["author"] == {
        "external_user_id": "ba2slk",
        "internal_user_id": "usr_github_ba2slk",
    }
    assert github_issue["assignees"][0] == {
        "external_user_id": "maintainer",
        "internal_user_id": "usr_github_maintainer",
    }
    assert github_issue["labels"] == [
        {"name": "migration", "color": "0e8a16", "description": None}
    ]
    assert github_issue["milestone"]["title"] == "GitHub v2"
    assert "comments_count" not in github_issue
    for forbidden_field in (
        "raw",
        "pagination",
        "body_text_anchor",
        "author_display",
        "assignee_displays",
        "review_state",
    ):
        assert forbidden_field not in github_issue

    document = GithubIssueV2RecordMapper().to_document(
        issue,
        owner="TeamCatchUp",
        repo="CatchUp",
        installation_id=118342815,
        content="summarized issue content",
        synced_at=_dt("2026-06-10T03:00:00+00:00"),
    )

    assert document.id == "github:issue:TeamCatchUp/CatchUp:812"
    assert document.page_content == "summarized issue content"
    assert document.metadata["github_issue"]["state"] == "open"
