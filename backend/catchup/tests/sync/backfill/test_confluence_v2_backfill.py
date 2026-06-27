from __future__ import annotations

import pytest

from catchup.sync.backfill.base import BackfillSeed
from catchup.sync.backfill.base import failed_ids_from_result
from catchup.sync.backfill.confluence_v2 import build_confluence_v1_target_query
from catchup.sync.backfill.confluence_v2 import build_confluence_v1_target_seed_query
from catchup.sync.backfill.confluence_v2 import build_upsert_seed_rows_statement
from catchup.sync.ingestion.schemas import SyncExecutionResult


def _sql(statement) -> str:
    return str(statement)


def test_confluence_page_seed_query_uses_bounded_keyset_pages() -> None:
    sql = _sql(build_confluence_v1_target_seed_query("page"))

    assert "SELECT langchain_id, record_id, content, embedding" in sql
    assert "AND target_id = :target_id" in sql
    assert "AND COALESCE(record_id, '') != ''" in sql
    assert "AND embedding IS NOT NULL" in sql
    assert "CAST(:after_record_id AS text) IS NULL" in sql
    assert "record_id > CAST(:after_record_id AS text)" in sql
    assert "record_id = CAST(:after_record_id AS text)" in sql
    assert "langchain_id > COALESCE(CAST(:after_langchain_id AS text), '')" in sql
    assert "ORDER BY record_id, langchain_id" in sql
    assert "LIMIT :limit" in sql
    assert "OFFSET" not in sql


@pytest.mark.parametrize("entity_type", ["page", "blogpost"])
def test_confluence_target_query_qualifies_grouped_columns_after_state_join(
    entity_type: str,
) -> None:
    sql = _sql(build_confluence_v1_target_query(entity_type))

    assert "SELECT\n            grouped.scope_id," in sql
    assert f"state.entity_type = '{entity_type}'" in sql
    assert "grouped.pending_count > 0" in sql
    assert "ORDER BY grouped.scope_id, grouped.target_id" in sql
    assert "SELECT scope_id, target_id" not in sql
    assert "ORDER BY scope_id, target_id" not in sql


def test_confluence_blogpost_seed_query_uses_blogpost_entity_type() -> None:
    sql = _sql(build_confluence_v1_target_seed_query("blogpost"))

    assert "e.cmetadata ->> 'entity_type' = 'blogpost'" in sql
    assert "AND COALESCE(record_id, '') != ''" in sql
    assert "LIMIT :limit" in sql


@pytest.mark.parametrize("entity_type", ["page", "blogpost"])
def test_confluence_seed_upsert_and_fetch_queries_use_entity_type(
    entity_type: str,
) -> None:
    target_seed_sql = _sql(build_confluence_v1_target_seed_query(entity_type))
    upsert_sql = _sql(build_upsert_seed_rows_statement(entity_type))

    assert f"e.cmetadata ->> 'entity_type' = '{entity_type}'" in target_seed_sql
    assert "AND COALESCE(record_id, '') != ''" in target_seed_sql
    assert f"'{entity_type}'" in upsert_sql


def test_failed_ids_from_result_uses_v2_failed_ids_metadata() -> None:
    seed = BackfillSeed(
        langchain_id="confluence:page:cloud-1:record-1",
        record_id="record-1",
        content="content",
        embedding=[0.1],
    )
    result = SyncExecutionResult(
        connector="confluence",
        tenant_id="cloud-1",
        target="space",
        failed_count=1,
        metadata={"v2_failed_ids": [seed.langchain_id]},
    )

    assert failed_ids_from_result(result, [seed]) == [seed.langchain_id]
