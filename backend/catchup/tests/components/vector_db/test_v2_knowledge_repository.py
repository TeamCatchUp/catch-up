from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_ID_COLUMN
from catchup.components.vector_db.v2.constants import KNOWLEDGE_STORE_TABLE_NAME
from catchup.components.vector_db.v2.knowledge_repository import V2KnowledgeRepository


class _AsyncSessionContext:
    def __init__(self, session) -> None:
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


def _session_factory(session):
    return lambda: _AsyncSessionContext(session)


@pytest.mark.asyncio
async def test_delete_multiple_chunks_by_id_uses_record_identity_columns() -> None:
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(rowcount=2))
    db.commit = AsyncMock()
    repository = V2KnowledgeRepository(session_factory=_session_factory(db))

    deleted = await repository.delete_multiple_chunks_by_id(
        source="channel_talk",
        entity_type="document_article",
        scope_id="channel-123",
        target_id="space-123",
        record_id="article-1",
    )

    assert deleted == 2
    db.execute.assert_awaited_once()
    statement, params = db.execute.call_args.args
    assert f"DELETE FROM {KNOWLEDGE_STORE_TABLE_NAME}" in str(statement)
    statement_text = str(statement)
    assert "source = :source" in statement_text
    assert "entity_type = :entity_type" in statement_text
    assert "scope_id = :scope_id" in statement_text
    assert "target_id = :target_id" in statement_text
    assert "record_id = :record_id" in statement_text
    assert KNOWLEDGE_STORE_ID_COLUMN not in statement_text
    assert "LIKE" not in statement_text
    assert params == {
        "source": "channel_talk",
        "entity_type": "document_article",
        "scope_id": "channel-123",
        "target_id": "space-123",
        "record_id": "article-1",
    }
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_multiple_chunks_by_id_rejects_incomplete_identity() -> None:
    repository = V2KnowledgeRepository()

    with pytest.raises(ValueError, match="record_id"):
        await repository.delete_multiple_chunks_by_id(
            source="confluence",
            entity_type="page",
            scope_id="cloud-123",
            target_id="ENG",
            record_id=" ",
        )


@pytest.mark.asyncio
async def test_find_missing_metadata_namespace_ids_checks_json_namespace() -> None:
    db = MagicMock()
    db.execute = AsyncMock(return_value=[("doc-2",), ("doc-3",)])
    repository = V2KnowledgeRepository(session_factory=_session_factory(db))

    missing_ids = await repository.find_missing_metadata_namespace_ids(
        ["doc-1", "doc-2", "doc-3"],
        namespace="github_issue",
    )

    assert missing_ids == ("doc-2", "doc-3")
    db.execute.assert_awaited_once()
    statement, params = db.execute.call_args.args
    statement_text = str(statement)
    assert "WITH requested(document_id) AS" in statement_text
    assert "LEFT JOIN knowledge_store store" in statement_text
    assert "jsonb_exists" in statement_text
    assert params == {
        "id_0": "doc-1",
        "id_1": "doc-2",
        "id_2": "doc-3",
        "namespace": "github_issue",
    }


@pytest.mark.asyncio
async def test_find_missing_metadata_namespace_ids_returns_empty_for_empty_ids() -> None:
    db = MagicMock()
    db.execute = AsyncMock()
    repository = V2KnowledgeRepository(session_factory=_session_factory(db))

    missing_ids = await repository.find_missing_metadata_namespace_ids(
        [],
        namespace="github_issue",
    )

    assert missing_ids == ()
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_find_missing_metadata_namespace_ids_rejects_blank_namespace() -> None:
    repository = V2KnowledgeRepository()

    with pytest.raises(ValueError, match="metadata namespace is required"):
        await repository.find_missing_metadata_namespace_ids(["doc-1"], namespace=" ")
