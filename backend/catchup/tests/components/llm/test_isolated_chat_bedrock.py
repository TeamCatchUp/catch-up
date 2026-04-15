"""
IsolatedChatBedrock이 rag_executors.llm을 사용하는지 검증한다.

목적:
  - _agenerate / _astream 호출이 asyncio 기본 executor가 아닌
    rag_executors.llm으로 실행됨을 보장한다.
  - ingestion default pool과 LLM 호출이 완전히 격리됨을 보장한다.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from langchain_core.messages import AIMessageChunk, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from catchup.components.llm.isolated_chat_bedrock import IsolatedChatBedrock
from catchup.rag.executors import rag_executors


def _make_llm() -> IsolatedChatBedrock:
    """AWS 연결 없이 IsolatedChatBedrock 인스턴스를 생성한다."""
    return object.__new__(IsolatedChatBedrock)


def _fake_chat_result() -> ChatResult:
    return ChatResult(
        generations=[ChatGeneration(message=HumanMessage(content="응답"))],
        llm_output={},
    )


class TestIsolatedChatBedrockExecutor(IsolatedAsyncioTestCase):

    def setUp(self):
        self._original_llm = rag_executors.llm
        self._test_executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="rag-llm-test"
        )
        rag_executors.llm = self._test_executor

    def tearDown(self):
        self._test_executor.shutdown(wait=False)
        rag_executors.llm = self._original_llm

    async def test_agenerate_uses_rag_executors_llm(self):
        """_agenerate가 rag_executors.llm으로 run_in_executor를 호출하는지 확인"""
        llm = _make_llm()
        captured_executors: list = []

        async def fake_run_in_executor(executor, func, *args, **kwargs):
            captured_executors.append(executor)
            return _fake_chat_result()

        with patch(
            "catchup.components.llm.isolated_chat_bedrock.run_in_executor",
            side_effect=fake_run_in_executor,
        ):
            await llm._agenerate(messages=[HumanMessage(content="테스트")])

        self.assertEqual(len(captured_executors), 1)
        self.assertIs(
            captured_executors[0],
            rag_executors.llm,
            "rag_executors.llm이 사용되어야 합니다.",
        )

    async def test_agenerate_not_using_default_executor(self):
        """_agenerate가 기본 executor(None)를 사용하지 않는지 확인"""
        llm = _make_llm()
        captured_executors: list = []

        async def fake_run_in_executor(executor, func, *args, **kwargs):
            captured_executors.append(executor)
            return _fake_chat_result()

        with patch(
            "catchup.components.llm.isolated_chat_bedrock.run_in_executor",
            side_effect=fake_run_in_executor,
        ):
            await llm._agenerate(messages=[HumanMessage(content="테스트")])

        for executor in captured_executors:
            self.assertIsNotNone(
                executor,
                "기본 executor(None)가 사용되면 ingestion과 thread pool을 공유하게 됩니다.",
            )

    async def test_astream_all_calls_use_rag_executors_llm(self):
        """_astream의 모든 run_in_executor 호출(iterator 생성 + chunk 순회)이
        rag_executors.llm을 사용하는지 확인"""
        llm = _make_llm()
        captured_executors: list = []

        fake_chunks = iter([
            ChatGenerationChunk(message=AIMessageChunk(content="안")),
            ChatGenerationChunk(message=AIMessageChunk(content="녕")),
        ])
        call_count = 0

        async def fake_run_in_executor(executor, func, *args, **kwargs):
            nonlocal call_count
            captured_executors.append(executor)
            call_count += 1
            if call_count == 1:
                # 첫 번째 호출: self._stream → iterator 반환
                return fake_chunks
            # 이후 호출: next(iterator, done)
            return func(*args, **kwargs)

        with patch(
            "catchup.components.llm.isolated_chat_bedrock.run_in_executor",
            side_effect=fake_run_in_executor,
        ):
            chunks = [
                chunk async for chunk in llm._astream(messages=[HumanMessage(content="테스트")])
            ]

        # iterator 생성 1회 + chunk 2회 + 종료 확인 1회 = 4회
        self.assertGreaterEqual(len(captured_executors), 3)
        for executor in captured_executors:
            self.assertIs(executor, rag_executors.llm)
            self.assertIsNotNone(executor)

        self.assertEqual(len(chunks), 2)

    async def test_astream_not_using_default_executor(self):
        """_astream이 기본 executor(None)를 사용하지 않는지 확인"""
        llm = _make_llm()
        captured_executors: list = []
        call_count = 0

        fake_chunks = iter([
            ChatGenerationChunk(message=AIMessageChunk(content="테스트")),
        ])

        async def fake_run_in_executor(executor, func, *args, **kwargs):
            nonlocal call_count
            captured_executors.append(executor)
            call_count += 1
            if call_count == 1:
                return fake_chunks
            return func(*args, **kwargs)

        with patch(
            "catchup.components.llm.isolated_chat_bedrock.run_in_executor",
            side_effect=fake_run_in_executor,
        ):
            _ = [chunk async for chunk in llm._astream(messages=[HumanMessage(content="테스트")])]

        for executor in captured_executors:
            self.assertIsNotNone(
                executor,
                "기본 executor(None)가 사용되면 ingestion과 thread pool을 공유하게 됩니다.",
            )
