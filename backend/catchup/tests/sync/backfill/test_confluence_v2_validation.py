from __future__ import annotations

import pytest

from catchup.sync.backfill.confluence_v2_validation import (
    build_confluence_v2_count_validation_query,
)
from catchup.sync.backfill.confluence_v2_validation import (
    build_confluence_v2_sample_query,
)


@pytest.mark.parametrize(
    ("entity_type", "namespace"),
    [
        ("page", "confluence_page"),
        ("blogpost", "confluence_blogpost"),
    ],
)
def test_confluence_v2_count_validation_query_uses_exact_metadata_namespace(
    entity_type: str,
    namespace: str,
) -> None:
    query = str(build_confluence_v2_count_validation_query(entity_type))

    assert f"entity_type = '{entity_type}'" in query
    assert f"COALESCE(metadata::jsonb, '{{}}'::jsonb) ? '{namespace}'" in query
    assert (
        f"COALESCE(metadata::jsonb, '{{}}'::jsonb) - '{namespace}' = '{{}}'::jsonb"
        in query
    )


@pytest.mark.parametrize(
    ("entity_type", "namespace"),
    [
        ("page", "confluence_page"),
        ("blogpost", "confluence_blogpost"),
    ],
)
def test_confluence_v2_sample_query_uses_exact_metadata_namespace(
    entity_type: str,
    namespace: str,
) -> None:
    query = str(build_confluence_v2_sample_query(entity_type))

    assert "document_id AS langchain_id" in query
    assert "AS langchain_metadata" in query
    assert "WHERE source = 'confluence'" in query
    assert f"entity_type = '{entity_type}'" in query
    assert f"COALESCE(metadata::jsonb, '{{}}'::jsonb) ? '{namespace}'" in query
    assert (
        f"COALESCE(metadata::jsonb, '{{}}'::jsonb) - '{namespace}' = '{{}}'::jsonb"
        in query
    )
