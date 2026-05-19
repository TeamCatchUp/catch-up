# backend/catchup/tests/rag/test_supervisor_prompt.py
from catchup.prompts.loader import prompt_loader
from catchup.rag.schemas.sources import SOURCE_METADATA
from catchup.rag.schemas.structures import SearchTurnMeta

SOURCES = list(SOURCE_METADATA.values())

MINIMAL_GLOBAL = dict(
    current_time=None,
    company=None,
    user=None,
)


# ---------------------------------------------------------------------------
# supervisor_static.j2
# ---------------------------------------------------------------------------


def test_static_contains_role():
    result = prompt_loader.get_prompt(
        "rag/supervisor_static",
        sources=SOURCES,
        slack_thread_context=None,
    )
    assert "<role>" in result
    assert "</role>" in result


def test_static_contains_pipeline_catalog():
    result = prompt_loader.get_prompt(
        "rag/supervisor_static",
        sources=SOURCES,
        slack_thread_context=None,
    )
    assert "<pipeline_catalog>" in result
    assert 'type="clarify"' in result
    assert 'type="direct_answer"' in result
    assert 'type="simple"' in result
    assert 'type="standard"' in result
    assert 'type="complex"' in result


def test_static_contains_decision_rules():
    result = prompt_loader.get_prompt(
        "rag/supervisor_static",
        sources=SOURCES,
        slack_thread_context=None,
    )
    assert "<decision_rules>" in result
    assert '<step order="1">' in result
    assert '<step order="2">' in result
    assert '<step order="3">' in result


def test_static_contains_output_spec():
    result = prompt_loader.get_prompt(
        "rag/supervisor_static",
        sources=SOURCES,
        slack_thread_context=None,
    )
    assert "<output_spec>" in result
    assert 'name="reasoning"' in result
    assert 'name="query_topic"' in result
    assert 'name="cache_turn_numbers"' in result


def test_static_no_slack_routing_when_no_slack():
    result = prompt_loader.get_prompt(
        "rag/supervisor_static",
        sources=SOURCES,
        slack_thread_context=None,
    )
    assert "<slack_thread_routing_addendum>" not in result


def test_static_includes_slack_routing_when_slack_present():
    result = prompt_loader.get_prompt(
        "rag/supervisor_static",
        sources=SOURCES,
        slack_thread_context="some thread content",
    )
    assert "<slack_thread_routing_addendum>" in result


def test_static_source_filter_rules_list_sources():
    result = prompt_loader.get_prompt(
        "rag/supervisor_static",
        sources=SOURCES,
        slack_thread_context=None,
    )
    assert "Jira에서" in result
    assert "Slack에서" in result


# ---------------------------------------------------------------------------
# supervisor_dynamic.j2 — minimal (no optional fields)
# ---------------------------------------------------------------------------


def test_dynamic_minimal_no_optional_wrappers():
    """모든 optional 조건이 false일 때 wrapper 태그 자체가 렌더링되지 않아야 한다."""
    result = prompt_loader.get_prompt(
        "rag/supervisor_dynamic",
        search_turn_history=[],
        slack_thread_context=None,
        **MINIMAL_GLOBAL,
    )
    assert "<time_context>" not in result
    assert "<organization>" not in result
    assert "<user>" not in result
    assert "<search_history>" not in result
    assert "<slack_thread_context>" not in result


def test_dynamic_contains_task():
    result = prompt_loader.get_prompt(
        "rag/supervisor_dynamic",
        search_turn_history=[],
        slack_thread_context=None,
        **MINIMAL_GLOBAL,
    )
    assert "<task>" in result
    assert "</task>" in result


def test_dynamic_context_wrapper_present_when_time_given():
    from types import SimpleNamespace

    time_ctx = SimpleNamespace(kst="2026-05-19 10:00 KST", utc="2026-05-19 01:00 UTC")
    result = prompt_loader.get_prompt(
        "rag/supervisor_dynamic",
        search_turn_history=[],
        slack_thread_context=None,
        current_time=time_ctx,
        company=None,
        user=None,
    )
    assert "<time_context>" in result
    assert "2026-05-19 10:00 KST" in result


def test_dynamic_organization_wrapper_present():
    from types import SimpleNamespace

    company = SimpleNamespace(
        name="CatchUp Inc.", description="Enterprise search service."
    )
    result = prompt_loader.get_prompt(
        "rag/supervisor_dynamic",
        search_turn_history=[],
        slack_thread_context=None,
        current_time=None,
        company=company,
        user=None,
    )
    assert "<organization>" in result
    assert "CatchUp Inc." in result


def test_dynamic_user_wrapper_present():
    from types import SimpleNamespace

    user = SimpleNamespace(
        name="홍길동", email="hong@example.com", department="Engineering"
    )
    result = prompt_loader.get_prompt(
        "rag/supervisor_dynamic",
        search_turn_history=[],
        slack_thread_context=None,
        current_time=None,
        company=None,
        user=user,
    )
    assert "<user>" in result
    assert "홍길동" in result
    assert "hong@example.com" in result


# ---------------------------------------------------------------------------
# supervisor_dynamic.j2 — search_history rendering
# ---------------------------------------------------------------------------


def test_dynamic_search_history_wrapper_absent_when_empty():
    result = prompt_loader.get_prompt(
        "rag/supervisor_dynamic",
        search_turn_history=[],
        slack_thread_context=None,
        **MINIMAL_GLOBAL,
    )
    assert "<search_history>" not in result


def test_dynamic_search_history_single_turn_is_hot_cache():
    snap = SearchTurnMeta(
        turn_number=1,
        rewritten_query="CATDEV-119 담당자",
        query_topic="CATDEV-119 담당자",
        doc_ids=["id1"],
        source_distribution={"jira": 1},
    )
    result = prompt_loader.get_prompt(
        "rag/supervisor_dynamic",
        search_turn_history=[snap],
        slack_thread_context=None,
        **MINIMAL_GLOBAL,
    )
    assert "<search_history>" in result
    assert 'index="1"' in result
    assert 'hot_cache="true"' in result
    assert "CATDEV-119 담당자" in result


def test_dynamic_search_history_only_last_turn_is_hot_cache():
    snaps = [
        SearchTurnMeta(
            turn_number=1,
            rewritten_query="query A",
            query_topic="topic A",
            doc_ids=["a1"],
            source_distribution={"jira": 1},
        ),
        SearchTurnMeta(
            turn_number=2,
            rewritten_query="query B",
            query_topic="topic B",
            doc_ids=["b1"],
            source_distribution={"slack": 1},
        ),
    ]
    result = prompt_loader.get_prompt(
        "rag/supervisor_dynamic",
        search_turn_history=snaps,
        slack_thread_context=None,
        **MINIMAL_GLOBAL,
    )
    assert 'index="1"' in result
    assert 'index="2"' in result
    # 첫 번째 턴에 hot_cache가 없어야 함
    first_turn_block = result.split('index="2"')[0]
    assert 'hot_cache="true"' not in first_turn_block
    # 마지막 턴에만 hot_cache
    assert 'index="2" hot_cache="true"' in result


def test_dynamic_search_history_source_distribution_rendered():
    snap = SearchTurnMeta(
        turn_number=1,
        rewritten_query="배포 이슈",
        query_topic="배포 이슈",
        doc_ids=["d1", "d2"],
        source_distribution={"jira": 2, "github": 1},
    )
    result = prompt_loader.get_prompt(
        "rag/supervisor_dynamic",
        search_turn_history=[snap],
        slack_thread_context=None,
        **MINIMAL_GLOBAL,
    )
    assert "jira" in result
    assert "github" in result


# ---------------------------------------------------------------------------
# supervisor_dynamic.j2 — slack_thread_context
# ---------------------------------------------------------------------------


def test_dynamic_slack_wrapper_absent_when_none():
    result = prompt_loader.get_prompt(
        "rag/supervisor_dynamic",
        search_turn_history=[],
        slack_thread_context=None,
        **MINIMAL_GLOBAL,
    )
    assert "<slack_thread_context>" not in result


def test_dynamic_slack_wrapper_present_when_given():
    result = prompt_loader.get_prompt(
        "rag/supervisor_dynamic",
        search_turn_history=[],
        slack_thread_context="User: 배포 언제 돼요?\nBot: 내일 예정입니다.",
        **MINIMAL_GLOBAL,
    )
    assert "<slack_thread_context>" in result
    assert "배포 언제 돼요?" in result
