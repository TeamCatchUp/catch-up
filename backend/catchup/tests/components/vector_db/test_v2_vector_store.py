from __future__ import annotations

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
from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_TABLE_NAME
from catchup.components.vector_db.v2.vector_store import VectorStore


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
    ensure_constraints = AsyncMock()
    monkeypatch.setattr(store, "_table_exists", lambda: False)
    monkeypatch.setattr(store, "_ensure_constraints", ensure_constraints)

    await store.initialize()

    pg_engine.ainit_vectorstore_table.assert_awaited_once()
    init_kwargs = pg_engine.ainit_vectorstore_table.await_args.kwargs
    assert init_kwargs["table_name"] == KNOWLEDGE_STORE_TABLE_NAME
    assert init_kwargs["id_column"].name == KNOWLEDGE_STORE_ID_COLUMN
    assert init_kwargs["content_column"] == KNOWLEDGE_STORE_CONTENT_COLUMN
    assert init_kwargs["embedding_column"] == KNOWLEDGE_STORE_EMBEDDING_COLUMN
    assert "metadata_json_column" not in init_kwargs
    assert init_kwargs["store_metadata"] is False
    assert [column.name for column in init_kwargs["metadata_columns"]] == (
        KNOWLEDGE_STORE_METADATA_COLUMN_NAMES
    )
    metadata_columns = {
        column.name: column for column in init_kwargs["metadata_columns"]
    }
    assert metadata_columns["chunk_identifier"].data_type == "INTEGER DEFAULT 0"

    create.assert_awaited_once()
    create_kwargs = create.await_args.kwargs
    assert create_kwargs["table_name"] == KNOWLEDGE_STORE_TABLE_NAME
    assert create_kwargs["id_column"] == KNOWLEDGE_STORE_ID_COLUMN
    assert create_kwargs["metadata_json_column"] is None
    assert create_kwargs["metadata_columns"] == KNOWLEDGE_STORE_METADATA_COLUMN_NAMES
    ensure_constraints.assert_awaited_once()


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
    ensure_constraints = AsyncMock()
    monkeypatch.setattr(store, "_table_exists", lambda: True)
    monkeypatch.setattr(store, "_ensure_constraints", ensure_constraints)

    await store.initialize()

    from_engine.assert_called_once_with(async_engine)
    pg_engine.ainit_vectorstore_table.assert_not_awaited()
    assert create.await_args.kwargs["engine"] is pg_engine
    ensure_constraints.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_documents_uses_langchain_add_embeddings_when_embeddings_are_given() -> None:
    vector_store = MagicMock()
    vector_store.aadd_embeddings = AsyncMock(
        return_value=["github:pr:118342815:674560284:724:0"]
    )
    store = VectorStore(
        embeddings=MagicMock(),
        vector_store=vector_store,
    )
    document_id = "github:pr:118342815:674560284:724:0"
    document = Document(
        page_content="Summarized pull request content",
        metadata={
            "source": "github",
            "entity_type": "pr",
            "scope_id": "118342815",
            "target_id": "674560284",
            "external_document_id": "724",
            "chunk_identifier": 0,
            "created_at": "2026-05-19T20:13:01+00:00",
            "updated_at": "2026-05-19T20:19:53+00:00",
        },
    )

    ids = await store.upsert_documents(
        [document],
        ids=[document_id],
        embeddings=[[0.0123, -0.0456, 0.0789]],
    )

    assert ids == [document_id]
    vector_store.aadd_embeddings.assert_awaited_once()
    kwargs = vector_store.aadd_embeddings.await_args.kwargs
    assert kwargs["texts"] == ["Summarized pull request content"]
    assert kwargs["embeddings"] == [[0.0123, -0.0456, 0.0789]]
    assert kwargs["ids"] == [document_id]
    assert kwargs["metadatas"] == [document.metadata]


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
