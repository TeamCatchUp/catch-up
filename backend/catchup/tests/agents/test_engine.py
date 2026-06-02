from unittest.mock import MagicMock
from unittest.mock import patch

from catchup.agents.engine import _GRAPH_CACHE_MAX_SIZE
from catchup.agents.engine import ExecutionService


def _make_service() -> ExecutionService:
    return ExecutionService(llm=MagicMock())


def _make_spec() -> MagicMock:
    return MagicMock()


def _fill_cache(service: ExecutionService, mock_build: MagicMock) -> None:
    """캐시를 max_size만큼 채운다."""
    for i in range(_GRAPH_CACHE_MAX_SIZE):
        service._get_graph(i, _make_spec())


def test_graph_cache_evicts_lru_when_full():
    service = _make_service()
    with patch(
        "catchup.agents.engine.build_execution_graph",
        side_effect=lambda spec, llm: MagicMock(),
    ):
        _fill_cache(service, None)
        # spec_id=0을 다시 접근해 최근 사용으로 승격
        service._get_graph(0, _make_spec())
        # 새 항목 삽입 → LRU(spec_id=1)가 evict되어야 함
        service._get_graph(_GRAPH_CACHE_MAX_SIZE, _make_spec())

    assert len(service._graph_cache) == _GRAPH_CACHE_MAX_SIZE
    assert 1 not in service._graph_cache   # LRU evict
    assert 0 in service._graph_cache       # 최근 접근 → 보존
    assert _GRAPH_CACHE_MAX_SIZE in service._graph_cache  # 신규 → 보존


def test_graph_cache_preserves_all_when_under_limit():
    service = _make_service()
    with patch(
        "catchup.agents.engine.build_execution_graph",
        side_effect=lambda spec, llm: MagicMock(),
    ):
        _fill_cache(service, None)

    assert len(service._graph_cache) == _GRAPH_CACHE_MAX_SIZE


def test_graph_cache_does_not_rebuild_cached_graph():
    service = _make_service()
    with patch(
        "catchup.agents.engine.build_execution_graph",
        side_effect=lambda spec, llm: MagicMock(),
    ) as mock_build:
        service._get_graph(1, _make_spec())
        service._get_graph(1, _make_spec())

    assert mock_build.call_count == 1
