from __future__ import annotations

import uuid
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from catchup.rag.nodes.supervisor.supervisor import supervisor_node
from catchup.rag.schemas.context import GlobalCompanyContext
from catchup.rag.schemas.context import GlobalContext
from catchup.rag.schemas.context import GlobalUserContext
from catchup.rag.schemas.context import GlobalWorkspaceContext
from catchup.rag.schemas.structures import PipelinePlan
from catchup.rag.semaphores import rag_semaphores


def _global_context() -> GlobalContext:
    return GlobalContext(
        user=GlobalUserContext(
            id=1, name="테스터", email="test@example.com", department="개발"
        ),
        workspace=GlobalWorkspaceContext(id=1, name="워크스페이스"),
        company=GlobalCompanyContext(id=1, name="테스트컴퍼니"),
    )


def _base_state(session_id: uuid.UUID) -> dict:
    return {
        "messages": [],
        "original_query": "테스트 질문",
        "global_context": _global_context(),
        "session_id": session_id,
        "max_pipeline_type": "complex",
    }


class SupervisorStreamingTests(IsolatedAsyncioTestCase):
    """supervisor_node의 process 스트리밍 이벤트를 검증한다."""

    def setUp(self):
        rag_semaphores.init(
            small_model_sema_value=5, large_model_sema_value=5, rerank_sema_value=5
        )

    @patch("catchup.rag.nodes.supervisor.supervisor.adispatch_custom_event")
    @patch("catchup.rag.nodes.supervisor.supervisor.ainvoke_llm_with_token_usage")
    @patch("catchup.rag.nodes.supervisor.supervisor.prompt_loader.get_prompt", return_value="시스템 프롬프트")
    async def test_supervisor_streams_process(
        self, _mock_prompt, mock_invoke, mock_dispatch
    ):
        # Given
        session_id = uuid.uuid4()
        state = _base_state(session_id)
        llm = MagicMock()
        
        # Mock LLM response
        pipeline_plan = PipelinePlan(
            pipeline_type="standard",
            reasoning="이것은 테스트 이유입니다.",
            max_iterations=3
        )
        mock_invoke.return_value = ({"parsed": pipeline_plan}, {"total_tokens": 100})

        # When
        await supervisor_node(state, llm)

        # Then
        # Check if adispatch_custom_event was called at least twice (in_progress, completed)
        self.assertGreaterEqual(mock_dispatch.call_count, 2)
        
        # Check first call (in_progress)
        first_call = mock_dispatch.call_args_list[0]
        self.assertEqual(first_call.args[0], "process")
        self.assertEqual(first_call.args[1]["status"], "in_progress")
        self.assertEqual(first_call.args[1]["session_id"], str(session_id))
        
        # Check second call (completed)
        second_call = mock_dispatch.call_args_list[1]
        self.assertEqual(second_call.args[0], "process")
        self.assertEqual(second_call.args[1]["status"], "completed")
        self.assertEqual(second_call.args[1]["reasoning"], "이것은 테스트 이유입니다.")
        self.assertEqual(second_call.args[1]["content"], "standard")

    @patch("catchup.rag.nodes.supervisor.supervisor.adispatch_custom_event")
    @patch("catchup.rag.nodes.supervisor.supervisor.ainvoke_llm_with_token_usage")
    async def test_supervisor_streams_error(
        self, mock_invoke, mock_dispatch
    ):
        # Given
        session_id = uuid.uuid4()
        state = _base_state(session_id)
        llm = MagicMock()
        
        # Mock exception
        mock_invoke.side_effect = Exception("LLM failure")

        # When
        await supervisor_node(state, llm)

        # Then
        # Check if error event was dispatched
        error_call = None
        for call in mock_dispatch.call_args_list:
            if call.args[1]["status"] == "error":
                error_call = call
                break
        
        self.assertIsNotNone(error_call)
        self.assertEqual(error_call.args[0], "process")
        self.assertIn("LLM failure", error_call.args[1]["reasoning"])
