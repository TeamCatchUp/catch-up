from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest
from langchain_core.documents import Document

from catchup.connectors.confluence.client import ConfluenceApiError
from catchup.connectors.confluence.schemas import ConfluenceCommentResponse
from catchup.connectors.confluence.schemas import ConfluencePageResponse
from catchup.sync.backfill.confluence_v2 import build_fetch_pending_seed_chunk_query
from catchup.sync.backfill.confluence_v2 import build_upsert_seed_rows_statement
from catchup.sync.ingestion.adapters.confluence.space_sync import (
    ConfluenceSpaceSyncDependencies,
)
from catchup.sync.ingestion.adapters.confluence.space_sync import (
    ConfluenceV2BackfillExecutionRequest,
)
from catchup.sync.ingestion.adapters.confluence.space_sync import (
    ConfluenceV2BackfillSeed,
)
from catchup.sync.ingestion.adapters.confluence.v2_backfill import (
    ConfluenceV2BackfillAdapter,
)
from catchup.sync.ingestion.adapters.confluence.v2_document_builder import (
    ConfluenceV2DocumentBuilder,
)
from catchup.sync.ingestion.document_builders.confluence import ConfluenceTransformer
from catchup.sync.ingestion.document_builders.confluence import (
    ConfluenceTransformResult,
)
from catchup.sync.ingestion.schemas import SyncWindow
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

    assert len(transform_result.v2_prepared_chunks) == 1

    first_chunk = transform_result.v2_prepared_chunks[0]
    assert first_chunk.chunk_count == 1
    assert first_chunk.section_hierarchy == ["Authentication"]
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

    assert len(parts) == 2
    assert parts[0]["type"] == "inline_comment"
    assert parts[0]["text"] == "Clarify token rotation."
    assert parts[0]["metadata"]["comment_id"] == "inline-1"
    assert parts[0]["metadata"]["selection"] == "tokens"
    assert parts[1]["type"] == "footer_comment"
    assert parts[1]["text"] == "Footer discussion."
    assert parts[1]["metadata"]["comment_id"] == "footer-1"
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


def test_confluence_inline_comment_falls_back_to_first_chunk_when_location_is_missing():
    transform_result = ConfluenceTransformer().transform_page(
        _page(),
        space_key="ENG",
        space_name="Engineering",
        inline_comments=(
            _comment(
                comment_id="inline-missing-location",
                text="Location metadata was lost.",
                properties={
                    "inline-marker-ref": "missing-ref",
                    "inline-original-selection": "text not present in body",
                },
            ),
        ),
        site_url="https://example.atlassian.net/wiki",
    )

    assert len(transform_result.documents) == 1
    assert len(transform_result.v2_prepared_chunks) == 1
    assert "Discussion" not in transform_result.documents[0].metadata[
        "section_hierarchy"
    ]
    assert "Location metadata was lost." in transform_result.documents[0].page_content

    document = ConfluenceV2RecordMapper().to_document(
        transform_result.v2_prepared_chunks[0],
        cloud_id="cloud-123",
    )
    parts = document.metadata["data"]["parts"]

    assert [part["type"] for part in parts] == ["inline_comment"]
    assert parts[0]["text"] == "Location metadata was lost."
    assert parts[0]["metadata"]["comment_id"] == "inline-missing-location"
    assert parts[0]["metadata"]["selection"] == "text not present in body"


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


def test_confluence_transform_logs_image_chunk_count():
    with patch("catchup.sync.ingestion.document_builders.confluence.logger") as logger:
        ConfluenceTransformer().transform_page(
            _page(),
            space_key="ENG",
            space_name="Engineering",
            site_url="https://example.atlassian.net/wiki",
        )

    matching_calls = [
        call
        for call in logger.info.call_args_list
        if call.args and call.args[0] == "confluence_transform_completed"
    ]
    assert matching_calls
    kwargs = matching_calls[-1].kwargs
    assert kwargs["image_chunk_count"] == 0
    assert "image_backed_count" not in kwargs


@pytest.mark.asyncio
async def test_confluence_v2_backfill_reuses_space_user_name_map_for_transform():
    class FakeConfluenceClient:
        async def get_page_by_id(
            self,
            record_id: str,
            *,
            body_format: str,
        ) -> dict:
            assert record_id == "1001"
            assert body_format == "storage"
            return _page().model_dump(mode="json", by_alias=True)

    seen_user_name_map: dict[str, str | None] | None = None
    dependencies = ConfluenceSpaceSyncDependencies(
        cloud_id="cloud-123",
        site_url="",
        client=FakeConfluenceClient(),
        repository=SimpleNamespace(),
        transformer=SimpleNamespace(),
    )
    adapter = ConfluenceV2BackfillAdapter(dependencies=dependencies)
    adapter._load_space_sync_context = AsyncMock(  # noqa: SLF001
        return_value=(
            {"ENG": "space-1"},
            {"ENG": "Engineering"},
            {"author-1": "Alice"},
        )
    )

    async def process_page(
        content: ConfluencePageResponse,
        *,
        space_key: str | None = None,
        space_name: str | None = None,
        user_name_map: dict[str, str | None] | None = None,
    ) -> ConfluenceTransformResult:
        nonlocal seen_user_name_map
        assert content.id == "1001"
        assert space_key == "ENG"
        assert space_name == "Engineering"
        seen_user_name_map = user_name_map
        return ConfluenceTransformResult(documents=[])

    adapter._process_page = process_page  # noqa: SLF001
    execution = ConfluenceV2BackfillExecutionRequest(
        tenant_id="tenant-1",
        space_key="ENG",
        record_type="page",
        seeds=(
            ConfluenceV2BackfillSeed(
                langchain_id="confluence:page:1001:chunk:0",
                record_id="1001",
                content="v1 contextual chunk",
                embedding=[0.1, 0.2],
            ),
        ),
    )
    sync_window = SyncWindow(
        window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 5, 2, tzinfo=timezone.utc),
    )

    fetched = await adapter.fetch(execution=execution, sync_window=sync_window)
    await adapter.transform(
        execution=execution,
        sync_window=sync_window,
        fetched=fetched,
    )

    assert fetched.space_id == "space-1"
    assert fetched.space_name == "Engineering"
    assert fetched.user_name_map == {"author-1": "Alice"}
    assert seen_user_name_map == {"author-1": "Alice"}


@pytest.mark.asyncio
async def test_confluence_v2_backfill_fetch_reraises_retryable_connector_errors():
    class FakeConfluenceClient:
        async def get_page_by_id(
            self,
            record_id: str,
            *,
            body_format: str,
        ) -> dict:
            _ = record_id, body_format
            raise ConfluenceApiError("retry later", status_code=503, retry_after=30)

    seed = ConfluenceV2BackfillSeed(
        langchain_id="confluence:page:1001:chunk:0",
        record_id="1001",
        content="v1 contextual chunk",
        embedding=[0.1, 0.2],
    )
    adapter = ConfluenceV2BackfillAdapter(
        dependencies=ConfluenceSpaceSyncDependencies(
            cloud_id="cloud-123",
            site_url="",
            client=FakeConfluenceClient(),
            repository=SimpleNamespace(),
            transformer=SimpleNamespace(),
        )
    )
    adapter._load_space_sync_context = AsyncMock(  # noqa: SLF001
        return_value=({"ENG": "space-1"}, {"ENG": "Engineering"}, {})
    )
    execution = ConfluenceV2BackfillExecutionRequest(
        tenant_id="cloud-123",
        space_key="ENG",
        record_type="page",
        seeds=(seed,),
    )
    sync_window = SyncWindow(
        window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 5, 2, tzinfo=timezone.utc),
    )

    with pytest.raises(ConfluenceApiError, match="retry later"):
        await adapter.fetch(execution=execution, sync_window=sync_window)


@pytest.mark.asyncio
async def test_confluence_v2_backfill_fetch_logs_non_retryable_record_failures():
    class FakeConfluenceClient:
        async def get_page_by_id(
            self,
            record_id: str,
            *,
            body_format: str,
        ) -> dict:
            _ = record_id, body_format
            raise ValueError("page payload broken")

    seed = ConfluenceV2BackfillSeed(
        langchain_id="confluence:page:1001:chunk:0",
        record_id="1001",
        content="v1 contextual chunk",
        embedding=[0.1, 0.2],
    )
    adapter = ConfluenceV2BackfillAdapter(
        dependencies=ConfluenceSpaceSyncDependencies(
            cloud_id="cloud-123",
            site_url="",
            client=FakeConfluenceClient(),
            repository=SimpleNamespace(),
            transformer=SimpleNamespace(),
        )
    )
    adapter._load_space_sync_context = AsyncMock(  # noqa: SLF001
        return_value=({"ENG": "space-1"}, {"ENG": "Engineering"}, {})
    )
    execution = ConfluenceV2BackfillExecutionRequest(
        tenant_id="cloud-123",
        space_key="ENG",
        record_type="page",
        seeds=(seed,),
    )
    sync_window = SyncWindow(
        window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 5, 2, tzinfo=timezone.utc),
    )

    with patch(
        "catchup.sync.ingestion.adapters.confluence.v2_backfill.logger"
    ) as logger:
        fetched = await adapter.fetch(execution=execution, sync_window=sync_window)

    assert fetched.records == ()
    assert fetched.v2_failed_ids == (seed.langchain_id,)
    logger.warning.assert_called_once_with(
        "confluence_v2_backfill_record_fetch_failed",
        connector="confluence",
        entity_type="page",
        scope_id="cloud-123",
        target_id="ENG",
        record_id="1001",
        failed_id_count=1,
        exception_type="ValueError",
        error="page payload broken",
        exc_info=True,
    )


@pytest.mark.asyncio
async def test_confluence_v2_backfill_transform_logs_non_retryable_record_failures():
    seed = ConfluenceV2BackfillSeed(
        langchain_id="confluence:page:1001:chunk:0",
        record_id="1001",
        content="v1 contextual chunk",
        embedding=[0.1, 0.2],
    )
    adapter = ConfluenceV2BackfillAdapter(
        dependencies=ConfluenceSpaceSyncDependencies(
            cloud_id="cloud-123",
            site_url="",
            client=SimpleNamespace(),
            repository=SimpleNamespace(),
            transformer=SimpleNamespace(),
        )
    )
    adapter._process_page = AsyncMock(  # noqa: SLF001
        side_effect=ValueError("transform broken")
    )
    execution = ConfluenceV2BackfillExecutionRequest(
        tenant_id="cloud-123",
        space_key="ENG",
        record_type="page",
        seeds=(seed,),
    )
    sync_window = SyncWindow(
        window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 5, 2, tzinfo=timezone.utc),
    )
    fetched = SimpleNamespace(
        records=(_page().model_dump(mode="json", by_alias=True),),
        v2_failed_ids=(),
        space_key="ENG",
        space_name="Engineering",
        user_name_map={},
    )

    with patch(
        "catchup.sync.ingestion.adapters.confluence.v2_backfill.logger"
    ) as logger:
        transformed = await adapter.transform(
            execution=execution,
            sync_window=sync_window,
            fetched=fetched,
        )

    assert transformed.items == ()
    assert transformed.v2_failed_ids == (seed.langchain_id,)
    logger.warning.assert_called_once_with(
        "confluence_v2_backfill_record_transform_failed",
        connector="confluence",
        entity_type="page",
        scope_id="cloud-123",
        target_id="ENG",
        record_id="1001",
        failed_id_count=1,
        exception_type="ValueError",
        error="transform broken",
        exc_info=True,
    )


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
    assert "metadata = '{}'::json" not in statement
    assert "title = ''" not in statement
    assert "body = ''" not in statement
    assert "data = '{}'::jsonb" not in statement
    assert "url = ''" not in statement


@pytest.mark.asyncio
async def test_confluence_v2_backfill_treats_missing_metadata_as_failed():
    class FakeVectorStore:
        async def upsert_documents(self, documents, ids, embeddings):
            _ = documents, embeddings
            return ids

    class FakeV2KnowledgeRepository:
        def __init__(self) -> None:
            self.namespace_checks = []

        async def find_missing_metadata_namespace_ids(self, ids, *, namespace):
            self.namespace_checks.append({"ids": list(ids), "namespace": namespace})
            return tuple(ids)

    seed = ConfluenceV2BackfillSeed(
        langchain_id="confluence:page:1001:chunk:0",
        record_id="1001",
        content="v1 contextual chunk",
        embedding=[0.1, 0.2],
    )
    vector_store = FakeVectorStore()
    v2_knowledge_repository = FakeV2KnowledgeRepository()
    adapter = ConfluenceV2BackfillAdapter(
        dependencies=ConfluenceSpaceSyncDependencies(
            cloud_id="cloud-123",
            site_url="",
            client=SimpleNamespace(),
            repository=SimpleNamespace(),
            transformer=SimpleNamespace(),
        ),
        vector_store=vector_store,
        v2_knowledge_repository=v2_knowledge_repository,
    )
    execution = ConfluenceV2BackfillExecutionRequest(
        tenant_id="cloud-123",
        space_key="ENG",
        record_type="page",
        seeds=(seed,),
    )
    document = Document(
        id=seed.langchain_id,
        page_content=seed.content,
        metadata={"confluence_page": {"content_type": "page"}},
    )

    persisted = await adapter.persist(
        execution=execution,
        sync_window=SyncWindow(
            window_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 5, 2, tzinfo=timezone.utc),
        ),
        transformed=SimpleNamespace(v2_failed_ids=(), v2_documents=(document,)),
        summary=SimpleNamespace(),
    )

    assert persisted.persisted_count == 0
    assert persisted.error_count == 1
    assert persisted.v2_failed_ids == (seed.langchain_id,)
    assert v2_knowledge_repository.namespace_checks == [
        {"ids": [seed.langchain_id], "namespace": "confluence_page"}
    ]
