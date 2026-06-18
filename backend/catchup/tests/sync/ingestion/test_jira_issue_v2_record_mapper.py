from __future__ import annotations

from datetime import datetime
from datetime import timezone

from catchup.connectors.jira.schemas import JiraAttachment
from catchup.connectors.jira.schemas import JiraComment
from catchup.connectors.jira.schemas import JiraInlineAttachment
from catchup.connectors.jira.schemas import JiraIssue
from catchup.connectors.jira.schemas import JiraLinkedIssue
from catchup.connectors.jira.schemas import JiraMention
from catchup.connectors.jira.schemas import JiraSprintInfo
from catchup.connectors.jira.schemas import JiraUser
from catchup.sync.ingestion.vector_records import JiraIssueV2RecordMapper


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def _issue() -> JiraIssue:
    author = JiraUser(
        account_id="acc-author",
        display_name="Author User",
        email_address="author@example.com",
        avatar_url="https://avatar.example/author.png",
        active=True,
        catchup_user_id="usr_author",
    )
    assignee = JiraUser(
        account_id="acc-assignee",
        display_name="Assignee",
        catchup_user_id="usr_assignee",
    )
    return JiraIssue(
        key="CATCH-145",
        id="100145",
        url="https://catchup.atlassian.net/browse/CATCH-145",
        project_key="CATCH",
        project_name="CatchUp",
        issue_type="Task",
        status="In Progress",
        status_category="In Progress",
        priority="High",
        resolution=None,
        summary="Implement Jira v2 records",
        description="Description from ADF as plain text.",
        assignee=assignee,
        reporter=author,
        creator=author,
        created_at=_dt("2026-06-01T09:00:00+00:00"),
        updated_at=_dt("2026-06-01T11:00:00+00:00"),
        due_date="2026-06-30",
        parent_key="CATCH-1",
        parent_name="Migration epic",
        subtask_keys=["CATCH-146"],
        sprint=JiraSprintInfo(id=7, name="Sprint 7", state="active"),
        story_points=3,
        components=["backend"],
        labels=["vector-store"],
        fix_versions=["v2"],
        affects_versions=["v1"],
        time_spent_seconds=3600,
        linked_issues=[
            JiraLinkedIssue(
                id="100044",
                key="CATCH-44",
                summary="Related issue",
                status="Done",
                issue_type="Bug",
                priority="Medium",
                link_type="relates to",
                direction="outward",
                url="https://catchup.atlassian.net/browse/CATCH-44",
            )
        ],
        comments=[
            JiraComment(
                id="comment-1",
                author="Commenter",
                author_account_id="acc-commenter",
                author_user=JiraUser(
                    account_id="acc-commenter",
                    display_name="Commenter",
                ),
                body="Please keep the v1 summary stable.",
                created=_dt("2026-06-01T10:00:00+00:00"),
                updated=_dt("2026-06-01T10:05:00+00:00"),
                visibility="Developers",
                mentions=[
                    JiraMention(
                        account_id="acc-author",
                        display_name="Author User",
                        text="@Author User",
                    )
                ],
                inline_attachments=[
                    JiraInlineAttachment(
                        id="media-1",
                        collection="jira",
                        type="image",
                        alt="diagram",
                        filename="diagram.png",
                        url="https://media.example/diagram.png",
                    )
                ],
            )
        ],
        attachments=[
            JiraAttachment(
                id="att-1",
                filename="spec.pdf",
                author="Author User",
                author_account_id="acc-author",
                author_user=author,
                mime_type="application/pdf",
                url="https://files.example/spec.pdf",
                thumbnail_url="https://files.example/spec-thumb.png",
                created=_dt("2026-06-01T09:30:00+00:00"),
                size=2048,
            )
        ],
        custom_fields={"Raw custom field": {"must": "not leak"}},
    )


def test_jira_issue_v2_mapper_builds_record_from_parsed_issue() -> None:
    record = JiraIssueV2RecordMapper().to_record(
        _issue(),
        cloud_id="cloud-1",
        content="summarized jira issue content",
        embedding=[0.1, 0.2, 0.3],
        synced_at=_dt("2026-06-10T03:00:00+00:00"),
    )
    values = record.to_db_values()

    assert values["langchain_id"] == "jira:issue:cloud-1:CATCH:CATCH-145"
    assert values["content"] == "summarized jira issue content"
    assert values["source"] == "jira"
    assert values["entity_type"] == "issue"
    assert values["record_id"] == "CATCH-145"
    assert values["scope_type"] == "cloud"
    assert values["scope_id"] == "cloud-1"
    assert values["target_type"] == "project"
    assert values["target_id"] == "CATCH"
    assert values["target_name"] == "CatchUp"
    assert values["internal_author_id"] == "usr_assignee"
    assert values["title"] == "Implement Jira v2 records"
    assert "Implement Jira v2 records" not in values["body"]
    assert "Description from ADF as plain text." in values["body"]

    assert [part["type"] for part in values["data"]["parts"]] == [
        "issue_description",
        "issue_comment",
        "linked_issue",
        "attachment",
        "inline_attachment",
    ]
    comment_part = values["data"]["parts"][1]
    assert comment_part["metadata"]["id"] == "comment-1"
    assert comment_part["metadata"]["author"]["account_id"] == "acc-commenter"
    assert set(comment_part["metadata"]["author"]) == {
        "account_id",
        "display_name",
        "email_address",
        "avatar_url",
        "catchup_user_id",
    }
    assert comment_part["metadata"]["mentions"][0]["text"] == "@Author User"
    attachment_part = values["data"]["parts"][3]
    assert attachment_part["metadata"]["comment_id"] is None
    assert set(attachment_part["metadata"]["author"]) == {
        "account_id",
        "display_name",
        "email_address",
        "avatar_url",
        "catchup_user_id",
    }
    assert "active" not in attachment_part["metadata"]["author"]
    inline_attachment_part = values["data"]["parts"][4]
    assert inline_attachment_part["metadata"]["comment_id"] == "comment-1"
    assert set(inline_attachment_part["metadata"]["comment_author"]) == {
        "account_id",
        "display_name",
        "email_address",
        "avatar_url",
        "catchup_user_id",
    }

    metadata = values["langchain_metadata"]
    assert set(metadata) == {"jira_issue"}
    jira_issue = metadata["jira_issue"]
    assert "issue_key" not in jira_issue
    assert "project_key" not in jira_issue
    assert "project_name" not in jira_issue
    assert jira_issue["type"] == "Task"
    assert "issue_type" not in jira_issue
    assert jira_issue["assignee"]["catchup_user_id"] == "usr_assignee"
    assert jira_issue["reporter"]["catchup_user_id"] == "usr_author"
    assert set(jira_issue["reporter"]) == {
        "account_id",
        "display_name",
        "email_address",
        "avatar_url",
        "catchup_user_id",
    }
    assert "active" not in jira_issue["reporter"]
    assert jira_issue["sprint"] == {"id": 7, "name": "Sprint 7", "state": "active"}
    for forbidden_field in (
        "raw",
        "fields",
        "adf",
        "contextual_content",
        "custom_fields",
        "attachments",
        "issue_type",
        "issue_key",
        "project_key",
        "project_name",
        "comments_count",
        "attachments_count",
        "linked_issue_count",
    ):
        assert forbidden_field not in jira_issue
    assert "issue_key" not in values["data"]["parts"][0]["metadata"]
    assert "project_key" not in values["data"]["parts"][0]["metadata"]

    document = JiraIssueV2RecordMapper().to_document(
        _issue(),
        cloud_id="cloud-1",
        content="summarized jira issue content",
        synced_at=_dt("2026-06-10T03:00:00+00:00"),
    )

    assert document.id == "jira:issue:cloud-1:CATCH:CATCH-145"
    assert document.page_content == "summarized jira issue content"
    assert document.metadata["record_id"] == "CATCH-145"
    assert document.metadata["target_id"] == "CATCH"
    assert document.metadata["target_name"] == "CatchUp"
    assert document.metadata["internal_author_id"] == "usr_assignee"
    assert "issue_key" not in document.metadata["jira_issue"]


def test_jira_issue_v2_mapper_builds_epics_as_canonical_issue_rows() -> None:
    epic = _issue().model_copy(
        update={
            "key": "CATCH-1",
            "id": "100001",
            "issue_type": "Epic",
            "summary": "Migration epic",
            "description": "Epic level migration plan.",
            "parent_key": None,
            "parent_name": None,
        }
    )

    document = JiraIssueV2RecordMapper().to_document(
        epic,
        cloud_id="cloud-1",
        content="summarized jira epic content",
        synced_at=_dt("2026-06-10T03:00:00+00:00"),
    )

    assert document.id == "jira:issue:cloud-1:CATCH:CATCH-1"
    assert document.page_content == "summarized jira epic content"
    assert document.metadata["source"] == "jira"
    assert document.metadata["entity_type"] == "issue"
    assert document.metadata["record_id"] == "CATCH-1"
    assert document.metadata["target_id"] == "CATCH"
    assert document.metadata["target_name"] == "CatchUp"
    assert document.metadata["title"] == "Migration epic"
    assert "Migration epic" not in document.metadata["body"]
    assert "Epic level migration plan." in document.metadata["body"]

    epic_metadata = document.metadata["jira_issue"]
    assert epic_metadata["issue_id"] == "100001"
    assert epic_metadata["type"] == "Epic"
    assert "epic_id" not in epic_metadata
    assert "issue_type" not in epic_metadata
    for forbidden_field in (
        "issue_key",
        "project_key",
        "project_name",
        "source",
        "entity_type",
        "record_id",
        "scope_id",
        "target_id",
        "target_name",
        "custom_fields",
    ):
        assert forbidden_field not in epic_metadata
    assert "jira_epic" not in document.metadata
