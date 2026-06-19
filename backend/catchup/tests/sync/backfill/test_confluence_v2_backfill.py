from __future__ import annotations

from catchup.sync.backfill.confluence_v2 import build_confluence_v1_target_seed_query


def _sql(statement) -> str:
    return str(statement)


def test_confluence_page_seed_query_uses_bounded_keyset_pages() -> None:
    sql = _sql(build_confluence_v1_target_seed_query("page"))

    assert "SELECT langchain_id, record_id, content, embedding" in sql
    assert "AND target_id = :target_id" in sql
    assert "AND embedding IS NOT NULL" in sql
    assert "CAST(:after_record_id AS text) IS NULL" in sql
    assert "record_id > CAST(:after_record_id AS text)" in sql
    assert "record_id = CAST(:after_record_id AS text)" in sql
    assert "langchain_id > COALESCE(CAST(:after_langchain_id AS text), '')" in sql
    assert "ORDER BY record_id, langchain_id" in sql
    assert "LIMIT :limit" in sql
    assert "OFFSET" not in sql


def test_confluence_blogpost_seed_query_uses_blogpost_entity_type() -> None:
    sql = _sql(build_confluence_v1_target_seed_query("blogpost"))

    assert "e.cmetadata ->> 'entity_type' = 'blogpost'" in sql
    assert "LIMIT :limit" in sql
