from __future__ import annotations

from catchup.sync.backfill.channel_talk_document_article_v2 import (
    build_channel_talk_document_article_v1_target_seed_query,
)


def test_channel_talk_document_article_seed_query_uses_bounded_keyset_pages() -> None:
    sql = str(build_channel_talk_document_article_v1_target_seed_query())

    assert "SELECT langchain_id, record_id, content, embedding" in sql
    assert "AND target_id = :target_id" in sql
    assert "(record_id, langchain_id) >" in sql
    assert "CAST(:after_record_id AS text)" in sql
    assert "CAST(:after_langchain_id AS text)" in sql
    assert "ORDER BY record_id, langchain_id" in sql
    assert "LIMIT :limit" in sql
    assert "OFFSET" not in sql
