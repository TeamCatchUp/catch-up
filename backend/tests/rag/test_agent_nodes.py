"""ReAct 에이전트 노드 단위 테스트 — LLM 호출 시 메시지 이력 포함 여부 검증."""
from __future__ import annotations

from asyncio import Semaphore
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from langchain_core.messages import ToolMessage

from catchup.rag.agents.complex_agent import complex_agent_node
from catchup.rag.agents.standard_agent import standard_agent_node
from catchup.rag.schemas.context import (
    GlobalCompanyContext,
    GlobalContext,
    GlobalUserContext,
    GlobalWorkspaceContext,
)
from catchup.rag.schemas.prompt_settings import PromptSettings
from catchup.rag.semaphores import rag_semaphores


def _global_context() -> GlobalContext:
    return GlobalContext(
        user=GlobalUserContext(id=1, name="테스터", email="test@example.com", department="개발"),
        workspace=GlobalWorkspaceContext(id=1, name="워크스페이스"),
        company=GlobalCompanyContext(id=1, name="테스트컴퍼니"),
    )


def _base_state(messages: list, agent_iteration: int = 0) -> dict:
    return {
        "messages": messages,
        "original_query": "테스트 질문",
        "rewritten_query": "테스트 질문 (재작성)",
        "agent_iteration": agent_iteration,
        "accumulated_docs": [],
        "global_context": _global_context(),
        "pipeline_plan": None,
        "prompt_settings": PromptSettings(),
        "search_plan": None,
        "gap_analysis": None,
    }


def _make_llm(response: AIMessage | None = None) -> MagicMock:
    """툴이 바인딩된 mock LLM을 반환한다."""
    if response is None:
        response = AIMessage(content="검색 완료", tool_calls=[])
    llm_with_tools = MagicMock()
    llm_with_tools.ainvoke = AsyncMock(return_value=response)
    llm = MagicMock()
    llm.bind_tools.return_value = llm_with_tools
    return llm


class StandardAgentMessageHistoryTests(IsolatedAsyncioTestCase):
    """standard_agent_node가 LLM에 올바른 메시지 시퀀스를 전달하는지 검증한다."""

    def setUp(self):
        rag_semaphores.init(small_model_sema_value=5, large_model_sema_value=5, rerank_sema_value=5)

    @patch("catchup.rag.agents.standard_agent.prompt_loader.get_prompt", return_value="시스템 프롬프트")
    @patch("catchup.rag.agents.standard_agent.extract_token_usages", return_value={})
    async def test_1차_반복에서는_시스템과_휴먼_메시지만_전달된다(self, _mock_tokens, _mock_prompt):
        """1차 반복: state["messages"] == [] → LLM은 [system, human] 2개만 받아야 한다."""
        llm = _make_llm()
        state = _base_state(messages=[], agent_iteration=0)

        await standard_agent_node(state, llm)

        call_args = llm.bind_tools.return_value.ainvoke.call_args
        sent_messages: list = call_args.kwargs.get("input") or call_args.args[0]
        self.assertEqual(len(sent_messages), 2)
        self.assertIsInstance(sent_messages[0], SystemMessage)
        self.assertIsInstance(sent_messages[1], HumanMessage)

    @patch("catchup.rag.agents.standard_agent.prompt_loader.get_prompt", return_value="시스템 프롬프트")
    @patch("catchup.rag.agents.standard_agent.extract_token_usages", return_value={})
    async def test_2차_반복에서는_이전_이력이_포함된다(self, _mock_tokens, _mock_prompt):
        """2차 반복: state["messages"] == [AIMessage, ToolMessage] → LLM은 4개 메시지를 받아야 한다."""
        prev_ai = AIMessage(content="", tool_calls=[{"name": "search_and_rerank", "args": {}, "id": "call_1", "type": "tool_call"}])
        prev_tool = ToolMessage(content="검색 결과", tool_call_id="call_1")
        llm = _make_llm()
        state = _base_state(messages=[prev_ai, prev_tool], agent_iteration=1)

        await standard_agent_node(state, llm)

        call_args = llm.bind_tools.return_value.ainvoke.call_args
        sent_messages: list = call_args.kwargs.get("input") or call_args.args[0]
        self.assertEqual(len(sent_messages), 4)
        self.assertIsInstance(sent_messages[0], SystemMessage)
        self.assertIsInstance(sent_messages[1], HumanMessage)
        self.assertIsInstance(sent_messages[2], AIMessage)
        self.assertIsInstance(sent_messages[3], ToolMessage)

    @patch("catchup.rag.agents.standard_agent.prompt_loader.get_prompt", return_value="시스템 프롬프트")
    @patch("catchup.rag.agents.standard_agent.extract_token_usages", return_value={})
    async def test_3차_반복에서는_전체_이력이_포함된다(self, _mock_tokens, _mock_prompt):
        """3차 반복: 두 쌍의 AIMessage+ToolMessage → LLM은 6개 메시지를 받아야 한다."""
        prev_ai_1 = AIMessage(content="", tool_calls=[{"name": "search_and_rerank", "args": {}, "id": "call_1", "type": "tool_call"}])
        prev_tool_1 = ToolMessage(content="첫 번째 검색 결과", tool_call_id="call_1")
        prev_ai_2 = AIMessage(content="", tool_calls=[{"name": "search_and_rerank", "args": {}, "id": "call_2", "type": "tool_call"}])
        prev_tool_2 = ToolMessage(content="두 번째 검색 결과", tool_call_id="call_2")
        llm = _make_llm()
        state = _base_state(messages=[prev_ai_1, prev_tool_1, prev_ai_2, prev_tool_2], agent_iteration=2)

        await standard_agent_node(state, llm)

        call_args = llm.bind_tools.return_value.ainvoke.call_args
        sent_messages: list = call_args.kwargs.get("input") or call_args.args[0]
        self.assertEqual(len(sent_messages), 6)
        self.assertIsInstance(sent_messages[4], AIMessage)
        self.assertIsInstance(sent_messages[5], ToolMessage)


class ComplexAgentMessageHistoryTests(IsolatedAsyncioTestCase):
    """complex_agent_node가 LLM에 올바른 메시지 시퀀스를 전달하는지 검증한다."""

    def setUp(self):
        rag_semaphores.init(small_model_sema_value=5, large_model_sema_value=5, rerank_sema_value=5)

    @patch("catchup.rag.agents.complex_agent.prompt_loader.get_prompt", return_value="시스템 프롬프트")
    @patch("catchup.rag.agents.complex_agent.extract_token_usages", return_value={})
    async def test_1차_반복에서는_시스템과_휴먼_메시지만_전달된다(self, _mock_tokens, _mock_prompt):
        """1차 반복: state["messages"] == [] → LLM은 [system, human] 2개만 받아야 한다."""
        llm = _make_llm()
        state = _base_state(messages=[], agent_iteration=0)

        await complex_agent_node(state, llm)

        call_args = llm.bind_tools.return_value.ainvoke.call_args
        sent_messages: list = call_args.kwargs.get("input") or call_args.args[0]
        self.assertEqual(len(sent_messages), 2)
        self.assertIsInstance(sent_messages[0], SystemMessage)
        self.assertIsInstance(sent_messages[1], HumanMessage)

    @patch("catchup.rag.agents.complex_agent.prompt_loader.get_prompt", return_value="시스템 프롬프트")
    @patch("catchup.rag.agents.complex_agent.extract_token_usages", return_value={})
    async def test_gap_analysis_후_재호출_시_이전_이력이_포함된다(self, _mock_tokens, _mock_prompt):
        """gap_analysis 재진입: 이전 검색 이력이 messages에 있을 때 LLM에 전달되어야 한다."""
        prev_ai = AIMessage(content="충분한 정보를 찾았습니다", tool_calls=[])
        tool_msg = ToolMessage(content="검색 결과", tool_call_id="call_1")
        llm = _make_llm()

        from catchup.rag.schemas.structures import GapAnalysis
        gap = GapAnalysis(is_sufficient=False, gaps=["추가 정보 필요"], suggested_queries=["보완 검색어"])
        state = _base_state(messages=[prev_ai, tool_msg], agent_iteration=1)
        state["gap_analysis"] = gap

        await complex_agent_node(state, llm)

        call_args = llm.bind_tools.return_value.ainvoke.call_args
        sent_messages: list = call_args.kwargs.get("input") or call_args.args[0]
        self.assertEqual(len(sent_messages), 4)
        self.assertIsInstance(sent_messages[2], AIMessage)
        self.assertIsInstance(sent_messages[3], ToolMessage)
