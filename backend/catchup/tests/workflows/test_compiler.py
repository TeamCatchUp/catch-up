"""compile_workflow() 단위 테스트.

외부 의존성(LLM, DB)은 전부 mock으로 대체한다.
NodeRegistry는 각 테스트마다 격리된 상태로 초기화한다.
"""
from __future__ import annotations

from unittest import IsolatedAsyncioTestCase

import pytest
from pydantic import BaseModel
from pydantic import Field

from catchup.workflows.graph.compiler import WorkflowCompileError
from catchup.workflows.graph.compiler import WorkflowState
from catchup.workflows.graph.compiler import _compile_cached
from catchup.workflows.graph.compiler import compile_workflow
from catchup.workflows.graph.compiler import resolve_inputs
from catchup.workflows.nodes.base import BaseConnector
from catchup.workflows.nodes.base import BaseTool
from catchup.workflows.nodes.common.action import action
from catchup.workflows.nodes.common.registry import NodeRegistry
from catchup.workflows.nodes.common.types import ChatMessage
from catchup.workflows.nodes.common.types import LlmResponse
from catchup.workflows.nodes.common.types import SearchResults

# ---------------------------------------------------------------------------
# 픽스처용 더미 노드
# ---------------------------------------------------------------------------

class _FetchInput(BaseModel):
    channel_id: str = Field(description="채널 ID.")


class _FetchOutput(BaseModel):
    message: str = Field(description="수신된 메시지 본문.")


class _SearchInput(BaseModel):
    query: str = Field(description="검색 쿼리.")


class _DraftInput(BaseModel):
    messages: list[ChatMessage] = Field(description="LLM에 전달할 메시지 목록.")
    search_results: SearchResults = Field(description="검색 결과.")


class _DraftOutput(BaseModel):
    response: LlmResponse = Field(description="LLM 응답.")


class FakeConnector(BaseConnector):
    @action(
        input_model=_FetchInput,
        output_model=_FetchOutput,
        description="더미 메시지를 반환한다.",
    )
    async def fetch(self, inputs: _FetchInput, node_results: dict) -> dict:
        return {"message": "테스트 메시지"}


class FakeSearchTool(BaseTool):
    @action(
        input_model=_SearchInput,
        output_model=SearchResults,
        description="더미 검색 결과를 반환한다.",
    )
    async def search(self, inputs: _SearchInput, node_results: dict) -> dict:
        return {"query": inputs.query, "items": [], "total": 0}


class FakeLlmTool(BaseTool):
    """search_results 타입이 SearchResults로 맞는 노드."""

    @action(
        input_model=_DraftInput,
        output_model=_DraftOutput,
        description="더미 LLM 응답을 생성한다.",
    )
    async def generate(self, inputs: _DraftInput, node_results: dict) -> dict:
        return {"response": {"content": "초안", "usage_metadata": None}}


class _MismatchedInput(BaseModel):
    """search_results 타입이 list[dict]로 잘못된 노드."""
    messages: list[ChatMessage]
    search_results: list[dict]  # SearchResults여야 하는데 list[dict]


class FakeMismatchedLlm(BaseTool):
    @action(
        input_model=_MismatchedInput,
        output_model=_DraftOutput,
        description="타입 불일치 테스트용.",
    )
    async def generate(self, inputs: _MismatchedInput, node_results: dict) -> dict:
        return {}


# ---------------------------------------------------------------------------
# 테스트 베이스: NodeRegistry 격리
# ---------------------------------------------------------------------------

class CompilerTestBase(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        # 각 테스트마다 레지스트리를 초기화
        NodeRegistry._nodes = {}
        _compile_cached.cache_clear()

        NodeRegistry.register(FakeConnector(
            name="fake_connector",
            display_name="Fake Connector",
            description="테스트용 커넥터.",
        ))
        NodeRegistry.register(FakeSearchTool(
            name="fake_search",
            display_name="Fake Search",
            description="테스트용 검색 툴.",
        ))
        NodeRegistry.register(FakeLlmTool(
            name="fake_llm",
            display_name="Fake LLM",
            description="테스트용 LLM 툴.",
        ))
        NodeRegistry.register(FakeMismatchedLlm(
            name="fake_mismatched_llm",
            display_name="Fake Mismatched LLM",
            description="타입 불일치 테스트용.",
        ))


# ---------------------------------------------------------------------------
# resolve_inputs 테스트
# ---------------------------------------------------------------------------

class ResolveInputsTests(CompilerTestBase):
    def _make_state(self) -> WorkflowState:
        return WorkflowState(
            trigger={"message": "안녕하세요", "channel": "ch-001"},
            node_results={"search": {"items": [{"content": "유사 사례"}], "total": 1, "query": "안녕"}},
            error=None,
            status="in_progress",
        )

    def test_trigger_표현식_해석(self) -> None:
        state = self._make_state()
        result = resolve_inputs({"query": "{{ trigger.message }}"}, state)
        self.assertEqual(result["query"], "안녕하세요")

    def test_context_표현식_해석(self) -> None:
        state = self._make_state()
        result = resolve_inputs(
            {"search_results": "{{ node_results.search.items }}"}, state
        )
        self.assertEqual(result["search_results"], [{"content": "유사 사례"}])

    def test_리터럴_값은_그대로_반환(self) -> None:
        state = self._make_state()
        result = resolve_inputs({"top_k": 5, "system": "당신은 전문가입니다."}, state)
        self.assertEqual(result["top_k"], 5)
        self.assertEqual(result["system"], "당신은 전문가입니다.")

    def test_존재하지_않는_경로는_KeyError(self) -> None:
        state = self._make_state()
        with self.assertRaises(KeyError):
            resolve_inputs({"x": "{{ node_results.missing_node.field }}"}, state)


# ---------------------------------------------------------------------------
# _validate_spec 테스트 (compile_workflow를 통해 간접 검증)
# ---------------------------------------------------------------------------

class ValidateSpecTests(CompilerTestBase):
    def _valid_spec(self) -> dict:
        return {
            "id": "test-workflow",
            "nodes": [
                {
                    "id": "search",
                    "node": "fake_search",
                    "action": "search",
                    "inputs": {"query": "{{ trigger.message }}"},
                },
            ],
            "edges": [],
        }

    def test_미등록_노드는_컴파일_에러(self) -> None:
        spec = self._valid_spec()
        spec["nodes"][0]["node"] = "nonexistent_node"
        with self.assertRaises(WorkflowCompileError, msg="노드 미등록"):
            compile_workflow(spec)

    def test_존재하지_않는_액션은_컴파일_에러(self) -> None:
        spec = self._valid_spec()
        spec["nodes"][0]["action"] = "nonexistent_action"
        with self.assertRaises(WorkflowCompileError, msg="액션 없음"):
            compile_workflow(spec)

    def test_선언되지_않은_input_필드는_컴파일_에러(self) -> None:
        spec = self._valid_spec()
        spec["nodes"][0]["inputs"]["unknown_field"] = "{{ trigger.message }}"
        with self.assertRaises(WorkflowCompileError, msg="input 필드 없음"):
            compile_workflow(spec)

    def test_존재하지_않는_노드_참조_표현식은_컴파일_에러(self) -> None:
        spec = self._valid_spec()
        spec["nodes"][0]["inputs"]["query"] = "{{ node_results.ghost_node.result }}"
        with self.assertRaises(WorkflowCompileError, msg="참조 노드 없음"):
            compile_workflow(spec)

    def test_타입_불일치는_컴파일_에러(self) -> None:
        """SearchResults → list[dict] 불일치를 컴파일 시점에 잡는다."""
        spec = {
            "id": "type-mismatch",
            "nodes": [
                {
                    "id": "search",
                    "node": "fake_search",
                    "action": "search",
                    "inputs": {"query": "{{ trigger.message }}"},
                },
                {
                    "id": "draft",
                    "node": "fake_mismatched_llm",
                    "action": "generate",
                    "inputs": {
                        "messages": [],
                        "search_results": "{{ node_results.search.items }}",
                    },
                },
            ],
            "edges": [{"from": "search", "to": "draft"}],
        }
        with self.assertRaises(WorkflowCompileError, msg="타입 불일치"):
            compile_workflow(spec)

    def test_유효한_스펙은_컴파일_성공(self) -> None:
        compile_workflow(self._valid_spec())  # 예외 없으면 통과


# ---------------------------------------------------------------------------
# 캐싱 테스트
# ---------------------------------------------------------------------------

class CachingTests(CompilerTestBase):
    def _spec(self) -> dict:
        return {
            "id": "cached-workflow",
            "nodes": [
                {
                    "id": "search",
                    "node": "fake_search",
                    "action": "search",
                    "inputs": {"query": "{{ trigger.message }}"},
                }
            ],
            "edges": [],
        }

    def test_동일_스펙은_같은_객체_반환(self) -> None:
        graph_a = compile_workflow(self._spec())
        graph_b = compile_workflow(self._spec())
        self.assertIs(graph_a, graph_b)

    def test_다른_스펙은_다른_객체_반환(self) -> None:
        spec_a = self._spec()
        spec_b = {**self._spec(), "id": "different-workflow"}
        graph_a = compile_workflow(spec_a)
        graph_b = compile_workflow(spec_b)
        self.assertIsNot(graph_a, graph_b)


# ---------------------------------------------------------------------------
# 노드 실행 통합 테스트
# ---------------------------------------------------------------------------

class NodeExecutionTests(CompilerTestBase):
    @pytest.mark.asyncio
    async def test_단일_노드_실행_결과가_context에_누적된다(self) -> None:
        spec = {
            "id": "exec-test",
            "nodes": [
                {
                    "id": "search",
                    "node": "fake_search",
                    "action": "search",
                    "inputs": {"query": "{{ trigger.message }}"},
                }
            ],
            "edges": [],
        }
        graph = compile_workflow(spec)
        initial_state: WorkflowState = {
            "trigger": {"message": "테스트 쿼리"},
            "node_results": {},
            "error": None,
            "status": "in_progress",
        }
        result = await graph.ainvoke(initial_state)

        self.assertIn("search", result["node_results"])
        self.assertEqual(result["node_results"]["search"]["query"], "테스트 쿼리")
        self.assertEqual(result["node_results"]["search"]["total"], 0)

    @pytest.mark.asyncio
    async def test_앞_노드_결과가_다음_노드_input으로_전달된다(self) -> None:
        spec = {
            "id": "chain-test",
            "nodes": [
                {
                    "id": "fetch",
                    "node": "fake_connector",
                    "action": "fetch",
                    "inputs": {"channel_id": "ch-001"},
                },
                {
                    "id": "search",
                    "node": "fake_search",
                    "action": "search",
                    "inputs": {"query": "{{ node_results.fetch.message }}"},
                },
            ],
            "edges": [{"from": "fetch", "to": "search"}],
        }
        graph = compile_workflow(spec)
        initial_state: WorkflowState = {
            "trigger": {},
            "node_results": {},
            "error": None,
            "status": "in_progress",
        }
        result = await graph.ainvoke(initial_state)

        self.assertEqual(result["node_results"]["fetch"]["message"], "테스트 메시지")
        # fetch.message → search.query 로 전달됐는지 확인
        self.assertEqual(result["node_results"]["search"]["query"], "테스트 메시지")
