"""valid_from 기입률 집계를 검증한다."""

from __future__ import annotations

from catchup.evaluation.eval_llm_wiki_extraction import _temporal_fill_stats


def _ok_result(claims: list[dict]) -> dict:
    return {
        "status": "ok",
        "batch": {
            "claims": claims,
            "entities": [],
            "relation_assertions": [],
        },
    }


def test_counts_bounds_and_dated_claims() -> None:
    results = [
        _ok_result(
            [
                {"value_type": "date", "valid_from": "2026-01-10T00:00:00Z"},
                {"value_type": "date", "valid_from": None},
                {"value_type": "text", "valid_from": "2026-01-01T00:00:00Z"},
            ]
        ),
        {"status": "error", "error": "boom"},
    ]
    assert _temporal_fill_stats(results) == (2, 1, 2)


def test_empty_results_count_zero() -> None:
    assert _temporal_fill_stats([]) == (0, 0, 0)
