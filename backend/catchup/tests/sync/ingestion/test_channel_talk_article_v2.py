from __future__ import annotations

import json
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleState,
)
from catchup.sync.backfill.channel_talk_document_article_v2 import (
    ChannelTalkArticleV1Target,
)
from catchup.sync.backfill.channel_talk_document_article_v2 import (
    ChannelTalkArticleV2BackfillService,
)
from catchup.sync.backfill.channel_talk_document_article_v2 import (
    build_channel_talk_document_article_mark_finished_statement,
)
from catchup.sync.backfill.channel_talk_document_article_v2 import (
    build_channel_talk_document_article_v1_target_query,
)
from catchup.sync.backfill.channel_talk_document_article_v2 import (
    build_channel_talk_document_article_v1_target_seed_query,
)
from catchup.sync.backfill.channel_talk_document_article_v2 import (
    build_fetch_seeded_seed_chunk_query,
)
from catchup.sync.backfill.channel_talk_document_article_v2 import (
    build_upsert_seed_rows_statement,
)
from catchup.sync.ingestion.adapters.channel_talk.article_full_sync import (
    ChannelTalkArticleFullSyncIngestionAdapter,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleFullSyncFetchResult,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleV2BackfillExecutionRequest,
)
from catchup.sync.ingestion.adapters.channel_talk.article_models import (
    ChannelTalkArticleV2BackfillSeed,
)
from catchup.sync.ingestion.adapters.channel_talk.article_v2_backfill import (
    ChannelTalkArticleV2BackfillAdapter,
)
from catchup.sync.ingestion.adapters.channel_talk.article_v2_document_builder import (
    ChannelTalkArticleV2DocumentBuilder,
)
from catchup.sync.ingestion.pipeline import run_sync_ingestion
from catchup.sync.ingestion.vector_records import (
    ChannelTalkDocumentArticleV2RecordMapper,
)
from catchup.tests.sync.ingestion.test_channel_talk_article_full_sync_adapter import (
    _article_view,
)
from catchup.tests.sync.ingestion.test_channel_talk_article_full_sync_adapter import (
    _bundle,
)
from catchup.tests.sync.ingestion.test_channel_talk_article_full_sync_adapter import (
    _execution,
)
from catchup.tests.sync.ingestion.test_channel_talk_article_full_sync_adapter import (
    _revision_view,
)
from catchup.tests.sync.ingestion.test_channel_talk_article_full_sync_adapter import (
    _window,
)


class _DualWriteArticleRepository:
    def __init__(self) -> None:
        self.initialized = False
        self.deleted_prefixes: list[str] = []
        self.deleted_ids: list[str] = []
        self.added_documents = []
        self.stored_documents = []
        self.stored_embeddings = []

    async def initialize(self, _ensure_indices) -> None:
        self.initialized = True

    async def delete_by_id_prefix(self, prefix: str) -> None:
        self.deleted_prefixes.append(prefix)

    async def add_documents(self, documents, ids=None):
        self.added_documents = list(documents)
        return list(ids or [])

    async def generate_embeddings(self, documents, audit_context=None, context=None):
        _ = audit_context
        _ = context
        return [[0.75] for _document in documents]

    async def delete_documents(self, ids):
        self.deleted_ids = list(ids)

    async def store_with_embeddings(
        self,
        documents,
        embeddings,
        ids,
        audit_context=None,
        context=None,
    ):
        _ = audit_context
        _ = context
        self.stored_documents = list(documents)
        self.stored_embeddings = list(embeddings)
        return list(ids)


class _FakeChannelTalkArticleAuthorResolver:
    def __init__(self, resolved_id: str | None = "42") -> None:
        self.resolved_id = resolved_id
        self.author_ids: list[str | None] = []

    def resolve_catchup_user_id(self, db, author_id):
        _ = db
        self.author_ids.append(author_id)
        return self.resolved_id


def _published_bundle(article_id: str = "article-1"):
    return _bundle(
        article_id=article_id,
        state=ChannelTalkDocumentArticleState.PUBLISHED,
        detail=_article_view(
            article_id=article_id,
            state=ChannelTalkDocumentArticleState.PUBLISHED,
            body_html="<p>Current body should not be used</p>",
        ),
        published_revision=_revision_view(
            article_id=article_id,
            body_html="<h1>Refunds</h1><p>Published body text.</p>",
        ),
    )


def _v2_document_builder(
    resolver: _FakeChannelTalkArticleAuthorResolver | None = None,
) -> ChannelTalkArticleV2DocumentBuilder:
    return ChannelTalkArticleV2DocumentBuilder(
        author_resolver=resolver or _FakeChannelTalkArticleAuthorResolver(),
        session_factory=lambda: nullcontext(object()),
    )


@pytest.mark.asyncio
async def test_channel_talk_article_v2_mapper_builds_contract_without_duplicates():
    adapter = ChannelTalkArticleFullSyncIngestionAdapter()
    transformed = await adapter.transform(
        execution=_execution(),
        sync_window=_window(),
        fetched=ChannelTalkArticleFullSyncFetchResult(
            channel_id="channel-123",
            space_id="space-123",
            language="ko",
            bundles=(_published_bundle(),),
            fetched_count=1,
            fetched_article_ids=("article-1",),
        ),
    )
    prepared = transformed.documents[0]

    document = ChannelTalkDocumentArticleV2RecordMapper().to_document(prepared)

    metadata = document.metadata
    domain_metadata = metadata["channel_talk_document_article"]

    assert document.id == prepared.document_id
    assert document.page_content == prepared.page_content
    assert metadata["source"] == "channel_talk"
    assert metadata["entity_type"] == "document_article"
    assert metadata["record_id"] == "article-1"
    assert metadata["scope_type"] == "channel"
    assert metadata["scope_id"] == "channel-123"
    assert metadata["target_type"] == "document_space"
    assert metadata["target_id"] == "space-123"
    assert metadata["target_name"] == "Help Center"
    assert metadata["internal_author_id"] is None
    assert metadata["title"] == "Published refund policy"
    assert metadata["body"] == "# Refunds\n\nPublished body text."
    assert metadata["data"] == {"parts": []}
    assert prepared.chunk_body_text == metadata["body"]
    assert "Published refund policy" not in metadata["body"]
    assert "channel-123" not in metadata["body"]
    assert "space-123" not in metadata["body"]
    assert "article-1" not in metadata["body"]

    assert set(domain_metadata) == {
        "schema_version",
        "author",
        "taxonomy",
        "publication",
    }
    for duplicated_field in (
        "article_id",
        "channel_id",
        "space_id",
        "space_name",
        "source",
        "entity_type",
        "record_id",
        "scope_id",
        "target_id",
        "target_name",
        "state",
        "language",
        "slug",
        "subtitle",
        "summary",
        "chunk",
    ):
        assert duplicated_field not in domain_metadata
    assert domain_metadata["schema_version"] == 2
    assert domain_metadata["author"]["author_id"] == "author-1"
    assert domain_metadata["author"]["author_name"] == "Writer Kim"
    assert set(domain_metadata["author"]) == {"author_id", "author_name"}
    assert "raw_payload" not in str(metadata)
    assert "signed" not in str(metadata)


@pytest.mark.asyncio
async def test_channel_talk_article_v2_mapper_allows_empty_body_with_seed_content():
    adapter = ChannelTalkArticleFullSyncIngestionAdapter()
    transformed = await adapter.transform(
        execution=_execution(),
        sync_window=_window(),
        fetched=ChannelTalkArticleFullSyncFetchResult(
            channel_id="channel-123",
            space_id="space-123",
            language="ko",
            bundles=(_published_bundle(),),
            fetched_count=1,
            fetched_article_ids=("article-1",),
        ),
    )
    prepared = transformed.documents[0].model_copy(
        update={
            "page_content": "   ",
            "chunk_body_text": "   ",
        }
    )
    logical = prepared.logical_metadata
    core = logical.document_article_core
    prepared = prepared.model_copy(
        update={
            "logical_metadata": logical.model_copy(
                update={
                    "document_article_core": core.model_copy(
                        update={
                            "article": core.article.model_copy(
                                update={"body_text": None}
                            )
                        }
                    )
                }
            )
        }
    )

    document = ChannelTalkDocumentArticleV2RecordMapper().to_document(
        prepared,
        content="preserved v1 seed content",
    )

    assert document.page_content == "preserved v1 seed content"
    assert document.metadata["body"] == ""
    assert document.metadata["data"] == {"parts": []}


@pytest.mark.asyncio
async def test_channel_talk_article_v2_mapper_uses_raw_text_fallbacks_only():
    adapter = ChannelTalkArticleFullSyncIngestionAdapter()
    transformed = await adapter.transform(
        execution=_execution(),
        sync_window=_window(),
        fetched=ChannelTalkArticleFullSyncFetchResult(
            channel_id="channel-123",
            space_id="space-123",
            language="ko",
            bundles=(
                _bundle(
                    article_id="article-1",
                    state=ChannelTalkDocumentArticleState.PUBLISHED,
                    detail=_article_view(
                        article_id="article-1",
                        state=ChannelTalkDocumentArticleState.PUBLISHED,
                        title="",
                        body_html="<p>Body first line.</p>",
                    ),
                    published_revision=_revision_view(
                        article_id="article-1",
                        title="",
                        body_html="<p>Body first line.</p>",
                    ),
                ),
            ),
            fetched_count=1,
            fetched_article_ids=("article-1",),
        ),
    )
    prepared = transformed.documents[0]
    logical = prepared.logical_metadata
    core = logical.document_article_core
    prepared = prepared.model_copy(
        update={
            "page_content": "Synthetic chunk heading\n\nSecond line.",
            "chunk_body_text": "Body first line.\nSecond line.",
            "logical_metadata": logical.model_copy(
                update={
                    "document_article_core": core.model_copy(
                        update={
                            "article": core.article.model_copy(
                                update={
                                    "title": None,
                                    "subtitle": None,
                                    "body_text": "Body first line.\nSecond line.",
                                }
                            ),
                            "space": core.space.model_copy(
                                update={"space_name": None}
                            )
                        }
                    )
                }
            )
        }
    )

    document = ChannelTalkDocumentArticleV2RecordMapper().to_document(prepared)

    assert document.metadata["title"] == ""
    assert document.metadata["body"] == "Body first line.\nSecond line."
    assert document.metadata["target_name"] == ""
    assert document.metadata["title"] != "article-1"
    assert document.metadata["target_name"] != "space-123"


@pytest.mark.asyncio
async def test_channel_talk_article_full_sync_dual_writes_v2_document():
    fake_fetcher = SimpleNamespace(
        fetch_articles=AsyncMock(
            return_value=SimpleNamespace(
                bundles=(_published_bundle(),),
                fetched_count=1,
                article_ids=("article-1",),
                next_checkpoint_state=None,
                next_checkpoint_cursor=None,
            )
        )
    )
    repository = _DualWriteArticleRepository()
    vector_store = SimpleNamespace(
        delete_by_id_prefix=AsyncMock(return_value=1),
        upsert_documents=AsyncMock(
            return_value=[
                "channel_talk:document_article:channel-123:space-123:ko:article-1:chunk:0"
            ]
        ),
    )
    author_resolver = _FakeChannelTalkArticleAuthorResolver()
    adapter = ChannelTalkArticleFullSyncIngestionAdapter(
        enable_v2_dual_write=True,
        vector_store=vector_store,
        v2_document_builder=_v2_document_builder(author_resolver),
    )
    adapter._fetcher = fake_fetcher
    adapter._build_repository = lambda: repository

    result = await run_sync_ingestion(
        port=adapter,
        execution=_execution(),
        sync_window=_window(),
    )

    assert result.persisted_count == 1
    assert result.v2_failed_count == 0
    assert repository.added_documents == []
    assert repository.deleted_prefixes == [
        "channel_talk:document_article:channel-123:space-123:ko:article-1:chunk:"
    ]
    assert repository.deleted_ids == [
        "channel_talk:document_article:channel-123:space-123:ko:article-1:chunk:0"
    ]
    assert repository.stored_documents[0].page_content.startswith(
        "Published refund policy"
    )
    vector_store.delete_by_id_prefix.assert_awaited_once_with(
        "channel_talk:document_article:channel-123:space-123:ko:article-1:chunk:"
    )
    vector_store.upsert_documents.assert_awaited_once()
    upsert_kwargs = vector_store.upsert_documents.await_args.kwargs
    v2_document = vector_store.upsert_documents.await_args.args[0][0]
    assert upsert_kwargs["ids"] == [
        "channel_talk:document_article:channel-123:space-123:ko:article-1:chunk:0"
    ]
    assert upsert_kwargs["embeddings"] == [[0.75]]
    assert v2_document.page_content.startswith("Published refund policy")
    assert v2_document.metadata["body"] == "# Refunds\n\nPublished body text."
    assert v2_document.metadata["data"] == {"parts": []}
    assert v2_document.metadata["channel_talk_document_article"]["author"] == {
        "author_id": "author-1",
        "author_name": "Writer Kim",
    }
    assert author_resolver.author_ids == ["author-1"]
    assert v2_document.metadata["internal_author_id"] == "42"


@pytest.mark.asyncio
async def test_channel_talk_article_v2_store_failure_keeps_legacy_persist_success():
    fake_fetcher = SimpleNamespace(
        fetch_articles=AsyncMock(
            return_value=SimpleNamespace(
                bundles=(_published_bundle(),),
                fetched_count=1,
                article_ids=("article-1",),
                next_checkpoint_state=None,
                next_checkpoint_cursor=None,
            )
        )
    )
    repository = _DualWriteArticleRepository()
    adapter = ChannelTalkArticleFullSyncIngestionAdapter(
        enable_v2_dual_write=True,
        v2_document_builder=_v2_document_builder(),
    )
    adapter._fetcher = fake_fetcher
    adapter._build_repository = lambda: repository
    adapter._get_vector_store = AsyncMock(side_effect=RuntimeError("v2 offline"))

    result = await run_sync_ingestion(
        port=adapter,
        execution=_execution(),
        sync_window=_window(),
    )

    assert result.persisted_count == 1
    assert result.v2_failed_count == 2
    assert result.v2_failed_ids == (
        "channel_talk:document_article:channel-123:space-123:ko:article-1:chunk:",
        "channel_talk:document_article:channel-123:space-123:ko:article-1:chunk:0",
    )
    assert repository.added_documents
    assert repository.stored_documents == []


def test_channel_talk_article_backfill_queries_follow_v1_seed_pattern():
    target_query = str(build_channel_talk_document_article_v1_target_query())
    target_seed_query = str(build_channel_talk_document_article_v1_target_seed_query())
    seed_query = str(build_fetch_seeded_seed_chunk_query())
    upsert_statement = str(build_upsert_seed_rows_statement())

    assert "e.cmetadata ->> 'source' = 'channel_talk'" in target_query
    assert "e.cmetadata ->> 'entity_type' = 'document_article'" in target_query
    assert "LEFT JOIN knowledge_store v2" in target_query
    assert "needs_backfill" in target_query
    assert "GROUP BY scope_id, target_id\n" in target_query
    assert "GROUP BY scope_id, target_id, target_name" not in target_query
    assert "v2.internal_author_id IS NULL" in target_query
    assert "#>> '{channel_talk_document_article,schema_version}'" in target_query
    assert "#>> '{channel_talk_document_article,author,author_id}'" in target_query
    assert "v2.internal_author_id IS NULL" in target_seed_query
    assert "#>> '{channel_talk_document_article,schema_version}'" in target_seed_query
    assert "scope_id = :scope_id" in seed_query
    assert "target_id = :target_id" in seed_query
    assert "COALESCE(metadata::jsonb, '{}'::jsonb) = '{}'::jsonb" in seed_query
    assert "INSERT INTO knowledge_store" in upsert_statement
    assert "'channel_talk'" in upsert_statement
    assert "'document_article'" in upsert_statement
    assert "'document_space'" in upsert_statement
    assert "metadata = '{}'::json" not in upsert_statement
    assert "title = ''" not in upsert_statement
    assert "body = ''" not in upsert_statement
    assert "data = NULL" not in upsert_statement
    assert "jsonb_build_object('parts', '[]'::jsonb)" in upsert_statement
    assert (
        ":target_name,\n"
        "            NULL,\n"
        "            '',\n"
        "            '',\n"
        "            jsonb_build_object('parts', '[]'::jsonb),\n"
        "            '',"
    ) in upsert_statement
    assert "url = ''" not in upsert_statement


def test_channel_talk_article_backfill_mark_finished_casts_failed_ids_to_jsonb():
    statement = str(build_channel_talk_document_article_mark_finished_statement())

    assert "failed_ids = CAST(:failed_ids AS jsonb)" in statement


def test_channel_talk_article_backfill_mark_finished_serializes_failed_ids():
    session = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = session
    service = ChannelTalkArticleV2BackfillService(session_factory=lambda: context)

    service._mark_finished_sync(
        ChannelTalkArticleV1Target(
            scope_id="channel-123",
            target_id="space-123",
            target_name="Help Center",
            expected_count=1,
            pending_count=1,
        ),
        backfill_count=0,
        failed_langchain_ids=[
            "channel_talk:document_article:channel-123:space-123:ko:article-1:chunk:0"
        ],
        force_failed=True,
    )

    params = session.execute.call_args.args[1]
    assert json.loads(params["failed_ids"]) == [
        "channel_talk:document_article:channel-123:space-123:ko:article-1:chunk:0"
    ]
    assert isinstance(params["failed_ids"], str)


@pytest.mark.asyncio
async def test_backfill_adapter_hydrates_article_and_reuses_v1_seed_values():
    seed = ChannelTalkArticleV2BackfillSeed(
        langchain_id=(
            "channel_talk:document_article:"
            "channel-123:space-123:ko:article-1:chunk:0"
        ),
        record_id="article-1",
        content="v1 article chunk content",
        embedding=[0.1, 0.2, 0.3],
    )
    fetcher = SimpleNamespace(
        fetch_article_bundle_by_id=AsyncMock(return_value=_published_bundle())
    )
    vector_store = SimpleNamespace(
        delete_by_id_prefix=AsyncMock(return_value=1),
        upsert_documents=AsyncMock(return_value=[seed.langchain_id]),
        find_missing_metadata_namespace_ids=AsyncMock(return_value=()),
    )
    author_resolver = _FakeChannelTalkArticleAuthorResolver()
    adapter = ChannelTalkArticleV2BackfillAdapter(
        fetcher=fetcher,
        vector_store=vector_store,
        v2_document_builder=_v2_document_builder(author_resolver),
    )
    execution = _execution()

    result = await run_sync_ingestion(
        port=adapter,
        execution=ChannelTalkArticleV2BackfillExecutionRequest(
            tenant_id="channel-123",
            channel_connection=execution.channel_connection,
            document_connection=execution.document_connection,
            seeds=(seed,),
        ),
        sync_window=_window(),
    )

    assert result.persisted_count == 1
    assert result.v2_failed_count == 0
    assert result.metadata["failed_ids"] == []
    fetcher.fetch_article_bundle_by_id.assert_awaited_once()
    vector_store.upsert_documents.assert_awaited_once()
    upsert_args = vector_store.upsert_documents.await_args
    document = upsert_args.args[0][0]
    assert document.id == seed.langchain_id
    assert document.page_content == seed.content
    assert document.metadata["body"] == "# Refunds\n\nPublished body text."
    assert document.metadata["data"] == {"parts": []}
    assert author_resolver.author_ids == ["author-1"]
    assert document.metadata["internal_author_id"] == "42"
    assert upsert_args.kwargs["ids"] == [seed.langchain_id]
    assert upsert_args.kwargs["embeddings"] == [seed.embedding]
    vector_store.delete_by_id_prefix.assert_not_awaited()
    vector_store.find_missing_metadata_namespace_ids.assert_awaited_once_with(
        [seed.langchain_id],
        namespace="channel_talk_document_article",
    )


@pytest.mark.asyncio
async def test_backfill_adapter_treats_missing_article_metadata_as_failed():
    seed = ChannelTalkArticleV2BackfillSeed(
        langchain_id=(
            "channel_talk:document_article:"
            "channel-123:space-123:ko:article-1:chunk:0"
        ),
        record_id="article-1",
        content="v1 article chunk content",
        embedding=[0.1, 0.2, 0.3],
    )
    fetcher = SimpleNamespace(
        fetch_article_bundle_by_id=AsyncMock(return_value=_published_bundle())
    )
    vector_store = SimpleNamespace(
        delete_by_id_prefix=AsyncMock(return_value=1),
        upsert_documents=AsyncMock(return_value=[seed.langchain_id]),
        find_missing_metadata_namespace_ids=AsyncMock(
            return_value=(seed.langchain_id,)
        ),
    )
    adapter = ChannelTalkArticleV2BackfillAdapter(
        fetcher=fetcher,
        vector_store=vector_store,
        v2_document_builder=_v2_document_builder(),
    )
    execution = _execution()

    result = await run_sync_ingestion(
        port=adapter,
        execution=ChannelTalkArticleV2BackfillExecutionRequest(
            tenant_id="channel-123",
            channel_connection=execution.channel_connection,
            document_connection=execution.document_connection,
            seeds=(seed,),
        ),
        sync_window=_window(),
    )

    assert result.persisted_count == 0
    assert result.v2_failed_count == 1
    assert result.v2_failed_ids == (seed.langchain_id,)
    assert result.metadata["failed_ids"] == [seed.langchain_id]


@pytest.mark.asyncio
async def test_backfill_adapter_does_not_delete_seed_rows_when_upsert_fails():
    seed = ChannelTalkArticleV2BackfillSeed(
        langchain_id=(
            "channel_talk:document_article:"
            "channel-123:space-123:ko:article-1:chunk:0"
        ),
        record_id="article-1",
        content="v1 article chunk content",
        embedding=[0.1, 0.2, 0.3],
    )
    fetcher = SimpleNamespace(
        fetch_article_bundle_by_id=AsyncMock(return_value=_published_bundle())
    )
    vector_store = SimpleNamespace(
        delete_by_id_prefix=AsyncMock(return_value=1),
        upsert_documents=AsyncMock(side_effect=RuntimeError("v2 write failed")),
    )
    adapter = ChannelTalkArticleV2BackfillAdapter(
        fetcher=fetcher,
        vector_store=vector_store,
        v2_document_builder=_v2_document_builder(),
    )
    execution = _execution()

    result = await run_sync_ingestion(
        port=adapter,
        execution=ChannelTalkArticleV2BackfillExecutionRequest(
            tenant_id="channel-123",
            channel_connection=execution.channel_connection,
            document_connection=execution.document_connection,
            seeds=(seed,),
        ),
        sync_window=_window(),
    )

    assert result.persisted_count == 0
    assert result.v2_failed_ids == (seed.langchain_id,)
    vector_store.upsert_documents.assert_awaited_once()
    vector_store.delete_by_id_prefix.assert_not_awaited()
