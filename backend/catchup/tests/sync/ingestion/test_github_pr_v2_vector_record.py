from __future__ import annotations

from datetime import datetime
from datetime import timezone

from catchup.sync.ingestion.vector_records.github_pr import GithubPrData
from catchup.sync.ingestion.vector_records.github_pr import GithubPrDataPart
from catchup.sync.ingestion.vector_records.github_pr import GithubPrLabelMetadata
from catchup.sync.ingestion.vector_records.github_pr import GithubPrMetadata
from catchup.sync.ingestion.vector_records.github_pr import GithubPrMilestoneMetadata
from catchup.sync.ingestion.vector_records.github_pr import GithubPrUserMetadata
from catchup.sync.ingestion.vector_records.github_pr import GithubPrVectorRecord


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def test_github_pr_v2_record_serializes_contract_without_contextual_content() -> None:
    record = GithubPrVectorRecord(
        langchain_id="github:pr:TeamCatchUp/CatchUp:724",
        content="Summarized pull request content",
        embedding=[0.0123, -0.0456, 0.0789],
        source="github",
        entity_type="pr",
        record_id="724",
        scope_type="installation",
        scope_id="118342815",
        target_type="repository",
        target_id="TeamCatchUp/CatchUp",
        target_name="TeamCatchUp/CatchUp",
        internal_author_id="usr_github_ba2slk",
        title="[CAM-37] refactor backend prompt pipeline",
        body=(
            "PR body: Refactor prompt pipeline.\n\n"
            "test(backend): add prompt rendering tests\n\n"
            "Code Review\n\n"
            "duplicated instruction"
        ),
        data=GithubPrData(
            parts=[
                GithubPrDataPart(
                    type="pr_body",
                    text="PR body: Refactor prompt pipeline.",
                    metadata={},
                ),
                GithubPrDataPart(
                    type="commit",
                    text="test(backend): add prompt rendering tests",
                    metadata={
                        "oid": "abcdef123456",
                        "author": {
                            "login": "ba2slk",
                            "name": "팀원C",
                            "catchup_user_id": "usr_github_ba2slk",
                        },
                    },
                ),
                GithubPrDataPart(
                    type="review",
                    text="Code Review",
                    metadata={
                        "id": 100,
                        "state": "COMMENTED",
                        "author": {
                            "login": "reviewer",
                            "name": "Reviewer",
                            "catchup_user_id": None,
                        },
                        "submitted_at": _dt("2026-05-19T20:15:00+00:00"),
                    },
                ),
                GithubPrDataPart(
                    type="review_comment",
                    text="duplicated instruction",
                    metadata={
                        "id": 101,
                        "author": {
                            "login": "reviewer",
                            "name": "Reviewer",
                            "catchup_user_id": None,
                        },
                        "path": "backend/catchup/prompts/rag/agent_limit_extraction.j2",
                        "line": 9,
                        "created_at": _dt("2026-05-19T20:16:00+00:00"),
                    },
                ),
            ]
        ),
        url="https://github.com/TeamCatchUp/CatchUp/pull/724",
        created_at=_dt("2026-05-19T20:13:01+00:00"),
        updated_at=_dt("2026-05-19T20:19:53+00:00"),
        synced_at=_dt("2026-06-10T03:00:00+00:00"),
        github_pr=GithubPrMetadata(
            state="merged",
            merged_at=_dt("2026-05-19T20:13:11+00:00"),
            closed_at=_dt("2026-05-19T20:13:11+00:00"),
            base_ref="develop",
            head_ref="refactor/backend/CAM-37-xml-based-prompt-engineering",
            is_draft=False,
            review_decision="COMMENTED",
            changed_files=38,
            author=GithubPrUserMetadata(
                login="ba2slk",
                name="팀원C",
                email="",
                avatar_url="https://github.com/ba2slk.png",
                type="User",
                url="https://github.com/ba2slk",
                catchup_user_id="usr_github_ba2slk",
            ),
            assignees=[],
            requested_reviewers=[],
            review_authors=[
                GithubPrUserMetadata(
                    login="reviewer",
                    name="Reviewer",
                    catchup_user_id=None,
                )
            ],
            merged_by=GithubPrUserMetadata(
                login="ba2slk",
                name="팀원C",
                email="",
                avatar_url="https://github.com/ba2slk.png",
                catchup_user_id="usr_github_ba2slk",
            ),
            labels=[
                GithubPrLabelMetadata(
                    name="refactor",
                    color="a2eeef",
                    description="prompt engineering refactor",
                )
            ],
            milestone=GithubPrMilestoneMetadata(
                number=37,
                title="XML-based Prompt Engineering",
                state="OPEN",
                due_on=_dt("2026-06-30T00:00:00+00:00"),
            ),
            additions=120,
            deletions=50,
        ),
    )

    values = record.to_db_values()
    metadata = values["langchain_metadata"]

    assert values["langchain_id"] == "github:pr:TeamCatchUp/CatchUp:724"
    assert values["content"] == "Summarized pull request content"
    assert values["source"] == "github"
    assert values["entity_type"] == "pr"
    assert values["record_id"] == "724"
    assert values["scope_type"] == "installation"
    assert values["scope_id"] == "118342815"
    assert values["target_type"] == "repository"
    assert values["target_id"] == "TeamCatchUp/CatchUp"
    assert values["target_name"] == "TeamCatchUp/CatchUp"
    assert values["internal_author_id"] == "usr_github_ba2slk"
    assert values["body"] == (
        "PR body: Refactor prompt pipeline.\n\n"
        "test(backend): add prompt rendering tests\n\n"
        "Code Review\n\n"
        "duplicated instruction"
    )
    assert "Commit messages:" not in values["body"]
    assert "Review bodies:" not in values["body"]
    assert "backend/catchup/prompts" not in values["body"]
    assert values["data"]["parts"][1]["metadata"]["oid"] == "abcdef123456"
    assert (
        values["data"]["parts"][3]["metadata"]["path"]
        == "backend/catchup/prompts/rag/agent_limit_extraction.j2"
    )

    assert set(metadata) == {"github_pr"}
    assert "contextual_content" not in metadata
    for duplicated_field in (
        "owner",
        "repo",
        "number",
        "installation_id",
        "source",
        "entity_type",
        "record_id",
        "target_id",
    ):
        assert duplicated_field not in metadata["github_pr"]

    github_pr = metadata["github_pr"]
    assert github_pr["state"] == "merged"
    assert github_pr["author"]["login"] == "ba2slk"
    assert github_pr["author"]["avatar_url"] == "https://github.com/ba2slk.png"
    assert github_pr["author"]["catchup_user_id"] == "usr_github_ba2slk"
    assert github_pr["review_authors"][0]["catchup_user_id"] is None
    assert github_pr["labels"] == [
        {
            "name": "refactor",
            "color": "a2eeef",
            "description": "prompt engineering refactor",
        }
    ]
    assert github_pr["milestone"]["title"] == "XML-based Prompt Engineering"
    assert github_pr["additions"] == 120
    assert github_pr["deletions"] == 50
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
