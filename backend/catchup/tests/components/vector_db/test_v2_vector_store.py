from __future__ import annotations

from datetime import datetime
from datetime import timezone
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document

from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_CONTENT_COLUMN
from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_EMBEDDING_COLUMN
from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_ID_COLUMN
from catchup.components.vector_db.v2.constants import (
    KNOWLEDGE_STORE_METADATA_COLUMN_NAMES,
)
from catchup.components.vector_db.v2.constants import (
    KNOWLEDGE_STORE_METADATA_JSON_COLUMN,
)
from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_TABLE_NAME
from catchup.components.vector_db.v2.vector_store import VectorStore
from catchup.sync.ingestion.vector_records.github_pr import GithubPrData
from catchup.sync.ingestion.vector_records.github_pr import GithubPrDataPart
from catchup.sync.ingestion.vector_records.github_pr import GithubPrMetadata
from catchup.sync.ingestion.vector_records.github_pr import GithubPrVectorRecord


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def _record(langchain_id: str = "github:pr:TeamCatchUp/CatchUp:724"):
    return GithubPrVectorRecord(
        langchain_id=langchain_id,
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
        body="PR body\n\nadd prompt rendering tests",
        data=GithubPrData(
            parts=[
                GithubPrDataPart(type="pr_body", text="PR body", metadata={}),
                GithubPrDataPart(
                    type="commit",
                    text="add prompt rendering tests",
                    metadata={"oid": "abcdef123456"},
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
            changed_files=38,
            additions=120,
            deletions=50,
        ),
    )


@pytest.mark.asyncio
async def test_initialize_creates_langchain_table_when_missing(monkeypatch) -> None:
    pg_engine = MagicMock()
    pg_engine.ainit_vectorstore_table = AsyncMock()
    vector_store = MagicMock()
    create = AsyncMock(return_value=vector_store)
    monkeypatch.setattr(
        "catchup.components.vector_db.v2.vector_store.PGVectorStore.create",
        create,
    )
    store = VectorStore(
        embeddings=MagicMock(),
        pg_engine=pg_engine,
    )
    monkeypatch.setattr(store, "_table_exists", lambda: False)

    await store.initialize()

    pg_engine.ainit_vectorstore_table.assert_awaited_once()
    init_kwargs = pg_engine.ainit_vectorstore_table.await_args.kwargs
    assert init_kwargs["table_name"] == KNOWLEDGE_STORE_TABLE_NAME
    assert init_kwargs["id_column"].name == KNOWLEDGE_STORE_ID_COLUMN
    assert init_kwargs["content_column"] == KNOWLEDGE_STORE_CONTENT_COLUMN
    assert init_kwargs["embedding_column"] == KNOWLEDGE_STORE_EMBEDDING_COLUMN
    assert init_kwargs["metadata_json_column"] == KNOWLEDGE_STORE_METADATA_JSON_COLUMN
    assert init_kwargs["store_metadata"] is True
    assert [column.name for column in init_kwargs["metadata_columns"]] == (
        KNOWLEDGE_STORE_METADATA_COLUMN_NAMES
    )

    create.assert_awaited_once()
    create_kwargs = create.await_args.kwargs
    assert create_kwargs["table_name"] == KNOWLEDGE_STORE_TABLE_NAME
    assert create_kwargs["id_column"] == KNOWLEDGE_STORE_ID_COLUMN
    assert create_kwargs["metadata_json_column"] == KNOWLEDGE_STORE_METADATA_JSON_COLUMN
    assert create_kwargs["metadata_columns"] == KNOWLEDGE_STORE_METADATA_COLUMN_NAMES


@pytest.mark.asyncio
async def test_initialize_reuses_existing_async_engine(monkeypatch) -> None:
    async_engine = object()
    pg_engine = MagicMock()
    pg_engine.ainit_vectorstore_table = AsyncMock()
    from_engine = MagicMock(return_value=pg_engine)
    vector_store = MagicMock()
    create = AsyncMock(return_value=vector_store)
    monkeypatch.setattr(
        "catchup.components.vector_db.v2.vector_store.sqlalchemy_async_engine",
        async_engine,
    )
    monkeypatch.setattr(
        "catchup.components.vector_db.v2.vector_store.PGEngine.from_engine",
        from_engine,
    )
    monkeypatch.setattr(
        "catchup.components.vector_db.v2.vector_store.PGVectorStore.create",
        create,
    )
    store = VectorStore(embeddings=MagicMock())
    monkeypatch.setattr(store, "_table_exists", lambda: True)

    await store.initialize()

    from_engine.assert_called_once_with(async_engine)
    pg_engine.ainit_vectorstore_table.assert_not_awaited()
    assert create.await_args.kwargs["engine"] is pg_engine


@pytest.mark.asyncio
async def test_upsert_documents_uses_langchain_add_embeddings_when_embeddings_are_given() -> None:
    vector_store = MagicMock()
    vector_store.aadd_embeddings = AsyncMock(
        return_value=["github:pr:TeamCatchUp/CatchUp:724"]
    )
    store = VectorStore(
        embeddings=MagicMock(),
        vector_store=vector_store,
    )
    record = _record()
    document = record.to_document()

    ids = await store.upsert_documents(
        [document],
        ids=[record.langchain_id],
        embeddings=[record.embedding],
    )

    assert ids == ["github:pr:TeamCatchUp/CatchUp:724"]
    vector_store.aadd_embeddings.assert_awaited_once()
    kwargs = vector_store.aadd_embeddings.await_args.kwargs
    assert kwargs["texts"] == ["Summarized pull request content"]
    assert kwargs["embeddings"] == [[0.0123, -0.0456, 0.0789]]
    assert kwargs["ids"] == ["github:pr:TeamCatchUp/CatchUp:724"]

    metadata = kwargs["metadatas"][0]
    assert metadata["title"] == "[CAM-37] refactor backend prompt pipeline"
    assert metadata["body"] == "PR body\n\nadd prompt rendering tests"
    assert metadata["data"]["parts"][1]["metadata"]["oid"] == "abcdef123456"
    assert set(metadata["github_pr"]) == {
        "state",
        "merged_at",
        "closed_at",
        "base_ref",
        "head_ref",
        "is_draft",
        "review_decision",
        "changed_files",
        "additions",
        "deletions",
        "author",
        "assignees",
        "requested_reviewers",
        "review_authors",
        "merged_by",
        "labels",
        "milestone",
    }


@pytest.mark.asyncio
async def test_upsert_documents_uses_langchain_add_documents_without_embeddings() -> None:
    vector_store = MagicMock()
    vector_store.aadd_documents = AsyncMock(return_value=["doc-1"])
    store = VectorStore(
        embeddings=MagicMock(),
        vector_store=vector_store,
    )
    document = Document(
        id="doc-1",
        page_content="content",
        metadata={"source": "github"},
    )

    ids = await store.upsert_documents([document])

    assert ids == ["doc-1"]
    vector_store.aadd_documents.assert_awaited_once_with(
        documents=[document],
        ids=["doc-1"],
    )


@pytest.mark.asyncio
async def test_upsert_documents_reraises_langchain_store_error() -> None:
    vector_store = MagicMock()
    vector_store.aadd_documents = AsyncMock(side_effect=RuntimeError("pgvector down"))
    store = VectorStore(
        embeddings=MagicMock(),
        vector_store=vector_store,
    )
    document = Document(
        id="doc-1",
        page_content="content",
        metadata={"source": "github"},
    )

    with pytest.raises(RuntimeError, match="pgvector down"):
        await store.upsert_documents([document])

    vector_store.aadd_documents.assert_awaited_once_with(
        documents=[document],
        ids=["doc-1"],
    )


@pytest.mark.asyncio
async def test_delete_delegates_to_langchain_store() -> None:
    vector_store = MagicMock()
    vector_store.adelete = AsyncMock(return_value=True)
    store = VectorStore(
        embeddings=MagicMock(),
        vector_store=vector_store,
    )

    deleted = await store.delete(
        [
            "github:pr:TeamCatchUp/CatchUp:724",
            "github:pr:TeamCatchUp/CatchUp:725",
        ]
    )

    assert deleted == 2
    vector_store.adelete.assert_awaited_once_with(
        ids=[
            "github:pr:TeamCatchUp/CatchUp:724",
            "github:pr:TeamCatchUp/CatchUp:725",
        ]
    )


@pytest.mark.asyncio
async def test_delete_reraises_langchain_store_error() -> None:
    vector_store = MagicMock()
    vector_store.adelete = AsyncMock(side_effect=RuntimeError("pgvector down"))
    store = VectorStore(
        embeddings=MagicMock(),
        vector_store=vector_store,
    )

    with pytest.raises(RuntimeError, match="pgvector down"):
        await store.delete(["github:pr:TeamCatchUp/CatchUp:724"])

    vector_store.adelete.assert_awaited_once_with(
        ids=["github:pr:TeamCatchUp/CatchUp:724"]
    )
