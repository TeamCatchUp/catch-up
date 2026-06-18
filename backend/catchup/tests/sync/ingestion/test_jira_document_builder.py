from __future__ import annotations

from catchup.sync.ingestion.document_builders.jira import JiraTransformer


class _FakeFieldMapper:
    def get_field_info_by_id(self, field_id: str):
        _ = field_id
        return None


def test_jira_transformer_builds_legacy_epic_document() -> None:
    issue_data = {
        "key": "GRT-EPIC",
        "id": "10002",
        "fields": {
            "project": {"key": "GRT", "name": "Growth"},
            "issuetype": {"name": "Epic"},
            "status": {
                "name": "To Do",
                "statusCategory": {"name": "To Do"},
            },
            "summary": "Migration epic",
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "Epic level migration plan."}
                        ],
                    }
                ],
            },
            "created": "2026-06-18T11:00:00.000+0900",
            "updated": "2026-06-18T11:01:00.000+0900",
        },
    }

    document = JiraTransformer(_FakeFieldMapper()).transform_issue(
        issue_data,
        "https://example.atlassian.net",
    )

    assert document.id == "jira:epic:GRT-EPIC"
    assert document.metadata["source"] == "jira"
    assert document.metadata["entity_type"] == "epic"
    assert document.metadata["issue_key"] == "GRT-EPIC"
    assert document.metadata["issue_type"] == "Epic"
    assert document.metadata["project_key"] == "GRT"
    assert document.metadata["record_id"] == "GRT-EPIC"
    assert "Epic level migration plan." in document.page_content
