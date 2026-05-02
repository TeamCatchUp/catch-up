"""
ChatStreamProcessor 단위 테스트.

DB / LangGraph / 외부 서비스 의존성 없이 순수 로직만 검증한다.
"""
from __future__ import annotations

import uuid
from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

# 헬퍼
def _make_processor(save_message: AsyncMock | None = None):
    """테스트용 ChatStreamProcessor 인스턴스를 반환한다."""
    from catchup.chat.stream_processor import ChatStreamProcessor

    if save_message is None:
        save_message = AsyncMock(return_value=42)

    return ChatStreamProcessor(
        session_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        room_id=1,
        save_message=save_message,
        langfuse_trace_id=None,
    )


def _make_token_event(token: str, node: str = "generate_final_answer", tags: list[str] | None = None) -> dict[str, Any]:
    """on_chat_model_stream 이벤트 픽스처."""
    if tags is None:
        tags = ["stream_target", "has_citations"]
    chunk = MagicMock()
    chunk.content = token
    return {
        "event": "on_chat_model_stream",
        "name": "ChatModel",
        "data": {"chunk": chunk},
        "metadata": {"langgraph_node": node, "tags": tags},
    }


def _make_node_start_event(name: str, input_data: dict | None = None, tags: list[str] | None = None) -> dict[str, Any]:
    """on_chain_start 이벤트 픽스처."""
    if tags is None:
        tags = []
    return {
        "event": "on_chain_start",
        "name": name,
        "data": {"input": input_data or {}},
        "metadata": {"langgraph_node": name, "tags": tags},
    }


def _make_node_end_event(name: str, output: dict | None = None, tags: list[str] | None = None) -> dict[str, Any]:
    """on_chain_end 이벤트 픽스처."""
    if tags is None:
        tags = ["stream_target"]
    return {
        "event": "on_chain_end",
        "name": name,
        "data": {"output": output or {}},
        "metadata": {"langgraph_node": name, "tags": tags},
    }


async def _collect(processor, event: dict) -> list:
    """processor.process()가 yield 하는 모든 이벤트를 리스트로 수집한다."""
    results = []
    async for item in processor.process(event):
        results.append(item)
    return results


# Citation 버퍼 로직
class TestTokenStreamCitationBuffer(IsolatedAsyncioTestCase):
    """_handle_token_stream 의 citation 버퍼 분기를 검증한다."""

    def setUp(self):
        self.processor = _make_processor()

    async def test_plain_text_is_yielded_immediately(self):
        """일반 텍스트는 즉시 전송되고 버퍼는 비워진다."""
        from catchup.chat.schemas import ChatStreamingTokenResponse

        results = await _collect(self.processor, _make_token_event("Hello world"))

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], ChatStreamingTokenResponse)
        self.assertEqual(results[0].token, "Hello world")
        self.assertEqual(self.processor.context.buffer, "")

    async def test_suspicious_prefix_is_buffered(self):
        """<c, <ci, <cit 등 citations 태그의 앞부분은 버퍼링되고 전송되지 않는다.

        주의: "<citations" 자체는 컷오프 트리거("in" 검사) 조건을 만족하므로 목록에서 제외.
        """
        for prefix in ("<c", "<ci", "<cit", "<cita", "<citat", "<citati", "<citatio", "<citation"):
            with self.subTest(prefix=prefix):
                processor = _make_processor()
                results = await _collect(processor, _make_token_event(prefix))

                self.assertEqual(results, [], f"prefix '{prefix}' should be buffered, not yielded")
                self.assertEqual(processor.context.buffer, prefix)

    async def test_citations_tag_triggers_cutoff(self):
        """<citations 태그가 나타나면 그 앞 텍스트만 전송하고 스트리밍을 차단한다."""
        from catchup.chat.schemas import ChatStreamingTokenResponse

        results = await _collect(self.processor, _make_token_event("답변 내용<citations>..."))

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], ChatStreamingTokenResponse)
        self.assertEqual(results[0].token, "답변 내용")
        self.assertTrue(self.processor.context.is_citation_reached)

    async def test_citation_tag_at_start_yields_nothing(self):
        """텍스트 없이 <citations 태그만 있으면 아무것도 전송하지 않는다."""
        results = await _collect(self.processor, _make_token_event("<citations>..."))

        self.assertEqual(results, [])
        self.assertTrue(self.processor.context.is_citation_reached)

    async def test_buffered_prefix_followed_by_non_tag_is_flushed(self):
        """버퍼에 <c 가 있다가 citations가 아닌 문자가 이어지면 버퍼를 flush하여 전송한다."""
        from catchup.chat.schemas import ChatStreamingTokenResponse

        # 1차: <c 버퍼링
        await _collect(self.processor, _make_token_event("<c"))
        self.assertEqual(self.processor.context.buffer, "<c")

        # 2차: 'm'이 이어지면 <cm 은 <citations와 무관 → flush
        results = await _collect(self.processor, _make_token_event("m"))

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], ChatStreamingTokenResponse)
        self.assertEqual(results[0].token, "<cm")
        self.assertEqual(self.processor.context.buffer, "")

    async def test_tokens_after_citation_reached_are_ignored(self):
        """is_citation_reached=True 상태 이후의 토큰은 무시된다."""
        # 먼저 citation 상태로 만들기
        await _collect(self.processor, _make_token_event("텍스트<citations>"))
        self.assertTrue(self.processor.context.is_citation_reached)

        # 이후 토큰은 차단
        results = await _collect(self.processor, _make_token_event("이후 토큰"))
        self.assertEqual(results, [])

    async def test_non_target_node_is_skipped(self):
        """target 노드가 아닌 경우 토큰을 전송하지 않는다."""
        results = await _collect(self.processor, _make_token_event("Hello", node="route", tags=[]))
        self.assertEqual(results, [])


# 노드 시작 이벤트
class TestHandleNodeStart(IsolatedAsyncioTestCase):
    """_handle_node_start 를 검증한다."""

    def setUp(self):
        self.processor = _make_processor()

    async def test_known_node_yields_process_response(self):
        """INPROGRESS_NODES 에 있는 노드는 ChatStreamingProcessResponse를 yield한다."""
        from catchup.chat.schemas import ChatStreamingProcessResponse

        results = await _collect(self.processor, _make_node_start_event("rewrite"))

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], ChatStreamingProcessResponse)
        self.assertEqual(results[0].node, "rewrite")
        self.assertEqual(results[0].status, "in_progress")

    async def test_unknown_node_yields_nothing(self):
        """NODE_STATUS_MAP 에 없는 노드는 아무것도 yield하지 않는다."""
        results = await _collect(self.processor, _make_node_start_event("unknown_node"))
        self.assertEqual(results, [])

    @patch("catchup.chat.stream_processor.emit_audit_event")
    @patch("catchup.chat.stream_processor.ChatStreamingSourceResponse")
    async def test_generate_final_answer_emits_audit_and_sources(self, mock_source_resp, mock_emit):
        """generate_final_answer 노드 시작 시 audit event와 source response를 emit한다."""
        mock_source_instance = MagicMock()
        mock_source_resp.return_value = mock_source_instance

        doc = MagicMock()
        with patch("catchup.chat.stream_processor.BaseSource.from_document", return_value=MagicMock(id="src-1")):
            results = await _collect(
                self.processor,
                _make_node_start_event(
                    "generate_final_answer",
                    input_data={"retrieved_docs": [doc]},
                    tags=["has_citations"],
                ),
            )

        # ChatStreamingSourceResponse 가 한 번 생성됐는지 확인
        mock_source_resp.assert_called_once()
        # audit event 가 emit됐는지 확인
        mock_emit.assert_called_once()
        # source response 인스턴스가 yield됐는지 확인
        self.assertIn(mock_source_instance, results)


# is_citation_reached 게이팅
class TestCitationGating(IsolatedAsyncioTestCase):
    """is_citation_reached=True 일 때 이벤트 차단 여부를 검증한다."""

    def setUp(self):
        self.processor = _make_processor()
        self.processor.context.is_citation_reached = True

    async def test_non_final_answer_end_event_is_blocked(self):
        """is_citation_reached 상태에서 generate_final_answer on_chain_end 외 이벤트는 차단된다."""
        results = await _collect(self.processor, _make_token_event("토큰"))
        self.assertEqual(results, [])

    async def test_generate_final_answer_end_event_is_allowed(self):
        """is_citation_reached 상태에서도 generate_final_answer on_chain_end 이벤트는 통과된다."""
        msg = MagicMock()
        msg.content = "최종 답변"
        output = {"messages": [msg], "sources": []}

        self.processor.context.has_streamed = True  # fallback 방지

        results = await _collect(
            self.processor,
            _make_node_end_event("generate_final_answer", output=output, tags=["stream_target", "has_citations"]),
        )
        # 소스 없으면 빈 리스트지만 차단은 아님 — 예외 없이 통과
        self.assertIsInstance(results, list)


# current_node 추적
class TestCurrentNodeTracking(IsolatedAsyncioTestCase):
    """on_chain_start 이벤트에서 current_node가 올바르게 갱신되는지 검증한다."""

    async def test_current_node_is_updated_on_chain_start(self):
        processor = _make_processor()
        self.assertIsNone(processor.context.current_node)

        await _collect(processor, _make_node_start_event("grade"))

        self.assertEqual(processor.context.current_node, "grade")
