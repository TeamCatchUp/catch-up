"""
reuse staleness guard 검증 테스트.

1. _is_reuse_stale 순수 함수 경계값 테스트
2. collect_docs_node의 last_search_turn 기록 테스트
3. _record_search_turn_node의 last_search_turn 기록 테스트
"""
from __future__ import annotations

from unittest import IsolatedAsyncioTestCase

from catchup.rag.nodes.supervisor.supervisor import _MAX_REUSE_TURNS
from catchup.rag.nodes.supervisor.supervisor import _is_reuse_stale


class IsReuseStaleTests(IsolatedAsyncioTestCase):
    # --- 미검색 케이스 ---

    def test_never_searched_is_always_stale(self):
        """last_search_turn=0이면 항상 stale."""
        self.assertTrue(_is_reuse_stale(current_turn=1, last_search_turn=0))
        self.assertTrue(_is_reuse_stale(current_turn=10, last_search_turn=0))

    # --- 허용 범위 경계값 ---

    def test_delta_within_max_is_not_stale(self):
        """delta <= _MAX_REUSE_TURNS이면 stale 아님."""
        # delta=1
        self.assertFalse(_is_reuse_stale(current_turn=2, last_search_turn=1))
        # delta=2
        self.assertFalse(_is_reuse_stale(current_turn=3, last_search_turn=1))
        # delta=MAX (경계값)
        self.assertFalse(_is_reuse_stale(current_turn=1 + _MAX_REUSE_TURNS, last_search_turn=1))

    def test_delta_exceeding_max_is_stale(self):
        """delta > _MAX_REUSE_TURNS이면 stale."""
        self.assertTrue(_is_reuse_stale(current_turn=1 + _MAX_REUSE_TURNS + 1, last_search_turn=1))
        self.assertTrue(_is_reuse_stale(current_turn=10, last_search_turn=1))

    # --- 검색이 최근 턴에서 발생한 케이스 ---

    def test_search_on_same_turn_is_not_stale(self):
        """같은 턴에 검색 → delta=0, stale 아님."""
        self.assertFalse(_is_reuse_stale(current_turn=5, last_search_turn=5))

    def test_multiple_reuse_turns_accumulate_correctly(self):
        """
        Turn 1 검색 → Turn 2,3,4 reuse 허용 → Turn 5 stale.
        _MAX_REUSE_TURNS=3 기준.
        """
        search_turn = 1
        for reuse_turn in range(2, 2 + _MAX_REUSE_TURNS):
            self.assertFalse(
                _is_reuse_stale(current_turn=reuse_turn, last_search_turn=search_turn),
                msg=f"Turn {reuse_turn} should NOT be stale (delta={reuse_turn - search_turn})",
            )
        first_stale_turn = 1 + _MAX_REUSE_TURNS + 1
        self.assertTrue(
            _is_reuse_stale(current_turn=first_stale_turn, last_search_turn=search_turn),
            msg=f"Turn {first_stale_turn} should be stale (delta={first_stale_turn - search_turn})",
        )


class CollectDocsNodeTests(IsolatedAsyncioTestCase):
    async def test_records_current_turn_number(self):
        """collect_docs_node가 turn_number를 last_search_turn에 기록한다."""
        from catchup.rag.agents.standard_agent import collect_docs_node

        state = {
            "accumulated_docs": [],
            "messages": [],
            "turn_number": 3,
        }
        result = await collect_docs_node(state)

        self.assertEqual(result["last_search_turn"], 3)
        self.assertIn("retrieved_docs", result)

    async def test_returns_empty_docs_when_no_accumulated(self):
        """누적 문서 없으면 retrieved_docs=[]."""
        from catchup.rag.agents.standard_agent import collect_docs_node

        state = {"accumulated_docs": [], "messages": [], "turn_number": 1}
        result = await collect_docs_node(state)

        self.assertEqual(result["retrieved_docs"], [])
        self.assertEqual(result["last_search_turn"], 1)

    async def test_caps_docs_at_rerank_window(self):
        """accumulated_docs가 300개 초과 시 300개로 cap."""
        from unittest.mock import MagicMock

        from catchup.rag.agents.standard_agent import _RERANK_INPUT_WINDOW
        from catchup.rag.agents.standard_agent import collect_docs_node

        fake_docs = [MagicMock() for _ in range(_RERANK_INPUT_WINDOW + 50)]
        state = {"accumulated_docs": fake_docs, "messages": [], "turn_number": 2}
        result = await collect_docs_node(state)

        self.assertEqual(len(result["retrieved_docs"]), _RERANK_INPUT_WINDOW)
        self.assertEqual(result["last_search_turn"], 2)

    async def test_fallback_when_turn_number_missing(self):
        """turn_number가 state에 없으면 0으로 fallback."""
        from catchup.rag.agents.standard_agent import collect_docs_node

        state = {"accumulated_docs": [], "messages": []}
        result = await collect_docs_node(state)

        self.assertEqual(result["last_search_turn"], 0)


class RecordSearchTurnNodeTests(IsolatedAsyncioTestCase):
    async def test_records_turn_number_as_last_search_turn(self):
        """_record_search_turn_node가 turn_number를 last_search_turn에 기록한다."""
        from catchup.rag.subgraphs.simple import _record_search_turn_node

        state = {"turn_number": 5, "messages": []}
        result = await _record_search_turn_node(state)

        self.assertEqual(result["last_search_turn"], 5)

    async def test_fallback_when_turn_number_missing(self):
        """turn_number가 없으면 0으로 fallback."""
        from catchup.rag.subgraphs.simple import _record_search_turn_node

        state = {}
        result = await _record_search_turn_node(state)

        self.assertEqual(result["last_search_turn"], 0)
