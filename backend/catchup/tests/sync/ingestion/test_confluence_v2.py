from __future__ import annotations

from catchup.connectors.confluence.schemas import ConfluenceCommentResponse
from catchup.connectors.confluence.schemas import ConfluencePageResponse
from catchup.sync.backfill.confluence_v2 import build_fetch_pending_seed_chunk_query
from catchup.sync.backfill.confluence_v2 import build_upsert_seed_rows_statement
from catchup.sync.ingestion.adapters.confluence.v2_document_builder import (
    ConfluenceV2DocumentBuilder,
)
from catchup.sync.ingestion.document_builders.confluence import ConfluenceTransformer
from catchup.sync.ingestion.vector_records import ConfluenceV2RecordMapper


def _page() -> ConfluencePageResponse:
    return ConfluencePageResponse.model_validate(
        {
            "id": "1001",
            "status": "current",
            "title": "API Design Guide",
            "spaceId": "space-1",
            "parentId": "parent-1",
            "parentType": "page",
            "position": 3,
            "authorId": "author-1",
            "ownerId": "owner-1",
            "createdAt": "2026-05-01T00:00:00.000Z",
            "version": {
                "number": 7,
                "createdAt": "2026-05-02T00:00:00.000Z",
                "authorId": "author-2",
                "message": "Updated section",
                "minorEdit": False,
            },
            "body": {
                "storage": {
                    "representation": "storage",
                    "value": (
                        "<h2>Authentication</h2>"
                        "<p>Use OAuth "
                        "<ac:inline-comment-marker ac:ref=\"ref-1\">tokens"
                        "</ac:inline-comment-marker> for API calls.</p>"
                    ),
                }
            },
            "_links": {"webui": "/spaces/ENG/pages/1001/API+Design+Guide"},
        }
    )


def _comment(
    *,
    comment_id: str,
    text: str,
    author_id: str = "commenter-1",
    properties: dict | None = None,
) -> ConfluenceCommentResponse:
    return ConfluenceCommentResponse.model_validate(
        {
            "id": comment_id,
            "status": "current",
            "authorId": author_id,
            "createdAt": "2026-05-03T00:00:00.000Z",
            "version": {"number": 1, "createdAt": "2026-05-03T01:00:00.000Z"},
            "body": {
                "storage": {
                    "representation": "storage",
                    "value": f"<p>{text}</p>",
                }
            },
            "properties": properties or {},
        }
    )


def test_confluence_v2_mapper_builds_clean_chunk_contract_without_duplicates():
    transform_result = ConfluenceTransformer().transform_page(
        _page(),
        space_key="ENG",
        space_name="Engineering",
        labels=["api", "oauth"],
        inline_comments=(
            _comment(
                comment_id="inline-1",
                text="Clarify token rotation.",
                properties={
                    "inline-marker-ref": "ref-1",
                    "inline-original-selection": "tokens",
                },
            ),
        ),
        footer_comments=(
            _comment(comment_id="footer-1", text="Footer discussion."),
        ),
        site_url="https://example.atlassian.net/wiki",
        user_name_map={"author-1": "Alice"},
    )

    assert len(transform_result.v2_prepared_chunks) == 2

    first_chunk = transform_result.v2_prepared_chunks[0]
    document = ConfluenceV2RecordMapper().to_document(
        first_chunk,
        cloud_id="cloud-123",
        content="v1 contextual chunk",
    )

    metadata = document.metadata
    domain_metadata = metadata["confluence_page"]
    parts = metadata["data"]["parts"]

    assert document.id == "confluence:page:1001:chunk:0"
    assert document.page_content == "v1 contextual chunk"
    assert metadata["source"] == "confluence"
    assert metadata["entity_type"] == "page"
    assert metadata["record_id"] == "1001"
    assert metadata["scope_type"] == "cloud"
    assert metadata["scope_id"] == "cloud-123"
    assert metadata["target_type"] == "space"
    assert metadata["target_id"] == "ENG"
    assert metadata["target_name"] == "Engineering"
    assert metadata["title"] == "API Design Guide"
    assert metadata["body"] == "Use OAuth tokens for API calls."
    assert "API Design Guide" not in metadata["body"]
    assert "Engineering" not in metadata["body"]
    assert "Clarify token rotation" not in metadata["body"]
    assert "Comment" not in metadata["body"]

    assert set(domain_metadata) == {
        "status",
        "space",
        "hierarchy",
        "author",
        "owner_id",
        "version",
        "labels",
        "chunk",
    }
    assert "schema_version" not in domain_metadata
    assert domain_metadata["space"] == {"space_id": "space-1"}
    assert domain_metadata["hierarchy"] == {
        "parent_page_id": "parent-1",
        "parent_type": "page",
        "position": 3,
    }
    assert domain_metadata["chunk"]["section_hierarchy"] == ["Authentication"]

    assert len(parts) == 1
    assert parts[0]["type"] == "inline_comment"
    assert parts[0]["text"] == "Clarify token rotation."
    assert parts[0]["metadata"]["comment_id"] == "inline-1"
    assert parts[0]["metadata"]["selection"] == "tokens"
    for part in parts:
        for duplicated_field in (
            "record_id",
            "content_id",
            "page_id",
            "space_key",
            "space_name",
            "title",
        ):
            assert duplicated_field not in part["metadata"]


def test_confluence_v2_builder_reports_validation_failures_without_raising():
    transform_result = ConfluenceTransformer().transform_page(
        _page(),
        space_key="ENG",
        space_name="Engineering",
        site_url="https://example.atlassian.net/wiki",
    )
    documents, failed_ids = ConfluenceV2DocumentBuilder().build_from_transform_results(
        cloud_id="",
        transform_results=(transform_result,),
    )

    assert documents == []
    assert failed_ids == ("confluence:page:1001:chunk:0",)


def test_confluence_v2_backfill_sql_casts_nullable_cursor_parameters():
    query = str(build_fetch_pending_seed_chunk_query("page"))

    assert "CAST(:after_record_id AS text) IS NULL" in query
    assert "record_id > CAST(:after_record_id AS text)" in query
    assert "CAST(:after_langchain_id AS text)" in query


def test_confluence_v2_seed_sql_uses_empty_metadata_json_for_seed_rows():
    statement = str(build_upsert_seed_rows_statement("blogpost"))

    assert "'confluence'" in statement
    assert "'blogpost'" in statement
    assert "'{}'::json" in statement
    assert "'{}'::jsonb" in statement
