from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from catchup.rag.agents.complex_agent import complex_agent_node
from catchup.rag.agents.standard_agent import collect_docs_node
from catchup.rag.agents.standard_agent import standard_agent_node
from catchup.rag.nodes.rerank.rerank import rerank_node
from catchup.rag.schemas.context import GlobalCompanyContext
from catchup.rag.schemas.context import GlobalContext
from catchup.rag.schemas.context import GlobalUserContext
from catchup.rag.schemas.context import GlobalWorkspaceContext
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
        rag_semaphores.init(small_llm_value=5, large_llm_value=5, reranker_value=5)

    @patch("catchup.rag.agents.standard_agent.prompt_loader.get_prompt", return_value="sys")
    @patch("catchup.rag.nodes.utils.extract_token_usages", return_value={})
    async def test_standard_agent_populates_reasoning_on_stop(self, _m1, _m2):
        llm = _make_llm(content="[Key Documents]: Doc1\n[Search Coverage]: All\n[Reason for Stopping]: Done")
        state = _base_state(messages=[])
        
        result = await standard_agent_node(state, llm)
        
        self.assertIn("agent_reasoning", result)
        self.assertEqual(result["agent_reasoning"], "[Key Documents]: Doc1\n[Search Coverage]: All\n[Reason for Stopping]: Done")

    @patch("catchup.rag.agents.complex_agent.prompt_loader.get_prompt", return_value="sys")
    @patch("catchup.rag.nodes.utils.extract_token_usages", return_value={})
    async def test_complex_agent_populates_reasoning_on_stop(self, _m1, _m2):
        llm = _make_llm(content="[Key Documents]: Doc2\n[Search Coverage]: Deep\n[Reason for Stopping]: Complete")
        state = _base_state(messages=[])
        state["max_pipeline_type"] = "complex"
        
        result = await complex_agent_node(state, llm)
        
        self.assertIn("agent_reasoning", result)
        self.assertEqual(result["agent_reasoning"], "[Key Documents]: Doc2\n[Search Coverage]: Deep\n[Reason for Stopping]: Complete")

    async def test_collect_docs_node_provides_fallback_reasoning(self):
        state = _base_state(messages=[])
        # agent_reasoning is NOT in state
        
        result = await collect_docs_node(state)
        
        self.assertIn("agent_reasoning", result)
        self.assertTrue(result["agent_reasoning"].startswith("[Key Documents]"))
        self.assertIn("reached maximum allotted iterations", result["agent_reasoning"])

    @patch("catchup.configs.config.settings.RERANK_TOP_N", 40)
    async def test_rerank_node_dynamic_k_and_boosting(self):
        mock_service = MagicMock()
        # 점수가 매우 촘촘한 50개 문서 (score_range = 0.0049)
        # Floor 0.05가 발동되어야 함.
        raw_docs = [Document(page_content=f"doc {i}", id=f"id_{i}", metadata={"relevance_score": 0.5 + (i*0.0001)}) for i in range(50)]
        mock_service.rerank = AsyncMock(return_value=raw_docs)
        
        doc_0_id = "id_0"
        state = _base_state(messages=[])
        state["max_pipeline_type"] = "complex"
        state["retrieved_docs"] = raw_docs
        state["essential_doc_ids"] = [doc_0_id]
        
        # 기본 boost_ratio=0.2, Floor=0.05 이므로 boost_value = 0.01
        # id_0의 원점수 0.5 -> 0.51
        # id_49의 원점수 0.5049. id_0이 1위가 됨.
        result = await rerank_node(state, mock_service)
        
        # doc 0이 부스팅되어 Top K(20개) 안에 들어왔는지 확인
        final_ids = [str(d.id) for d in result["retrieved_docs"]]
        self.assertIn(doc_0_id, final_ids)
        self.assertEqual(final_ids[0], doc_0_id) # 0.01 부스트면 0.5049인 id_49를 제치고 1위
        
        # 메타데이터 검증
        self.assertIn("rerank_metadata", result)
        meta = result["rerank_metadata"]
        self.assertEqual(meta["boosted_ids"], [doc_0_id])
        self.assertAlmostEqual(meta["score_range"], 0.0049)
        self.assertEqual(meta["effective_range"], 0.05) # Floor 발동
        self.assertAlmostEqual(meta["boost_value"], 0.01)

        # 문서 개별 메타데이터 검증
        doc_0 = next(d for d in result["retrieved_docs"] if d.id == "id_0")
        self.assertEqual(doc_0.metadata["original_rerank_score"], 0.5)
        self.assertAlmostEqual(doc_0.metadata["boosted_score"], 0.51)
        self.assertTrue(doc_0.metadata["is_agent_cited"])

    def test_index_alignment_between_summary_and_extraction(self):
        """build_docs_summary에서 보여주는 번호가 extract_essential_ids에서 정확히 매핑되는지 검증."""
        from catchup.rag.nodes.utils import build_docs_summary
        from catchup.rag.nodes.utils import extract_essential_ids
        from catchup.rag.nodes.utils import get_document_id
        
        docs = [
            Document(page_content="doc A", id="id_a"),
            Document(page_content="doc B", id="id_b"),
            Document(page_content="doc C", id="id_c"),
        ]
        
        # 1. build_docs_summary 결과 확인
        summary = build_docs_summary(docs)
        # summary 에는 "[1] (unknown) ... doc A", "[2] (unknown) ... doc B" 형식이 들어있음
        self.assertIn("[1] (unknown)", summary)
        self.assertIn("doc A", summary)
        self.assertIn("[3] (unknown)", summary)
        self.assertIn("doc C", summary)
        
        # 2. 에이전트가 "1번과 3번이 중요하다"고 답변한 상황 가정
        reasoning = "I found relevant info. [Key Document Indices]: 1, 3"
        
        # 3. 추출 결과가 실제 docs[0], docs[2]의 ID와 일치하는지 확인
        essential_ids = extract_essential_ids(reasoning, docs)
        
        expected_ids = {get_document_id(docs[0]), get_document_id(docs[2])}
        self.assertEqual(essential_ids, expected_ids)
        self.assertNotIn(get_document_id(docs[1]), essential_ids)

    @patch("catchup.rag.agents.standard_agent.prompt_loader.get_prompt", return_value="sys")
    @patch("catchup.rag.nodes.utils.extract_token_usages", return_value={})
    async def test_standard_agent_populates_essential_ids(self, _m1, _m2):
        # 1번과 3번 문서 지목
        reasoning = "[Key Document Indices]: 1, 3\n[Key Documents]: DocA, DocC"
        llm = _make_llm(content=reasoning)
        
        doc1 = Document(page_content="content 1", id="id_1")
        doc3 = Document(page_content="content 3", id="id_3")
        state = _base_state(messages=[])
        state["accumulated_docs"] = [doc1, Document(page_content="content 2", id="id_2"), doc3]
        
        result = await standard_agent_node(state, llm)
        
        self.assertIn("essential_doc_ids", result)
        expected_ids = {"id_1", "id_3"}
        self.assertEqual(set(result["essential_doc_ids"]), expected_ids)
