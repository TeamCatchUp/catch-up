"""
IsolatedChatBedrock이 rag_executors.llm_executor를 사용하는지 검증한다.

목적:
  - _agenerate / _astream 호출이 asyncio 기본 executor가 아닌
    rag_executors.llm_executor으로 실행됨을 보장한다.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock
from unittest.mock import patch

from catchup.components.llm.isolated_chat_bedrock import IsolatedChatBedrock
from catchup.rag.executors import rag_executors


class TestIsolatedChatBedrockExecutor(IsolatedAsyncioTestCase):

    def setUp(self):
        self._original_llm = rag_executors.llm_executor
        self._test_executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="llm-isolation-test"
        )
        rag_executors.llm_executor = self._test_executor

    def tearDown(self):
        self._test_executor.shutdown(wait=False)
        rag_executors.llm_executor = self._original_llm

    async def test_agenerate_uses_llm_executor(self):
        """_agenerate가 rag_executors.llm_executor으로 run_in_executor를 호출하는지 확인"""
        captured_executors: list = []

        async def fake_run_in_executor(executor, func, *args, **kwargs):
            captured_executors.append(executor)
            # 실제 실행은 하지 않고 가짜 결과 반환
            return MagicMock()

        llm = IsolatedChatBedrock(
            model_id="anthropic.claude-3-sonnet", region_name="us-east-1"
        )

        with patch(
            "catchup.components.llm.isolated_chat_bedrock.run_in_executor",
            side_effect=fake_run_in_executor,
        ):
            await llm._agenerate(messages=[MagicMock()])

        self.assertIn(
            rag_executors.llm_executor,
            captured_executors,
            "rag_executors.llm_executor가 사용되어야 합니다.",
        )

    async def test_astream_uses_llm_executor(self):
        """_astream의 모든 run_in_executor 호출(iterator 생성 + chunk 순회)이
        rag_executors.llm_executor을 사용하는지 확인"""
        captured_executors: list = []
    
        async def fake_run_in_executor(executor, func, *args, **kwargs):
            captured_executors.append(executor)
            # iterator와 chunk 순회 동작 흉내
            if func == llm._stream:
                return iter([MagicMock()])
            if func == next:
                # args: (iterator, sentinel)
                try:
                    return next(args[0])
                except StopIteration:
                    return args[1] # sentinel (done) 반환
            return MagicMock()

        llm = IsolatedChatBedrock(
            model_id="anthropic.claude-3-sonnet", region_name="us-east-1"
        )

        with patch(
            "catchup.components.llm.isolated_chat_bedrock.run_in_executor",
            side_effect=fake_run_in_executor,
        ):
            async for _ in llm._astream(messages=[MagicMock()]):
                pass

        self.assertGreater(len(captured_executors), 0)
        for executor in captured_executors:
            self.assertIs(executor, rag_executors.llm_executor)
