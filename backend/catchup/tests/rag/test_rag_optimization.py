from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from langchain_core.messages import AIMessage

from catchup.rag.agents.complex_agent import complex_agent_node
from catchup.rag.agents.standard_agent import standard_agent_node
from catchup.schemas.context import GlobalCompanyContext
from catchup.schemas.context import GlobalContext
from catchup.schemas.context import GlobalUserContext
from catchup.schemas.context import GlobalWorkspaceContext
from catchup.schemas.prompt_settings import PromptSettings
from catchup.utils.semaphores import service_semaphores


def _global_context() -> GlobalContext:
    return GlobalContext(
        user=GlobalUserContext(id=1, name="테스터", email="test@example.com", department="개발"),
        workspace=GlobalWorkspaceContext(id=1, name="워크스페이스"),
        company=GlobalCompanyContext(id=1, name="테스트컴퍼니"),
    )

def _base_state(messages: list, agent_iteration: int = 0) -> dict:
    return {
        "messages": messages,
        "original_query": "test query",
        "rewritten_query": "test query rewritten",
        "agent_iteration": agent_iteration,
        "accumulated_docs": [],
        "global_context": _global_context(),
        "pipeline_plan": None,
        "prompt_settings": PromptSettings(),
        "search_plan": None,
        "max_pipeline_type": "standard",
    }

def _make_llm(content: str = "Reasoning content", tool_calls: list = None) -> MagicMock:
    response = AIMessage(content=content, tool_calls=tool_calls or [])
    llm_with_tools = MagicMock()
    llm_with_tools.ainvoke = AsyncMock(return_value=response)
    llm = MagicMock()
    llm.bind_tools.return_value = llm_with_tools
    return llm

class RagOptimizationTests(IsolatedAsyncioTestCase):
    def setUp(self):
        service_semaphores.init(small_llm_value=5, large_llm_value=5, reranker_value=5)

    @patch("catchup.rag.agents.standard_agent.adispatch_custom_event")
    @patch("catchup.rag.agents.standard_agent.prompt_loader.get_prompt", return_value="sys")
    @patch("catchup.langgraph.utils.extract_token_usages", return_value={})
    async def test_standard_agent_populates_reasoning_on_stop(self, _m1, _m2, _m3):
        llm = _make_llm(content="[Key Documents]: Doc1\n[Search Coverage]: All\n[Reason for Stopping]: Done")
        state = _base_state(messages=[])
        
        result = await standard_agent_node(state, llm)
        
        self.assertIn("agent_reasoning", result)
        self.assertEqual(result["agent_reasoning"], "[Key Documents]: Doc1\n[Search Coverage]: All\n[Reason for Stopping]: Done")

    @patch("catchup.rag.agents.complex_agent.adispatch_custom_event")
    @patch("catchup.rag.agents.complex_agent.prompt_loader.get_prompt", return_value="sys")
    @patch("catchup.langgraph.utils.extract_token_usages", return_value={})
    async def test_complex_agent_populates_reasoning_on_stop(self, _m1, _m2, _m3):
        llm = _make_llm(content="[Key Documents]: Doc2\n[Search Coverage]: Deep\n[Reason for Stopping]: Complete")
        state = _base_state(messages=[])
        state["max_pipeline_type"] = "complex"
        
        result = await complex_agent_node(state, llm)
        
        self.assertIn("agent_reasoning", result)
        self.assertEqual(result["agent_reasoning"], "[Key Documents]: Doc2\n[Search Coverage]: Deep\n[Reason for Stopping]: Complete")

